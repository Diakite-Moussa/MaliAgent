"""
DeliveryPartner = Entreprise ou flotte partenaire de livraison tierce.
Sprint 9 (V2.0 Logistique & Flotte).
"""

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class DeliveryPartner(Base, UUIDPKMixin, BusinessScopedMixin, TimestampMixin):
    __tablename__ = "delivery_partners"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    missions = relationship("DeliveryMission", back_populates="partner")

    def __repr__(self) -> str:
        return f"<DeliveryPartner {self.name!r} ({self.phone_number})>"
