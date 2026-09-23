"""
Client pour envoyer des messages via l'API WhatsApp Cloud (Meta).
Intègre un mécanisme natif de retry avec backoff exponentiel pour la résilience réseau (Sprint 8).
"""

import asyncio
import logging
import httpx

from app.core.config import settings

logger = logging.getLogger("maliagent.whatsapp.client")


def _is_retryable_whatsapp_error(exc: BaseException) -> bool:
    """
    Ne retente que les erreurs transitoires :
    - Timeout réseau, coupure de connexion, erreur de socket.
    - Erreurs serveur Meta Graph API (code HTTP 5xx : 500, 502, 503, 504).
    
    Une erreur client 4xx (400 Bad Request, 401 Token invalide/expiré, 404, etc.)
    ne doit JAMAIS être retentée afin d'éviter les boucles d'appels inutiles.
    """
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


async def _post_with_retry(
    url: str,
    headers: dict,
    json_payload: dict,
    max_retries: int = 3,
) -> dict:
    """
    Envoie une requête POST avec retry automatique et backoff exponentiel (1s, 2s, 4s).
    """
    delays = [1, 2, 4]
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, headers=headers, json=json_payload)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            is_last_attempt = (attempt == max_retries - 1)
            if not _is_retryable_whatsapp_error(exc) or is_last_attempt:
                raise

            delay = delays[min(attempt, len(delays) - 1)]
            logger.warning(
                f"Échec appel Meta WhatsApp ({exc}). "
                f"Nouvelle tentative dans {delay}s (tentative {attempt + 1}/{max_retries})..."
            )
            await asyncio.sleep(delay)

    raise RuntimeError("Échec inattendu de la boucle de retry")


async def send_text_message(to: str, body: str) -> dict:
    """
    Envoie un message texte à un numéro WhatsApp avec retry automatique.

    to: numéro au format international sans "+", ex. "22300000000"
    """
    url = f"https://graph.facebook.com/v21.0/{settings.whatsapp_phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    return await _post_with_retry(url, headers, payload)


async def send_document_message(
    to: str,
    document_url: str,
    caption: str | None = None,
    filename: str | None = None,
) -> dict:
    """
    Envoie un document (ex: facture PDF) à un numéro WhatsApp via l'API Cloud Meta avec retry automatique.
    """
    url = f"https://graph.facebook.com/v21.0/{settings.whatsapp_phone_number_id}/messages"
    doc_data: dict[str, str] = {"link": document_url}
    if caption:
        doc_data["caption"] = caption
    if filename:
        doc_data["filename"] = filename

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "document",
        "document": doc_data,
    }
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    return await _post_with_retry(url, headers, payload)


async def send_image_message(
    to: str,
    image_url: str,
    caption: str | None = None,
) -> dict:
    """
    Envoie une image (ex: photo produit) à un numéro WhatsApp via l'API Cloud Meta avec retry automatique.
    """
    url = f"https://graph.facebook.com/v21.0/{settings.whatsapp_phone_number_id}/messages"
    image_data: dict[str, str] = {"link": image_url}
    if caption:
        image_data["caption"] = caption

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": image_data,
    }
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    return await _post_with_retry(url, headers, payload)


async def send_audio_message(to: str, audio_url: str) -> dict:
    """
    Envoie une note vocale / message audio à un numéro WhatsApp avec retry automatique.
    """
    url = f"https://graph.facebook.com/v21.0/{settings.whatsapp_phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "audio",
        "audio": {"link": audio_url},
    }
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    return await _post_with_retry(url, headers, payload)