"""
Webhook WhatsApp — reçoit les messages entrants, les fait traiter par
l'agent (LLM + tools + DB réelle), répond.
"""

import json
import time
from collections import OrderedDict

from fastapi import APIRouter, BackgroundTasks, Query, Request, Response

from app.agent.orchestrator import run_agent_turn
from app.business.lookup import get_business_by_whatsapp_number
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import async_session
from app.voice.stt.factory import get_stt_provider
from app.whatsapp.client import send_audio_message, send_image_message, send_text_message
from app.whatsapp.media import download_whatsapp_media
from app.whatsapp.security import verify_meta_signature

logger = get_logger("webhook")

router = APIRouter()

# Cache LRU de déduplication des messages WhatsApp entrants (wamid...)
# Conserve les 2000 derniers messages reçus pendant 15 minutes max.
_PROCESSED_MESSAGES: OrderedDict[str, float] = OrderedDict()
_MAX_PROCESSED_CACHE = 2000
_TTL_SECONDS = 900  # 15 minutes


def _is_duplicate_message(msg_id: str | None) -> bool:
    if not msg_id:
        return False
    now = time.time()

    # Nettoyage des messages expirés
    while _PROCESSED_MESSAGES and (now - next(iter(_PROCESSED_MESSAGES.values()))) > _TTL_SECONDS:
        _PROCESSED_MESSAGES.popitem(last=False)

    if msg_id in _PROCESSED_MESSAGES:
        return True

    _PROCESSED_MESSAGES[msg_id] = now
    if len(_PROCESSED_MESSAGES) > _MAX_PROCESSED_CACHE:
        _PROCESSED_MESSAGES.popitem(last=False)
    return False


async def process_whatsapp_message_task(
    to_number: str,
    from_number: str,
    text: str,
    msg_id: str | None,
    media_id: str | None = None,
    is_voice: bool = False,
    mime_type: str | None = None,
):
    """
    Exécute le tour d'agent et l'envoi de la réponse WhatsApp en tâche de fond.
    Prend en charge la transcription vocale (STT) et la synthèse de réponse vocale (TTS).
    """
    logger.info("Début traitement message en arrière-plan (id=%s, from=%s, voice=%s)", msg_id, from_number, is_voice)
    try:
        trans_lang = None
        # 1. Si une note vocale est reçue, télécharger et transcrire
        if media_id:
            try:
                audio_bytes, media_mime = await download_whatsapp_media(media_id)
                stt = get_stt_provider()
                trans_res = await stt.transcribe(
                    audio_bytes, mime_type=media_mime or mime_type or "audio/ogg; codecs=opus"
                )
                text = trans_res.text
                trans_lang = trans_res.detected_language
                logger.info("Transcription vocale réussie [%s] : %s", trans_lang, text)
            except Exception as stt_err:
                logger.error("Erreur lors de la transcription audio du média %s: %s", media_id, stt_err)
                if not text or text == "[NOTE_VOCALE_EN_ATTENTE_DE_TRANSCRIPTION]":
                    text = "Message vocal reçu (impossible à transcrire pour le moment)"

        async with async_session() as session:
            business = await get_business_by_whatsapp_number(session, to_number)
            if business is None:
                logger.warning("Aucun business trouvé pour le numéro de destination: %s", to_number)
                return

            reply_text, voice_url, photo_info = await run_agent_turn(
                session,
                business.id,
                text,
                customer_phone_number=from_number,
                is_voice=is_voice,
                return_voice_url=True,
                return_photo_info=True,
                forced_language=trans_lang,
            )

        # 2. Si une photo produit doit être envoyée, l'envoyer avant le texte
        if photo_info and photo_info.get("url"):
            try:
                await send_image_message(
                    to=from_number,
                    image_url=photo_info["url"],
                    caption=photo_info.get("caption"),
                )
                logger.info("Photo produit WhatsApp envoyée avec succès à %s", from_number)
            except Exception as img_err:
                logger.warning(
                    "Impossible d'envoyer la photo produit WhatsApp (%s). Envoi du texte seul.", img_err
                )

        # 3. Si une réponse vocale a été générée, envoyer la note vocale WhatsApp
        if voice_url:
            try:
                await send_audio_message(to=from_number, audio_url=voice_url)
                logger.info("Note vocale WhatsApp envoyée avec succès à %s", from_number)
            except Exception as audio_err:
                logger.warning("Impossible d'envoyer la note vocale WhatsApp (%s). Envoi du texte seul.", audio_err)

        # 4. Envoyer la réponse textuelle / transcription
        await send_text_message(to=from_number, body=reply_text)
        logger.info("Réponse WhatsApp envoyée avec succès à %s", from_number)
    except Exception as exc:
        logger.error(
            "Erreur lors du traitement ou de l'envoi du message WhatsApp à %s: %s",
            from_number,
            exc,
            exc_info=True,
        )


@router.get("/webhook/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(status_code=403)


@router.post("/webhook/whatsapp")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256")

    if not verify_meta_signature(raw_body, signature_header, settings.meta_app_secret):
        logger.warning("Signature Meta invalide ou absente — requête rejetée 403.")
        return Response(status_code=403)

    try:
        payload = json.loads(raw_body)
    except Exception:
        return {"status": "invalid_json"}

    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]["value"]
        messages = change.get("messages")
        if not messages:
            # Notifications de statut (sent, delivered, read) -> acquittées immédiatement
            return {"status": "status_update_ignored"}

        message = messages[0]
        msg_id = message.get("id")
        from_number = message["from"]
        to_number = change["metadata"]["display_phone_number"]
        msg_type = message.get("type", "text")
        media_id = None
        is_voice = False
        mime_type = None

        if msg_type == "location":
            loc = message.get("location", {})
            lat = loc.get("latitude")
            lng = loc.get("longitude")
            loc_name = loc.get("name") or ""
            loc_address = loc.get("address") or ""
            text = f"[LOCALISATION_GPS: latitude={lat}, longitude={lng}, repere={loc_name}, adresse={loc_address}]"
        elif msg_type == "audio":
            audio_info = message.get("audio", {})
            media_id = audio_info.get("id")
            # Tout message de type audio reçu déclenche une réponse vocale
            is_voice = True
            mime_type = audio_info.get("mime_type", "audio/ogg; codecs=opus")
            text = "[NOTE_VOCALE_EN_ATTENTE_DE_TRANSCRIPTION]"
        else:
            text = message.get("text", {}).get("body", "")
    except (KeyError, IndexError):
        return {"status": "ignored"}

    if not text:
        return {"status": "ignored"}

    # Déduplication : si Meta renvoie le message suite à un délai, on l'ignore
    if _is_duplicate_message(msg_id):
        logger.info("Message WhatsApp doublon ignoré (id=%s, from=%s)", msg_id, from_number)
        return {"status": "duplicate_ignored"}

    # Lancement immédiat en tâche d'arrière-plan pour libérer la requête HTTP Meta sous 100ms
    background_tasks.add_task(
        process_whatsapp_message_task,
        to_number=to_number,
        from_number=from_number,
        text=text,
        msg_id=msg_id,
        media_id=media_id,
        is_voice=is_voice,
        mime_type=mime_type,
    )

    return {"status": "queued"}