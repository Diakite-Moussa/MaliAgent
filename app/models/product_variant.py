"""
ProductVariant = Déclinaison d'un produit (couleur, taille, mémoire...).
Section 13.6 du cahier des charges fonctionnel.
"""

import uuid
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BusinessScopedMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.product import Product


class ProductVariant(Base, UUIDPKMixin, BusinessScopedMixin, TimestampMixin):
    __tablename__ = "product_variants"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Nom de l'attribut (ex: "Taille", "Capacité", "Couleur")
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Valeur de la déclinaison (ex: "XL", "256Go", "Noir")
    value: Mapped[str] = mapped_column(String(100), nullable=False)

    # Prix spécifique à cette variante (si None, le prix de base du Product s'applique)
    price: Mapped[Numeric | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Stock dédié à cette déclinaison
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Référence produit / code-barre facultatif
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Image optionnelle spécifique à cette déclinaison (ex: photo du t-shirt rouge)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="variants")

    @property
    def label(self) -> str:
        """Libellé lisible pour l'agent et le client (ex: 'Taille: XL' ou '128Go')"""
        return f"{self.name}: {self.value}" if self.name.lower() not in self.value.lower() else self.value

    def __repr__(self) -> str:
        return f"<ProductVariant {self.name}={self.value!r} stock={self.stock_quantity}>"
