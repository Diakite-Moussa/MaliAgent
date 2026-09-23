"""
Product = un article du catalogue d'un Business.

Le champ `category` est indispensable : le test de tool calling
(scripts/test_tool_calling.py) a montré qu'une recherche par nom exact
seul échoue sur des requêtes client naturelles ("un téléphone pas cher").
Le vrai search_products devra chercher sur name ET category.
"""

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class Product(Base, UUIDPKMixin, BusinessScopedMixin, TimestampMixin):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Prix en unité entière de la devise du Business (ex. FCFA n'a pas de
    # sous-unité usuelle) — Numeric plutôt que float pour éviter les erreurs
    # d'arrondi sur des montants réels.
    price: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)

    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # URL publique de la photo produit (upload local /api/products/images/...
    # ou URL externe CDN/Cloudinary), utilisée pour l'envoi WhatsApp.
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<Product {self.name!r} ({self.category})>"