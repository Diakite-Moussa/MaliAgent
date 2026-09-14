"""
User = un utilisateur du dashboard (section 13.2 du cahier des charges).

Peut être :
- Un membre d'une boutique (rôle admin, vendeur, operateur rattaché à un business_id).
- Le propriétaire de la plateforme SaaS (rôle super_admin, avec business_id=None).

Le client final (sur WhatsApp) n'a jamais de compte User — voir Customer.
"""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"  # Propriétaire de la plateforme SaaS (Section 6.3)
    ADMIN = "admin"              # Commerçant propriétaire de sa boutique
    VENDEUR = "vendeur"          # Vendeur / gestionnaire catalogue
    OPERATEUR = "operateur"      # Opérateur support / SAV WhatsApp
    LIVREUR = "livreur"          # Livreur flotte / logistique (Sprint 9 - V2.0)


class DriverType(str, enum.Enum):
    INTERNAL = "internal"  # Livreur employé direct de la boutique
    PARTNER = "partner"    # Livreur d'une agence partenaire


class User(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False, default=UserRole.ADMIN
    )
    is_active: Mapped[bool] = mapped_column(default=True)

    # Champs optionnels spécifiques au rôle LIVREUR (Sprint 9 - V2.0)
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    driver_type: Mapped[DriverType | None] = mapped_column(
        Enum(DriverType, name="driver_type", values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    is_available: Mapped[bool] = mapped_column(default=True)

    # business_id est NULL uniquement pour le SUPER_ADMIN de la plateforme.
    # Pour tout autre rôle commerçant, il est obligatoire.
    business_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=True, index=True
    )

    business = relationship("Business", foreign_keys=[business_id], lazy="selectin")

    def __repr__(self) -> str:
        return f"<User {self.email!r} ({self.role.value}, biz={self.business_id})>"
