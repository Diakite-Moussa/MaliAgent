"""
Category = Catégorie formalisée de produits propre à un Business.
Section 13.5 du cahier des charges fonctionnel.
"""

from typing import TYPE_CHECKING
from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BusinessScopedMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.product import Product


class Category(Base, UUIDPKMixin, BusinessScopedMixin, TimestampMixin):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("business_id", "name", name="uq_categories_business_name"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    products: Mapped[list["Product"]] = relationship(
        "Product", back_populates="category_rel"
    )

    def __repr__(self) -> str:
        return f"<Category {self.name!r} (business={self.business_id})>"
