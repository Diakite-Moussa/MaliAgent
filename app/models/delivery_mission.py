"""
DeliveryMission = Mission de livraison rattachée à une commande.
Sprint 9 (V2.0 Logistique & Flotte).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class MissionStatus(str, enum.Enum):
    PENDING = "pending"        # Course créée, en attente d'attribution
    ASSIGNED = "assigned"      # Attribuée à un livreur
    PICKED_UP = "picked_up"    # Colis récupéré chez le commerçant
    IN_TRANSIT = "in_transit"  # En cours d'acheminement vers le client
    DELIVERED = "delivered"    # Livré avec validation OTP
    FAILED = "failed"          # Échec de livraison (absent, refus)
    CANCELLED = "cancelled"    # Course annulée


class AssignmentType(str, enum.Enum):
    INTERNAL = "internal"  # Livreur interne de la boutique
    PARTNER = "partner"    # Partenaire logistique externe


class DeliveryMission(Base, UUIDPKMixin, BusinessScopedMixin, TimestampMixin):
    __tablename__ = "delivery_missions"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True
    )

    assignment_type: Mapped[AssignmentType] = mapped_column(
        Enum(AssignmentType, name="assignment_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AssignmentType.INTERNAL,
    )

    status: Mapped[MissionStatus] = mapped_column(
        Enum(MissionStatus, name="mission_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=MissionStatus.PENDING,
        index=True,
    )

    # Livreur interne (User avec rôle LIVREUR)
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )

    # Partenaire logistique externe (si assignment_type == PARTNER)
    partner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("delivery_partners.id"), nullable=True, index=True
    )

    # Zone de livraison facultative
    delivery_zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("delivery_zones.id"), nullable=True
    )

    # Adresses et contacts
    pickup_address: Mapped[str] = mapped_column(String(500), nullable=False)
    delivery_address: Mapped[str] = mapped_column(String(500), nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    customer_phone: Mapped[str] = mapped_column(String(50), nullable=False)

    # Sécurité & validation infalsifiable par code OTP
    otp_code: Mapped[str] = mapped_column(String(10), nullable=False)
    otp_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Géolocalisation en direct du livreur
    current_latitude: Mapped[Numeric | None] = mapped_column(Numeric(10, 7), nullable=True)
    current_longitude: Mapped[Numeric | None] = mapped_column(Numeric(10, 7), nullable=True)

    # Horodatages de passage
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    picked_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relations
    order = relationship("Order", lazy="selectin")
    driver = relationship("User", foreign_keys=[driver_id], lazy="selectin")
    partner = relationship("DeliveryPartner", foreign_keys=[partner_id], back_populates="missions", lazy="selectin")
    delivery_zone = relationship("DeliveryZone", foreign_keys=[delivery_zone_id], lazy="selectin")

    def __repr__(self) -> str:
        return f"<DeliveryMission {self.id} (status={self.status.value}, order={self.order_id})>"
