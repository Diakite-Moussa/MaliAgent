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


async def send_document_message(
    to: str,
    document_url: str,
    caption: str | None = None,
    filename: str | None = None,
) -> dict:
    """
    Envoie un document (ex: facture PDF) à un numéro WhatsApp via l'API Cloud Meta.
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
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()