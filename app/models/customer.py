"""
Customer = le client d'un Business, identifié par son numéro WhatsApp.

Un même numéro de téléphone peut être client de plusieurs Business
différents (deux boutiques distinctes) — d'où l'unicité sur
(business_id, whatsapp_phone_number) plutôt que sur le numéro seul.
"""

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class Customer(Base, UUIDPKMixin, BusinessScopedMixin, TimestampMixin):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("business_id", "whatsapp_phone_number", name="uq_customer_per_business"),
    )

    whatsapp_phone_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<Customer {self.whatsapp_phone_number!r}>"
