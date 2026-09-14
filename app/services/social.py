"""
Couche d'abstraction pour les réseaux sociaux et canaux conversationnels.
Section 22 du cahier des charges de la plateforme MaliAgent.
Prépare l'extension de WhatsApp vers Instagram, Facebook Messenger et TikTok.
"""

from abc import ABC, abstractmethod
from typing import Any

from app.core.config import settings
from app.whatsapp.security import verify_meta_signature


class SocialMediaService(ABC):
    """Interface générique définissant le contrat de communication multi-canal."""

    @abstractmethod
    async def send_text_message(self, recipient_id: str, text: str) -> dict[str, Any]:
        """Envoie un message textuel au destinataire final."""
        pass

    @abstractmethod
    async def send_order_invoice(self, recipient_id: str, invoice_pdf_url: str, caption: str) -> dict[str, Any]:
        """Transmet une facture PDF ou un document multimédia."""
        pass

    @abstractmethod
    def verify_webhook_signature(self, raw_body: bytes, signature_header: str) -> bool:
        """Vérifie la signature cryptographique du webhook entrant."""
        pass

    @abstractmethod
    def get_channel_info(self) -> dict[str, Any]:
        """Retourne les informations de configuration et l'état de santé du canal."""
        pass


class WhatsAppCloudAPIService(SocialMediaService):
    """Implémentation officielle Meta WhatsApp Cloud API (Graph API v21.0)."""

    def __init__(self):
        self.phone_number_id = settings.whatsapp_phone_number_id
        self.access_token = settings.whatsapp_access_token
        self.app_secret = settings.meta_app_secret

    async def send_text_message(self, recipient_id: str, text: str) -> dict[str, Any]:
        from app.whatsapp.client import send_text_message
        return await send_text_message(to=recipient_id, body=text)

    async def send_order_invoice(self, recipient_id: str, invoice_pdf_url: str, caption: str) -> dict[str, Any]:
        from app.whatsapp.client import send_document_message
        return await send_document_message(to=recipient_id, document_url=invoice_pdf_url, caption=caption)

    def verify_webhook_signature(self, raw_body: bytes, signature_header: str) -> bool:
        return verify_meta_signature(
            payload_body=raw_body,
            signature_header=signature_header,
            app_secret=self.app_secret or "",
        )

    def get_channel_info(self) -> dict[str, Any]:
        return {
            "channel": "whatsapp",
            "provider": "Meta Graph API v21.0",
            "phone_number_id": self.phone_number_id or "Non configuré",
            "is_configured": bool(self.access_token and self.app_secret),
        }


class InstagramMessagingService(SocialMediaService):
    """Connecteur préparatoire pour Instagram Direct Messaging via Meta Graph API."""

    async def send_text_message(self, recipient_id: str, text: str) -> dict[str, Any]:
        # Extension V2 prévue avec OAuth Instagram Graph API
        return {"status": "queued", "channel": "instagram", "recipient_id": recipient_id}

    async def send_order_invoice(self, recipient_id: str, invoice_pdf_url: str, caption: str) -> dict[str, Any]:
        return {"status": "queued", "channel": "instagram", "recipient_id": recipient_id}

    def verify_webhook_signature(self, raw_body: bytes, signature_header: str) -> bool:
        return verify_meta_signature(
            payload_body=raw_body,
            signature_header=signature_header,
            app_secret=settings.meta_app_secret or "",
        )

    def get_channel_info(self) -> dict[str, Any]:
        return {
            "channel": "instagram",
            "provider": "Instagram Direct (Meta)",
            "is_configured": False,
            "roadmap": "Prévu V2",
        }


class FacebookMessengerService(SocialMediaService):
    """Connecteur préparatoire pour Facebook Messenger."""

    async def send_text_message(self, recipient_id: str, text: str) -> dict[str, Any]:
        return {"status": "queued", "channel": "facebook", "recipient_id": recipient_id}

    async def send_order_invoice(self, recipient_id: str, invoice_pdf_url: str, caption: str) -> dict[str, Any]:
        return {"status": "queued", "channel": "facebook", "recipient_id": recipient_id}

    def verify_webhook_signature(self, raw_body: bytes, signature_header: str) -> bool:
        return verify_meta_signature(
            payload_body=raw_body,
            signature_header=signature_header,
            app_secret=settings.meta_app_secret or "",
        )

    def get_channel_info(self) -> dict[str, Any]:
        return {
            "channel": "facebook",
            "provider": "Facebook Messenger (Meta)",
            "is_configured": False,
            "roadmap": "Prévu V2",
        }


class TikTokMessagingService(SocialMediaService):
    """Connecteur préparatoire pour TikTok Direct Messages API."""

    async def send_text_message(self, recipient_id: str, text: str) -> dict[str, Any]:
        return {"status": "queued", "channel": "tiktok", "recipient_id": recipient_id}

    async def send_order_invoice(self, recipient_id: str, invoice_pdf_url: str, caption: str) -> dict[str, Any]:
        return {"status": "queued", "channel": "tiktok", "recipient_id": recipient_id}

    def verify_webhook_signature(self, raw_body: bytes, signature_header: str) -> bool:
        return False

    def get_channel_info(self) -> dict[str, Any]:
        return {
            "channel": "tiktok",
            "provider": "TikTok Business Direct Message API",
            "is_configured": False,
            "roadmap": "Prévu V2",
        }
