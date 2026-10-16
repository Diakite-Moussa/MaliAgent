"""
WavePaymentGateway : Connecteur officiel Wave Checkout API (Réservé Phase 2 — Production).

Documentation officielle : https://docs.wave.com/checkout
Ce module prépare l'intégration de production avec l'API Wave Mali :
- Session checkout (POST /v1/checkout/sessions)
- Vérification cryptographique des signatures de webhooks (Wave-Signature)
- Gestion des devises XOF (FCFA) et deep-links mobiles

Note : En phase actuelle V2.1 (développement), le mode actif est PAYMENT_PROVIDER=mock.
Toute tentative d'utilisation directe en production sans clés marchandes lève NotImplementedError.
"""

from app.core.config import settings
from app.payments.base import (
    BasePaymentGateway,
    PaymentInitiateRequest,
    PaymentInitiateResult,
    PaymentVerifyResult,
    PaymentWebhookResult,
)


class WavePaymentGateway(BasePaymentGateway):
    """
    Passerelle de paiement Wave Mali pour la Phase 2 (Production).
    Prête pour injection des credentials marchands :
    - WAVE_API_KEY
    - WAVE_API_URL
    - WAVE_WEBHOOK_SECRET
    """

    def __init__(self):
        self.api_key = settings.wave_api_key
        self.api_url = settings.wave_api_url or "https://api.wave.com/v1/checkout/sessions"
        self.webhook_secret = settings.wave_webhook_secret

    async def initiate_payment(self, request: PaymentInitiateRequest) -> PaymentInitiateResult:
        """
        Initie une session de paiement Wave Checkout officielle.
        TODO Phase 2 :
        1. Requête HTTP POST sécurisée vers self.api_url avec header Authorization: Bearer {self.api_key}
        2. Payload : {
               "amount": str(request.amount),
               "currency": "XOF",
               "client_reference": str(request.order_id),
               "success_url": request.return_url,
               "error_url": request.return_url
           }
        3. Retourner checkout_url = response.json()["wave_launch_url"]
        """
        raise NotImplementedError(
            "WavePaymentGateway n'est pas encore actif en production. "
            "Configurez WAVE_API_KEY et passez PAYMENT_MODE=production après signature du contrat marchand Wave."
        )

    async def verify_payment(self, transaction_ref: str) -> PaymentVerifyResult:
        """
        Interroge l'API Wave pour vérifier l'état de la session.
        TODO Phase 2 :
        GET https://api.wave.com/v1/checkout/sessions/{session_id}
        """
        raise NotImplementedError(
            "Vérification d'API Wave réservée à la phase 2 de production."
        )

    @staticmethod
    def verify_signature(raw_body: str | bytes, signature_header: str, secret: str) -> bool:
        """
        Vérifie l'en-tête 'Wave-Signature' de format : t=1492774577,v1=52571869e79ce...
        selon la spécification officielle Wave Checkout.
        """
        import hashlib
        import hmac

        if not signature_header or not secret:
            return False
        try:
            parts = dict(item.split("=", 1) for item in signature_header.split(",") if "=" in item)
            timestamp = parts.get("t")
            v1_signature = parts.get("v1")
            if not timestamp or not v1_signature:
                return False

            if isinstance(raw_body, str):
                raw_body = raw_body.encode("utf-8")
            to_sign = f"{timestamp}.".encode("utf-8") + raw_body
            expected_mac = hmac.new(secret.encode("utf-8"), to_sign, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected_mac, v1_signature)
        except Exception:
            return False

    async def process_webhook(self, payload: dict, headers: dict) -> PaymentWebhookResult:
        """
        Traite un webhook officiel envoyé par les serveurs de Wave Mali.
        """
        if not self.api_key:
            raise NotImplementedError(
                "Traitement des webhooks réels Wave réservé à la phase 2 de production (WAVE_API_KEY requise)."
            )

        sig_header = headers.get("wave-signature") or headers.get("Wave-Signature") or ""
        raw_body = payload.get("_raw_body", "")
        if self.webhook_secret and not self.verify_signature(raw_body, sig_header, self.webhook_secret):
            return PaymentWebhookResult(
                success=False,
                handled=False,
                transaction_reference="",
                provider_event_id="",
                status=PaymentStatus.FAILED,
                error_message="Signature Wave invalide.",
            )

        event_type = payload.get("type", "")
        data = payload.get("data", {})
        tx_ref = data.get("client_reference", "")
        event_id = payload.get("id", "")

        from datetime import datetime, timezone
        from decimal import Decimal

        if event_type == "checkout.session.completed":
            amount_val = Decimal(str(data.get("amount", "0")))
            return PaymentWebhookResult(
                success=True,
                handled=True,
                transaction_reference=tx_ref,
                provider_event_id=event_id,
                provider_tx_id=data.get("id"),
                status=PaymentStatus.SUCCESS,
                paid_at=datetime.now(timezone.utc),
                amount=amount_val,
                raw_event=payload,
            )

        return PaymentWebhookResult(
            success=True,
            handled=False,
            transaction_reference=tx_ref,
            provider_event_id=event_id,
            status=PaymentStatus.PROCESSING,
            raw_event=payload,
        )
