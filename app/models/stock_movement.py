"""
StockMovement = journal d'audit de tout changement de stock_quantity sur un Product.

Règle du projet : ne JAMAIS modifier product.stock_quantity directement.
Toujours passer par record_stock_movement() (app/services/stock.py) pour
garantir que ce journal reste exhaustif et fiable — c'est la seule source
de vérité pour distinguer une vente WhatsApp, une annulation, ou un
réapprovisionnement manuel Dashboard.
"""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class StockMovementType(str, enum.Enum):
    SALE = "sale"  # Vente WhatsApp (create_order)
    CANCELLATION = "cancellation"  # Réapprovisionnement (cancel_order)
    MANUAL_RESTOCK = "manual_restock"  # Ajustement positif, Dashboard
    MANUAL_ADJUSTMENT = "manual_adjustment"  # Ajustement négatif/correctif, Dashboard


class StockMovement(Base, UUIDPKMixin, BusinessScopedMixin, TimestampMixin):
    __tablename__ = "stock_movements"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True, index=True
    )
    movement_type: Mapped[StockMovementType] = mapped_column(
        Enum(StockMovementType, name="stock_movement_type", native_enum=False, length=30),
        nullable=False,
    )
    quantity_change: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_before: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<StockMovement {self.movement_type.value} {self.quantity_change:+d}>"
