"""
Order = une commande passée par un Customer auprès d'un Business.
OrderItem = une ligne de commande (un produit + une quantité).

Le prix unitaire est recopié dans OrderItem au moment de la commande
(unit_price_snapshot) plutôt que d'aller relire Product.price à chaque
fois — sinon une commande passée change de montant si le commerçant
modifie ses prix après coup. C'est une règle de facturation classique :
la facture doit refléter le prix au moment de l'achat, pas le prix actuel.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BusinessScopedMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.delivery_mission import DeliveryMission
    from app.models.invoice import Invoice
    from app.models.payment import Payment
    from app.models.product import Product
    from app.models.product_variant import ProductVariant


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
    customer: Mapped[Customer] = relationship("Customer", lazy="selectin")

    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"), nullable=False, default=OrderStatus.PENDING
    )

    # Adresse/zone de livraison en texte libre pour le MVP — la section 23.1
    # (calculate_delivery) affinera ça plus tard avec un modèle DeliveryZone.
    delivery_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    delivery_fee: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    # Coordonnées GPS exactes partagées par le client via WhatsApp (V2.2)
    delivery_latitude: Mapped[Numeric | None] = mapped_column(Numeric(10, 7), nullable=True)
    delivery_longitude: Mapped[Numeric | None] = mapped_column(Numeric(10, 7), nullable=True)

    # Statut et méthode de paiement (V2.1)
    # payment_status: 'unpaid', 'pending', 'paid', 'refunded'
    payment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unpaid")
    payment_method: Mapped[str | None] = mapped_column(String(32), nullable=True)

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )

    payments: Mapped[list[Payment]] = relationship(
        "Payment", back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )

    invoice: Mapped["Invoice | None"] = relationship(
        "Invoice", back_populates="order", uselist=False, lazy="selectin"
    )

    delivery_missions: Mapped[list["DeliveryMission"]] = relationship(
        "DeliveryMission", back_populates="order", cascade="all, delete-orphan", lazy="selectin"
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
    # Référence optionnelle à la déclinaison exacte (Section 13.6)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Nom figé de la variante au moment de la commande (ex: "Couleur: Noir, Taille: XL")
    variant_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Prix unitaire au moment de la commande — voir note en haut du fichier.
    unit_price_snapshot: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(
        "Product", foreign_keys=[product_id], lazy="selectin"
    )
    variant: Mapped["ProductVariant | None"] = relationship(
        "ProductVariant", foreign_keys=[variant_id], lazy="selectin"
    )

    def __repr__(self) -> str:
        var_info = f" ({self.variant_name})" if self.variant_name else ""
        return f"<OrderItem product={self.product_id}{var_info} qty={self.quantity}>"
