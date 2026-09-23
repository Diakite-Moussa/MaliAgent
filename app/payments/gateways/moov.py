"""
MoovPaymentGateway : Connecteur Moov Money / Flooz Mali (Moov Africa).

Documentation et intégration Moov Africa Mali :
- Déclenchement de demande de débit Push USSD (*166#)
- Traitement sécurisé des notifications de paiement IPN (Instant Payment Notification)
- Support de la devise XOF (FCFA)

Note : En phase de développement (PAYMENT_PROVIDER=mock), MockPaymentGateway prend en charge les flux.
En production, cette passerelle communique avec les serveurs de Moov Africa Mali.
"""

from app.core.config import settings
from app.payments.base import (
    BasePaymentGateway,
    PaymentInitiateRequest,
    PaymentInitiateResult,
    PaymentVerifyResult,
    PaymentWebhookResult,
)


class MoovPaymentGateway(BasePaymentGateway):
    """
    Passerelle de paiement Moov Money / Moov Africa Mali pour la Phase 2 (Production).
    Prête pour injection des credentials marchands :
    - MOOV_CLIENT_ID
    - MOOV_CLIENT_SECRET
    - MOOV_API_URL
    - MOOV_WEBHOOK_SECRET
    """

    def __init__(self):
        self.client_id = settings.moov_client_id
        self.client_secret = settings.moov_client_secret
        self.api_url = settings.moov_api_url or "https://api.moov-africa.ml/flooz/v1"
        self.webhook_secret = settings.moov_webhook_secret

    async def initiate_payment(self, request: PaymentInitiateRequest) -> PaymentInitiateResult:
        """
        Initie un ordre de paiement Moov Money (Push USSD ou Web checkout).
        """
        raise NotImplementedError(
            "MoovPaymentGateway n'est pas encore actif en production. "
            "Configurez MOOV_CLIENT_ID/SECRET et passez PAYMENT_MODE=production après signature du contrat Moov Africa Mali."
        )

    async def verify_payment(self, transaction_ref: str) -> PaymentVerifyResult:
        """
        Interroge l'API Moov Money pour vérifier l'état d'une transaction.
        """
        raise NotImplementedError(
            "Vérification d'API Moov Money réservée à la phase de production."
        )

    def verify_signature(self, headers: dict) -> bool:
        """Vérifie le jeton ou signature d'authentification fourni par Moov Africa Mali."""
        if not self.webhook_secret:
            return True
        token = headers.get("x-moov-signature") or headers.get("authorization") or ""
        return self.webhook_secret in token

    async def process_webhook(self, payload: dict, headers: dict) -> PaymentWebhookResult:
        """
        Traite la notification IPN envoyée par Moov Africa Mali.
        """
        if not self.client_id:
            raise NotImplementedError(
                "Traitement des webhooks réels Moov Money réservé à la phase de production (MOOV_CLIENT_ID requis)."
            )

        if not self.verify_signature(headers):
            return PaymentWebhookResult(
                success=False,
                handled=False,
                transaction_reference="",
                provider_event_id="",
                status=PaymentStatus.FAILED,
                error_message="Authentification IPN Moov Money invalide.",
            )

        tx_ref = payload.get("reference") or payload.get("order_id") or payload.get("trans_id", "")
        status_raw = (payload.get("status") or "").upper()
        event_id = payload.get("event_id") or payload.get("moov_tx_id") or ""

        from datetime import datetime, timezone
        from decimal import Decimal

        status_mapping = {
            "SUCCESS": PaymentStatus.SUCCESS,
            "SUCCESSFUL": PaymentStatus.SUCCESS,
            "CONFIRMED": PaymentStatus.SUCCESS,
            "FAILED": PaymentStatus.FAILED,
            "EXPIRED": PaymentStatus.EXPIRED,
            "CANCELLED": PaymentStatus.CANCELLED,
        }
        mapped_status = status_mapping.get(status_raw, PaymentStatus.PROCESSING)
        amount_val = None
        if "amount" in payload:
            try:
                amount_val = Decimal(str(payload["amount"]))
            except Exception:
                pass

        return PaymentWebhookResult(
            success=True,
            handled=True,
            transaction_reference=tx_ref,
            provider_event_id=event_id,
            provider_tx_id=payload.get("moov_tx_id"),
            status=mapped_status,
            paid_at=datetime.now(timezone.utc) if mapped_status == PaymentStatus.SUCCESS else None,
            amount=amount_val,
            raw_event=payload,
        )
