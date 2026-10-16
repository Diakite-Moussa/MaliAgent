"""
Product = un article du catalogue d'un Business.

Le champ `category` est indispensable : le test de tool calling
(scripts/test_tool_calling.py) a montré qu'une recherche par nom exact
seul échoue sur des requêtes client naturelles ("un téléphone pas cher").
Le vrai search_products devra chercher sur name ET category.
"""

import uuid
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BusinessScopedMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.product_variant import ProductVariant


class Product(Base, UUIDPKMixin, BusinessScopedMixin, TimestampMixin):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Référence optionnelle à la table Category formalisée (Section 13.5)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Conservation de category (string) pour rétrocompatibilité et recherche rapide
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True, default="Général")

    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Prix en unité entière de la devise du Business (ex. FCFA n'a pas de
    # sous-unité usuelle) — Numeric plutôt que float pour éviter les erreurs
    # d'arrondi sur des montants réels.
    price: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)

    # Stock global (si le produit n'a pas de variantes, c'est le stock direct).
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Seuil personnalisable par produit (remplace le <= 3 en dur de l'API).
    low_stock_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3"
    )

    # URL publique de la photo produit (upload local /api/products/images/...
    # ou URL externe CDN/Cloudinary), utilisée pour l'envoi WhatsApp.
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    category_rel: Mapped["Category | None"] = relationship(
        "Category", back_populates="products", lazy="selectin"
    )

    variants: Mapped[list["ProductVariant"]] = relationship(
        "ProductVariant",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ProductVariant.created_at",
    )

    @property
    def has_variants(self) -> bool:
        """Indique si le produit dispose de déclinaisons spécifiques (taille, couleur...)."""
        if "variants" in self.__dict__ and self.variants is not None:
            return len(self.variants) > 0
        return False

    @property
    def effective_stock(self) -> int:
        """Retourne la somme du stock des variantes si définies, sinon stock_quantity."""
        if self.has_variants:
            return sum(v.stock_quantity for v in self.variants)
        return self.stock_quantity

    def __repr__(self) -> str:
        return f"<Product {self.name!r} ({self.category}) variants={len(self.variants)}>"