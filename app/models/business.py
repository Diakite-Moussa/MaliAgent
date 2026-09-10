"""
Business = un commerçant pilote sur la plateforme.

C'est la racine du multi-tenant : tout le reste (Product, Customer, Order...)
est rattaché à un Business via business_id.
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class Business(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "businesses"

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Numéro WhatsApp Business associé (format E.164, ex. +22300000000).
    # Sert à router les messages entrants vers le bon Business.
    whatsapp_phone_number: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True
    )

    # Devise d'affichage des prix, ex. "XOF" (FCFA). Simple pour le MVP —
    # un seul pays/devise par business, pas de multi-devise.
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="XOF")

    def __repr__(self) -> str:
        return f"<Business {self.name!r}>"
