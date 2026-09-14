"""
Conversation et Message : historique conversationnel multi-tours.

Sections 13.10 et 13.11 du cahier des charges fonctionnel.
Permet à l'agent de conserver le fil de la discussion avec chaque client WhatsApp.
"""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class Conversation(Base, UUIDPKMixin, BusinessScopedMixin, TimestampMixin):
    __tablename__ = "conversations"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True
    )

    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="whatsapp")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")  # "active" | "needs_human" | "closed"
    handoff_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Conversation {self.id} ({self.status})>"


class ConversationMessage(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True
    )

    role: Mapped[str] = mapped_column(String(32), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<ConversationMessage {self.role}: {self.content[:30]!r}>"
