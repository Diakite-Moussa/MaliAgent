"""
Invoice = facture générée pour une commande passée.

Section 13.9 du cahier des charges fonctionnel.
Supporte le statut 'issued' (en attente de paiement) et 'paid' (acquittée).
"""

import uuid

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BusinessScopedMixin, TimestampMixin, UUIDPKMixin
from app.models.order import Order


class Invoice(Base, UUIDPKMixin, BusinessScopedMixin, TimestampMixin):
    __tablename__ = "invoices"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, unique=True, index=True
    )

    invoice_number: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )

    subtotal: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    delivery_fee: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)

    # 'issued' (émise / en attente de règlement), 'paid' (acquittée), 'cancelled' (annulée)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="issued")

    # Chemin local vers le fichier PDF généré
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    order: Mapped[Order] = relationship("Order", lazy="selectin")


    def __repr__(self) -> str:
        return f"<Invoice {self.invoice_number} ({self.status}): {self.total} FCFA>"
