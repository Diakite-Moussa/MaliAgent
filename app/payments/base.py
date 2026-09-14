"""
Interface de base et DTOs pour les passerelles de paiement (Gateway / Adapter pattern).

Section V2.1 du projet MaliAgent.
Définit le contrat strict que tout provider (Mock, Wave, Orange Money) doit implémenter.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
import uuid

from app.models.payment import PaymentStatus


@dataclass
class PaymentInitiateRequest:
    """Paramètres pour initier une transaction de paiement."""
    order_id: uuid.UUID
    business_id: uuid.UUID
    customer_id: uuid.UUID
    amount: Decimal
    currency: str = "XOF"
    customer_phone: str | None = None
    customer_name: str | None = None
    order_ref: str | None = None
    provider_name: str = "mock"  # "mock", "wave", "orange_money"
    return_url: str | None = None


@dataclass
class PaymentInitiateResult:
    """Résultat renvoyé après l'initiation auprès de la gateway."""
    success: bool
    transaction_reference: str
    provider: str
    status: PaymentStatus
    checkout_url: str | None = None
    qr_code_url: str | None = None
    provider_tx_id: str | None = None
    instructions: str | None = None
    error_message: str | None = None
    raw_response: dict = field(default_factory=dict)


@dataclass
class PaymentVerifyResult:
    """Résultat d'une vérification active auprès de l'opérateur."""
    success: bool
    transaction_reference: str
    provider_tx_id: str | None
    status: PaymentStatus
    paid_at: datetime | None = None
    amount: Decimal | None = None
    error_message: str | None = None


@dataclass
class PaymentWebhookResult:
    """Résultat après le traitement d'une notification webhook de l'opérateur."""
    success: bool
    handled: bool
    transaction_reference: str
    status: PaymentStatus
    provider_event_id: str  # Pour idempotence absolue
    provider_tx_id: str | None = None
    paid_at: datetime | None = None
    amount: Decimal | None = None
    raw_event: dict = field(default_factory=dict)
    error_message: str | None = None


class BasePaymentGateway(ABC):
    """Interface abstraite que chaque connecteur de paiement doit implémenter."""

    @abstractmethod
    async def initiate_payment(self, request: PaymentInitiateRequest) -> PaymentInitiateResult:
        """Initie une session ou un ordre de paiement (checkout URL ou push USSD)."""
        pass

    @abstractmethod
    async def verify_payment(self, transaction_ref: str) -> PaymentVerifyResult:
        """Interroge l'API de l'opérateur pour vérifier l'état courant de la transaction."""
        pass

    @abstractmethod
    async def process_webhook(self, payload: dict, headers: dict) -> PaymentWebhookResult:
        """Parse et valide un webhook opérateur entrant (signature, événement, statut)."""
        pass
