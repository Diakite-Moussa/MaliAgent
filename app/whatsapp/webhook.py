"""
Webhook WhatsApp — reçoit les messages entrants et répond.

Pour l'instant : bot en écho (renvoie ce qu'on lui envoie), juste pour
valider que la boucle Meta → notre backend → Meta fonctionne de bout
en bout, avant de brancher le vrai LLM.
"""

from fastapi import APIRouter, Query, Request, Response

from app.core.config import settings
from app.whatsapp.client import send_text_message

router = APIRouter()


@router.get("/webhook/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    """Meta appelle ceci une fois, pour valider le webhook."""
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(status_code=403)


@router.post("/webhook/whatsapp")
async def receive_message(request: Request):
    """Reçoit un message entrant et répond en écho (pour l'instant)."""
    payload = await request.json()

    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]["value"]
        message = change["messages"][0]
        from_number = message["from"]
        text = message.get("text", {}).get("body", "")
    except (KeyError, IndexError):
        # Pas un message texte entrant (accusé de lecture, statut, etc.)
        # — on ignore proprement.
        return {"status": "ignored"}

    await send_text_message(to=from_number, body=f"Écho : {text}")

    return {"status": "ok"}