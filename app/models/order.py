"""
Order = une commande passée par un Customer auprès d'un Business.
OrderItem = une ligne de commande (un produit + une quantité).

Le prix unitaire est recopié dans OrderItem au moment de la commande
(unit_price_snapshot) plutôt que d'aller relire Product.price à chaque
fois — sinon une commande passée change de montant si le commerçant
modifie ses prix après coup. C'est une règle de facturation classique :
la facture doit refléter le prix au moment de l'achat, pas le prix actuel.
"""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class OrderStatus(str, enum.Enum):
    PENDING = "pending"  # créée, pas encore confirmée
    CONFIRMED = "confirmed"  # confirmée par le commerçant
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Order(Base, UUIDPKMixin, BusinessScopedMixin, TimestampMixin):
    __tablename__ = "orders"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True
    )

    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"), nullable=False, default=OrderStatus.PENDING
    )

    # Adresse/zone de livraison en texte libre pour le MVP — la section 23.1
    # (calculate_delivery) affinera ça plus tard avec un modèle DeliveryZone.
    delivery_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    delivery_fee: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )


    @property
    def total_amount(self) -> "Numeric":
        return sum((item.unit_price_snapshot * item.quantity for item in self.items), start=0) + (
            self.delivery_fee or 0
        )

    def __repr__(self) -> str:
        return f"<Order {self.id} ({self.status.value})>"


class OrderItem(Base, UUIDPKMixin):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )

    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Prix unitaire au moment de la commande — voir note en haut du fichier.
    unit_price_snapshot: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return f"<OrderItem product={self.product_id} qty={self.quantity}>"
