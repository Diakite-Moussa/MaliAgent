"""
Base déclarative SQLAlchemy + mixins communs.

Tout modèle métier (sauf Business lui-même) doit hériter de BusinessScopedMixin
en plus de Base, pour garantir l'isolation multi-tenant dès la définition du
modèle — pas ajoutée après coup. Voir cahier des charges, principe RB-003 /
RF-017 (isolation par business_id).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BusinessScopedMixin:
    """
    Ajoute business_id à tout modèle qui en hérite.

    Règle du projet : toute table contenant des données propres à un
    commerçant DOIT hériter de ce mixin. Ne jamais interroger ces tables
    sans filtrer par business_id — voir app/db/scoped_session.py (à
    créer avec la couche de requêtes, pour appliquer ce filtre
    automatiquement plutôt que de compter sur la discipline de chaque
    requête écrite à la main).
    """

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False, index=True
    )
