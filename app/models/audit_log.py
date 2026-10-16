"""
Modèle AuditLog pour la traçabilité complète des actions du Super Admin et du système.
Section 14 du cahier des charges de la plateforme MaliAgent.
"""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.user import User


class AuditLog(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    # ID de l'utilisateur ayant exécuté l'action (Super Admin ou système)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Type d'action (ex: CREATE_BUSINESS, SUSPEND_BUSINESS, IMPERSONATE_BUSINESS, etc.)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Entité ciblée (business, user, order, system, etc.)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Boutique concernée (optionnel)
    business_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Adresse IP de la requête
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Métadonnées structurées de l'action
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    actor_user: Mapped["User | None"] = relationship("User", foreign_keys=[actor_user_id], lazy="selectin")
    business: Mapped["Business | None"] = relationship("Business", foreign_keys=[business_id], lazy="selectin")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by={self.actor_user_id} on={self.resource_type}:{self.resource_id}>"

