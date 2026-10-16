"""
MockPaymentGateway : Implémentation complète de simulation pour la Phase 1 (Développement / Test / Recette).

Imite fidèlement le comportement d'un vrai opérateur Mobile Money :
- Génération de références de transaction
- Simulation de lien de checkout (Wave)
- Simulation de push USSD (Orange Money)
- Génération et validation de webhooks simulés avec idempotence (provider_event_id)
- Simulation des cas de succès, échec solde et expiration
"""

from datetime import datetime, timezone
from decimal import Decimal
import uuid

from app.core.config import settings
from app.models.payment import PaymentStatus
from app.payments.base import (
    BasePaymentGateway,
    PaymentInitiateRequest,
    PaymentInitiateResult,
    PaymentVerifyResult,
    PaymentWebhookResult,
)


class MockPaymentGateway(BasePaymentGateway):
    """
    Passerelle de simulation.
    Permet de tester l'ensemble du cycle de vente sans dépendre d'un vrai compte marchand.
    """

    def __init__(self):
        self.gateway_name = "mock"

    async def initiate_payment(self, request: PaymentInitiateRequest) -> PaymentInitiateResult:
        sub_provider = (request.provider_name or "mock").lower()
        short_id = uuid.uuid4().hex[:8].upper()

        if "wave" in sub_provider:
            tx_ref = f"PAY-WAV-{short_id}"
            provider_tag = "mock_wave"
            checkout_url = f"{settings.public_base_url}/api/payments/mock-checkout/{tx_ref}"
            instructions = (
                f"Lien Wave sécurisé généré pour {request.amount} {request.currency}. "
                f"Cliquez sur le lien pour valider dans votre application Wave."
            )
        elif "orange" in sub_provider:
            tx_ref = f"PAY-OM-{short_id}"
            provider_tag = "mock_orange_money"
            checkout_url = f"{settings.public_base_url}/api/payments/mock-checkout/{tx_ref}"
            phone_str = request.customer_phone or "votre mobile"
            instructions = (
                f"Une demande Orange Money de {request.amount} {request.currency} a été envoyée sur {phone_str}. "
                f"Tapez votre code secret Orange Money pour valider la transaction."
            )
        elif "moov" in sub_provider or "malitel" in sub_provider:
            tx_ref = f"PAY-MOV-{short_id}"
            provider_tag = "mock_moov_money"
            checkout_url = f"{settings.public_base_url}/api/payments/mock-checkout/{tx_ref}"
            phone_str = request.customer_phone or "votre mobile"
            instructions = (
                f"Une demande Moov Money de {request.amount} {request.currency} a été envoyée sur {phone_str}. "
                f"Composez le *166# ou validez la notification sur votre mobile pour confirmer."
            )
        else:
            tx_ref = f"PAY-SIM-{short_id}"
            provider_tag = "mock"
            checkout_url = f"{settings.public_base_url}/api/payments/mock-checkout/{tx_ref}"
            instructions = f"Paiement de simulation initié pour {request.amount} {request.currency}."

        return PaymentInitiateResult(
            success=True,
            transaction_reference=tx_ref,
            provider=provider_tag,
            status=PaymentStatus.PENDING_VALIDATION,
            checkout_url=checkout_url,
            qr_code_url=f"{checkout_url}?view=qr",
            provider_tx_id=f"MOCK-TX-{short_id}",
            instructions=instructions,
            raw_response={"mock": True, "created_at": datetime.now(timezone.utc).isoformat()},
        )

    async def verify_payment(self, transaction_ref: str) -> PaymentVerifyResult:
        return PaymentVerifyResult(
            success=True,
            transaction_reference=transaction_ref,
            provider_tx_id=f"MOCK-VERIFY-{transaction_ref}",
            status=PaymentStatus.SUCCESS,
            paid_at=datetime.now(timezone.utc),
            amount=Decimal("0.00"),
        )

    async def process_webhook(self, payload: dict, headers: dict) -> PaymentWebhookResult:
        """
        Traite un payload de webhook simulé.
        Format attendu du payload simulé :
        {
            "event_id": "evt_123456",
            "transaction_reference": "PAY-...",
            "status": "success" | "failed" | "expired",
            "amount": 10000,
            "provider_tx_id": "TX-..." (optionnel)
        }
        """
        tx_ref = payload.get("transaction_reference") or payload.get("client_reference") or ""
        event_id = payload.get("event_id") or f"mock_evt_{uuid.uuid4().hex[:12]}"
        status_str = (payload.get("status") or "success").lower()

        if not tx_ref:
            return PaymentWebhookResult(
                success=False,
                handled=False,
                transaction_reference="",
                provider_event_id=event_id,
                status=PaymentStatus.FAILED,
                error_message="Champ transaction_reference manquant dans le payload webhook",
            )

        status_map = {
            "success": PaymentStatus.SUCCESS,
            "failed": PaymentStatus.FAILED,
            "expired": PaymentStatus.EXPIRED,
            "cancelled": PaymentStatus.CANCELLED,
            "processing": PaymentStatus.PROCESSING,
        }
        mapped_status = status_map.get(status_str, PaymentStatus.SUCCESS)
        now = datetime.now(timezone.utc) if mapped_status == PaymentStatus.SUCCESS else None

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
            provider_tx_id=payload.get("provider_tx_id") or f"TX-MOCK-{uuid.uuid4().hex[:8].upper()}",
            status=mapped_status,
            paid_at=now,
            amount=amount_val,
            raw_event=payload,
        )

    @staticmethod
    def build_simulated_webhook(
        transaction_reference: str,
        outcome: str = "success",
        event_id: str | None = None,
        amount: Decimal | None = None,
    ) -> dict:
        """Génère un payload de webhook simulé prêt à l'emploi pour les tests et la démonstration."""
        return {
            "event_id": event_id or f"mock_evt_{uuid.uuid4().hex[:12]}",
            "transaction_reference": transaction_reference,
            "status": outcome,
            "amount": float(amount) if amount is not None else 0.0,
            "provider_tx_id": f"OP-TX-{uuid.uuid4().hex[:8].upper()}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
