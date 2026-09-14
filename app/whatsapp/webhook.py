"""
Webhook WhatsApp — reçoit les messages entrants, les fait traiter par
l'agent (LLM + tools + DB réelle), répond.
"""

import json

from fastapi import APIRouter, Query, Request, Response

from app.agent.orchestrator import run_agent_turn
from app.business.lookup import get_business_by_whatsapp_number
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import async_session
from app.whatsapp.client import send_text_message
from app.whatsapp.security import verify_meta_signature

logger = get_logger("webhook")

router = APIRouter()


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
async def receive_message(request: Request):
    raw_body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256")

    if not verify_meta_signature(raw_body, signature_header, settings.meta_app_secret):
        logger.warning("Signature Meta invalide ou absente — requête rejetée 403.")
        return Response(status_code=403)

    payload = json.loads(raw_body)

    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]["value"]
        message = change["messages"][0]
        from_number = message["from"]
        to_number = change["metadata"]["display_phone_number"]
        text = message.get("text", {}).get("body", "")
    except (KeyError, IndexError):
        return {"status": "ignored"}

    if not text:
        return {"status": "ignored"}

    async with async_session() as session:
        business = await get_business_by_whatsapp_number(session, to_number)
        if business is None:
            logger.warning("Aucun business trouvé pour le numéro de destination: %s", to_number)
            return {"status": "no_business_found"}

        reply = await run_agent_turn(
            session, business.id, text, customer_phone_number=from_number
        )

    try:
        await send_text_message(to=from_number, body=reply)
    except Exception as exc:
        logger.error("Erreur lors de l'envoi du message WhatsApp à %s: %s", from_number, exc)
        return {"status": "send_error", "detail": str(exc)}

    return {"status": "ok"}