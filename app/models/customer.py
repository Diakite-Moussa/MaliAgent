"""
Customer = le client d'un Business, identifié par son numéro WhatsApp.

Un même numéro de téléphone peut être client de plusieurs Business
différents (deux boutiques distinctes) — d'où l'unicité sur
(business_id, whatsapp_phone_number) plutôt que sur le numéro seul.
"""

from typing import TYPE_CHECKING

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BusinessScopedMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class Customer(Base, UUIDPKMixin, BusinessScopedMixin, TimestampMixin):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("business_id", "whatsapp_phone_number", name="uq_customer_per_business"),
    )

    whatsapp_phone_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Préférences linguistiques et canal (V0.5 Voice & Multilingual)
    preferred_language: Mapped[str] = mapped_column(String(10), nullable=False, default="fr")
    preferred_channel_type: Mapped[str] = mapped_column(String(16), nullable=False, default="text")

    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="customer", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Customer {self.whatsapp_phone_number!r}>"
