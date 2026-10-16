"""
OrangeMoneyPaymentGateway : Connecteur Orange Money Web Payment & USSD Push (Réservé Phase 2 — Production).

Documentation officielle : https://developer.orange.com/tech-guide/orange-money-web-pay/
Ce module prépare l'intégration de production avec Orange Money MEA / Mali :
- Authentification OAuth2 Client Credentials
- Ordre de paiement Web Payment ou déclenchement Push USSD
- Réception et validation des callbacks IPN (Instant Payment Notification)

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


class OrangeMoneyPaymentGateway(BasePaymentGateway):
    """
    Passerelle de paiement Orange Money Mali pour la Phase 2 (Production).
    Prête pour injection des credentials marchands :
    - ORANGE_CLIENT_ID
    - ORANGE_CLIENT_SECRET
    - ORANGE_API_URL
    - ORANGE_WEBHOOK_SECRET
    """

    def __init__(self):
        self.client_id = settings.orange_client_id
        self.client_secret = settings.orange_client_secret
        self.api_url = settings.orange_api_url or "https://api.orange.com/orange-money-webpay/dev/v1"
        self.webhook_secret = settings.orange_webhook_secret

    async def initiate_payment(self, request: PaymentInitiateRequest) -> PaymentInitiateResult:
        """
        Initie un ordre de paiement Orange Money (Web Payment ou Push USSD).
        TODO Phase 2 :
        1. Obtenir un jeton OAuth2 via POST https://api.orange.com/oauth/v3/token
        2. POST vers {self.api_url}/webpayment avec body :
           {
               "merchant_key": self.client_id,
               "currency": "OUV", # ou XOF
               "order_id": str(request.order_id),
               "amount": int(request.amount),
               "return_url": request.return_url,
               "cancel_url": request.return_url,
               "reference": f"OM-ML-{request.order_id}"
           }
        3. Retourner payment_url
        """
        raise NotImplementedError(
            "OrangeMoneyPaymentGateway n'est pas encore actif en production. "
            "Configurez ORANGE_CLIENT_ID/SECRET et passez PAYMENT_MODE=production après signature du contrat marchand Orange."
        )

    async def verify_payment(self, transaction_ref: str) -> PaymentVerifyResult:
        """
        Interroge l'état de la transaction Orange Money.
        TODO Phase 2 :
        GET {self.api_url}/transactionstatus
        """
        raise NotImplementedError(
            "Vérification d'API Orange Money réservée à la phase 2 de production."
        )

    def verify_ipn_token(self, headers: dict) -> bool:
        """Vérifie le token de sécurité ou signature IPN envoyé par Orange Money."""
        if not self.webhook_secret:
            return True
        token = headers.get("x-orange-token") or headers.get("authorization") or ""
        return self.webhook_secret in token

    async def process_webhook(self, payload: dict, headers: dict) -> PaymentWebhookResult:
        """
        Traite la notification IPN envoyée par le serveur Orange Money Mali.
        """
        if not self.client_id:
            raise NotImplementedError(
                "Traitement des webhooks réels Orange Money réservé à la phase 2 de production (ORANGE_CLIENT_ID requis)."
            )

        if not self.verify_ipn_token(headers):
            return PaymentWebhookResult(
                success=False,
                handled=False,
                transaction_reference="",
                provider_event_id="",
                status=PaymentStatus.FAILED,
                error_message="Authentification IPN Orange Money invalide.",
            )

        tx_ref = payload.get("order_id") or payload.get("reference") or payload.get("notif_token", "")
        status_raw = (payload.get("status") or "").upper()
        event_id = payload.get("txnid") or payload.get("pay_token") or ""

        from datetime import datetime, timezone
        from decimal import Decimal

        status_mapping = {
            "SUCCESS": PaymentStatus.SUCCESS,
            "SUCCESSFULL": PaymentStatus.SUCCESS,
            "FAILED": PaymentStatus.FAILED,
            "EXPIRED": PaymentStatus.EXPIRED,
            "CANCELLED": PaymentStatus.CANCELLED,
            "INITIATED": PaymentStatus.PENDING_VALIDATION,
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
            provider_tx_id=payload.get("txnid"),
            status=mapped_status,
            paid_at=datetime.now(timezone.utc) if mapped_status == PaymentStatus.SUCCESS else None,
            amount=amount_val,
            raw_event=payload,
        )
