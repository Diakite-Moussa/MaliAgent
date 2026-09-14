"""
DeliveryZone = une zone de livraison avec son tarif et son délai estimé.

Section 13.15 du cahier des charges fonctionnel.
"""

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class DeliveryZone(Base, UUIDPKMixin, BusinessScopedMixin, TimestampMixin):
    __tablename__ = "delivery_zones"

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Mots-clés / alias pour la recherche insensible à la casse (ex. "aci, aci 2000, hamdallaye")
    keywords: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Frais de livraison en FCFA
    fee: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    # Délai estimé (ex. "1h à 2h", "Dans la journée")
    estimated_time: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Active ou désactivée
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<DeliveryZone {self.name!r} ({self.fee} FCFA)>"
