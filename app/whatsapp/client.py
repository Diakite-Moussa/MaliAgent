"""
Client pour envoyer des messages via l'API WhatsApp Cloud (Meta).
"""

import httpx

from app.core.config import settings


async def send_text_message(to: str, body: str) -> dict:
    """
    Envoie un message texte à un numéro WhatsApp.

    to: numéro au format international sans "+", ex. "22300000000"
    """
    url = f"https://graph.facebook.com/v21.0/{settings.whatsapp_phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()