"""
Téléchargement et gestion des fichiers médias (audio, images, documents)
depuis l'API WhatsApp Cloud de Meta (Graph API).
"""

import logging
import httpx

from app.core.config import settings

logger = logging.getLogger("maliagent.whatsapp.media")


async def download_whatsapp_media(media_id: str) -> tuple[bytes, str]:
    """
    Télécharge le contenu binaire d'un média WhatsApp (ex: note vocale audio)
    à partir de son identifiant Meta 'media_id'.

    Retourne:
        tuple (bytes_content, mime_type)
    """
    if not settings.whatsapp_access_token:
        raise ValueError("WHATSAPP_ACCESS_TOKEN non configuré.")

    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}

    async with httpx.AsyncClient(timeout=45) as client:
        # Étape 1 : Récupération de l'URL de téléchargement signée par Meta
        meta_url = f"https://graph.facebook.com/v21.0/{media_id}"
        resp = await client.get(meta_url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        download_url = data.get("url")
        mime_type = data.get("mime_type", "audio/ogg; codecs=opus")

        if not download_url:
            raise ValueError(f"URL de téléchargement introuvable pour le média {media_id}")

        # Étape 2 : Téléchargement effectif du flux binaire
        media_resp = await client.get(download_url, headers=headers)
        media_resp.raise_for_status()
        media_bytes = media_resp.content

        logger.info(
            "Média WhatsApp %s téléchargé avec succès (%d octets, type: %s)",
            media_id,
            len(media_bytes),
            mime_type,
        )
        return media_bytes, mime_type
