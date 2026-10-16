"""
AgentConfiguration = personnalisation de l'agent IA par Business.

Section 13.14 du cahier des charges : chaque boutique peut personnaliser
le nom de son agent, son ton, sa langue par défaut, ses règles métier
propres, son message d'accueil, et le désactiver temporairement.

Relation 1-1 avec Business (business_id unique). Interrogée par requête
explicite (select(AgentConfiguration).where(...)), comme le reste du
projet, plutôt que via une relation ORM chargée depuis Business.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class AgentConfiguration(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "agent_configurations"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    agent_name: Mapped[str] = mapped_column(String(100), nullable=False, default="Assistant")
    tone: Mapped[str] = mapped_column(String(50), nullable=False, default="chaleureux")
    default_language: Mapped[str] = mapped_column(String(5), nullable=False, default="fr")
    custom_rules: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    welcome_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return (
            f"<AgentConfiguration business_id={self.business_id} "
            f"name={self.agent_name!r} enabled={self.enabled}>"
        )