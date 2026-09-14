"""
Payment = Modèle de gestion des paiements Mobile Money (Wave, Orange Money, Mock).

Section V2.1 du projet MaliAgent.
Gère les 8 statuts de paiement, l'isolation multi-tenant, l'idempotence des webhooks (provider_event_id),
et les relations vers Order et Customer.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BusinessScopedMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.order import Order


class PaymentStatus(str, enum.Enum):
    INITIATED = "initiated"                 # Session créée, en attente de redirection ou prompt USSD
    PENDING_VALIDATION = "pending_validation" # En attente de validation par le client (PIN/USSD/App)
    PROCESSING = "processing"               # En cours de traitement côté opérateur
    SUCCESS = "success"                     # Transaction validée et fonds confirmés
    FAILED = "failed"                       # Transaction rejetée (solde insuffisant, code erroné)
    CANCELLED = "cancelled"                 # Abandonné par le client
    EXPIRED = "expired"                     # Délai de paiement dépassé (session timeout)
    REFUNDED = "refunded"                   # Remboursé (total ou partiel)


class PaymentProvider(str, enum.Enum):
    MOCK = "mock"
    WAVE = "wave"
    ORANGE_MONEY = "orange_money"
    CASH_ON_DELIVERY = "cash_on_delivery"


class Payment(Base, UUIDPKMixin, BusinessScopedMixin, TimestampMixin):
    __tablename__ = "payments"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False, default=PaymentProvider.MOCK.value)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="XOF")

    status: Mapped[PaymentStatus] = mapped_column(
        Enum(
            PaymentStatus,
            name="payment_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PaymentStatus.INITIATED,
        index=True,
    )

    # Référence unique interne MaliAgent (ex: PAY-2026-OM-9A7B1C)
    transaction_reference: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )

    # Identifiant de transaction renvoyé par l'opérateur externe (Wave / Orange Money)
    provider_tx_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    # Identifiant unique de l'événement webhook pour IDEMPOTENCE ABSOLUE
    provider_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True, index=True)

    # Numéro de téléphone du payeur (+223...)
    customer_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Lien direct de checkout (Wave deep link ou page web)
    checkout_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # QR Code URL
    qr_code_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Date et heure de confirmation effective du paiement
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Métadonnées brutes / audits JSONB
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relations
    order: Mapped[Order] = relationship("Order", back_populates="payments", lazy="selectin")
    customer: Mapped[Customer] = relationship("Customer", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Payment {self.transaction_reference} ({self.provider} - {self.status.value}): {self.amount} {self.currency}>"
