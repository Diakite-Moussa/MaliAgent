"""
Endpoints de gestion de la logistique et des missions de livraison pour le Dashboard commerçant.
Sprint 9 (V2.0 Logistique & Flotte).
"""

import logging
import re
import secrets
import urllib.parse
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.deps import get_current_business_id, get_current_driver
from app.core.security import hash_password
from app.db.session import async_session
from app.whatsapp.client import send_text_message

logger = logging.getLogger(__name__)
from app.models import (
    AssignmentType,
    Customer,
    DeliveryMission,
    DeliveryPartner,
    DeliveryZone,
    DriverType,
    MissionStatus,
    Order,
    OrderStatus,
    User,
    UserRole,
)

router = APIRouter(prefix="/api/delivery", tags=["Delivery & Logistics"])


def build_navigation_links(address: str, lat: float | None = None, lng: float | None = None) -> dict[str, str]:
    """Génère des URLs directes d'itinéraire Google Maps et Waze vers Bamako."""
    destination = f"{lat},{lng}" if lat is not None and lng is not None else f"{address}, Bamako, Mali"
    encoded_dest = urllib.parse.quote(destination)
    return {
        "google_maps": f"https://www.google.com/maps/dir/?api=1&destination={encoded_dest}",
        "waze": f"https://waze.com/ul?q={encoded_dest}&navigate=yes",
    }


def _serialize_mission(m: DeliveryMission, include_otp: bool = True) -> dict:
    """Sérialise une mission de livraison pour l'API REST de manière unifiée."""
    lat = float(m.current_latitude) if m.current_latitude is not None else None
    lng = float(m.current_longitude) if m.current_longitude is not None else None
    dest_lat = float(m.destination_latitude) if m.destination_latitude is not None else None
    dest_lng = float(m.destination_longitude) if m.destination_longitude is not None else None

    driver = getattr(m, "driver", None)
    partner = getattr(m, "partner", None)

    data = {
        "id": str(m.id),
        "order_id": str(m.order_id),
        "status": m.status.value,
        "assignment_type": m.assignment_type.value if m.assignment_type else None,
        "driver_id": str(m.driver_id) if m.driver_id else None,
        "driver_name": f"{driver.first_name} {driver.last_name}" if driver else None,
        "driver_phone": driver.phone_number if driver else None,
        "partner_id": str(m.partner_id) if m.partner_id else None,
        "partner_name": partner.name if partner else None,
        "pickup_address": m.pickup_address,
        "delivery_address": m.delivery_address,
        "customer_name": m.customer_name,
        "customer_phone": m.customer_phone,
        "otp_verified": m.otp_verified,
        "current_latitude": lat,
        "current_longitude": lng,
        "destination_latitude": dest_lat,
        "destination_longitude": dest_lng,
        "navigation": build_navigation_links(m.delivery_address, dest_lat, dest_lng),
        "assigned_at": m.assigned_at.isoformat() if m.assigned_at else None,
        "picked_up_at": m.picked_up_at.isoformat() if m.picked_up_at else None,
        "delivered_at": m.delivered_at.isoformat() if m.delivered_at else None,
        "notes": m.notes,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }
    if include_otp:
        data["otp_code"] = m.otp_code
    return data



# ================= SCHEMAS PYDANTIC =================


class CreateMissionRequest(BaseModel):
    order_id: uuid.UUID
    pickup_address: str | None = None
    delivery_address: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    delivery_zone_id: uuid.UUID | None = None
    assignment_type: Literal["internal", "partner"] = "internal"
    driver_id: uuid.UUID | None = None
    partner_id: uuid.UUID | None = None
    notes: str | None = None


class AssignMissionRequest(BaseModel):
    assignment_type: Literal["internal", "partner"]
    driver_id: uuid.UUID | None = None
    partner_id: uuid.UUID | None = None
    notes: str | None = None


class CreatePartnerRequest(BaseModel):
    name: str
    contact_name: str | None = None
    phone_number: str
    address: str | None = None
    notes: str | None = None


class LocationUpdateRequest(BaseModel):
    latitude: float
    longitude: float


class VerifyOtpRequest(BaseModel):
    otp_code: str


class DriverCreateIn(BaseModel):
    first_name: str
    last_name: str
    phone_number: str
    email: str | None = None
    password: str | None = None
    driver_type: Literal["internal", "partner"] = "internal"


class DriverUpdateIn(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone_number: str | None = None
    driver_type: Literal["internal", "partner"] | None = None
    is_available: bool | None = None
    is_active: bool | None = None


class DriverAvailabilityIn(BaseModel):
    is_available: bool


# ================= ENDPOINTS MISSIONS =================


@router.get("/missions")
async def list_missions(
    business_id: uuid.UUID = Depends(get_current_business_id),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Retourne la liste des missions de livraison de la boutique.
    Cloisonné strictement par business_id (Multi-Tenant).
    """
    async with async_session() as session:
        stmt = (
            select(DeliveryMission)
            .where(DeliveryMission.business_id == business_id)
            .order_by(DeliveryMission.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(DeliveryMission.status == status)

        missions = (await session.execute(stmt)).scalars().all()
        results = [_serialize_mission(m, include_otp=True) for m in missions]
        return {"missions": results, "total": len(results)}


@router.post("/missions", status_code=201)
async def create_mission(
    payload: CreateMissionRequest,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Crée une nouvelle mission de livraison pour une commande existante.
    Génère un code OTP secret de 6 chiffres pour la validation de livraison.
    """
    async with async_session() as session:
        # 1. Vérifier que la commande appartient bien à cette boutique
        stmt_order = select(Order).where(Order.id == payload.order_id, Order.business_id == business_id)
        order = (await session.execute(stmt_order)).scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Commande introuvable dans cette boutique")

        # Récupérer les infos client
        stmt_c = select(Customer).where(Customer.id == order.customer_id)
        customer = (await session.execute(stmt_c)).scalar_one_or_none()

        customer_phone = payload.customer_phone or (customer.whatsapp_phone_number if customer else "")
        customer_name = payload.customer_name or (customer.display_name if customer and customer.display_name else "Client")
        delivery_address = payload.delivery_address or (order.delivery_address or "Bamako")
        pickup_address = payload.pickup_address or "Boutique principale"

        # 2. Vérifier le livreur ou le partenaire si fourni
        assignment_type = AssignmentType(payload.assignment_type)
        status = MissionStatus.PENDING
        assigned_at = None

        if assignment_type == AssignmentType.INTERNAL and payload.driver_id:
            stmt_d = select(User).where(
                User.id == payload.driver_id,
                User.business_id == business_id,
                User.role == UserRole.LIVREUR,
            )
            driver = (await session.execute(stmt_d)).scalar_one_or_none()
            if not driver:
                raise HTTPException(status_code=400, detail="Livreur interne introuvable ou non assignable")
            status = MissionStatus.ASSIGNED
            assigned_at = datetime.now(timezone.utc)

        elif assignment_type == AssignmentType.PARTNER and payload.partner_id:
            stmt_p = select(DeliveryPartner).where(
                DeliveryPartner.id == payload.partner_id,
                DeliveryPartner.business_id == business_id,
                DeliveryPartner.active == True,
            )
            partner = (await session.execute(stmt_p)).scalar_one_or_none()
            if not partner:
                raise HTTPException(status_code=400, detail="Partenaire de livraison introuvable ou inactif")
            status = MissionStatus.ASSIGNED
            assigned_at = datetime.now(timezone.utc)

        # 3. Générer un code OTP secret aléatoire à 6 chiffres
        otp_code = f"{secrets.randbelow(900000) + 100000}"

        mission = DeliveryMission(
            business_id=business_id,
            order_id=payload.order_id,
            assignment_type=assignment_type,
            status=status,
            driver_id=payload.driver_id if assignment_type == AssignmentType.INTERNAL else None,
            partner_id=payload.partner_id if assignment_type == AssignmentType.PARTNER else None,
            delivery_zone_id=payload.delivery_zone_id,
            pickup_address=pickup_address,
            delivery_address=delivery_address,
            destination_latitude=order.delivery_latitude,
            destination_longitude=order.delivery_longitude,
            customer_name=customer_name,
            customer_phone=customer_phone,
            otp_code=otp_code,
            otp_verified=False,
            assigned_at=assigned_at,
            notes=payload.notes,
        )
        session.add(mission)
        await session.commit()
        await session.refresh(mission)

        if mission.driver_id and driver and driver.phone_number:
            try:
                msg_driver = (
                    f"🛵 *MaliAgent — Nouvelle course assignée !*\n\n"
                    f"• Commande : `#{str(mission.order_id)[:8]}`\n"
                    f"• Retrait : {mission.pickup_address or 'Boutique'}\n"
                    f"• Destination : {mission.delivery_address}\n"
                    f"• Client : {mission.customer_name or 'Client'} ({mission.customer_phone or 'N/A'})\n\n"
                    f"👉 Ouvrez votre cockpit coursier pour démarrer :\n"
                    f"{settings.public_base_url}/driver"
                )
                await send_text_message(to=driver.phone_number, body=msg_driver)
            except Exception as e:
                logger.warning(f"Notification WhatsApp coursier échouée: {e}")

        return {
            "id": str(mission.id),
            "order_id": str(mission.order_id),
            "status": mission.status.value,
            "assignment_type": mission.assignment_type.value,
            "otp_code": mission.otp_code,
            "pickup_address": mission.pickup_address,
            "delivery_address": mission.delivery_address,
            "customer_phone": mission.customer_phone,
            "message": "Mission de livraison créée avec succès",
        }


@router.get("/missions/{mission_id}")
async def get_mission_detail(
    mission_id: uuid.UUID,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Retourne le détail d'une mission de livraison.
    """
    async with async_session() as session:
        stmt = (
            select(DeliveryMission)
            .where(DeliveryMission.id == mission_id, DeliveryMission.business_id == business_id)
        )
        mission = (await session.execute(stmt)).scalar_one_or_none()
        if not mission:
            raise HTTPException(status_code=404, detail="Mission de livraison introuvable")

        return _serialize_mission(mission, include_otp=True)


@router.patch("/missions/{mission_id}/assign")
async def assign_mission(
    mission_id: uuid.UUID,
    payload: AssignMissionRequest,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Attribue ou réattribue une mission à un livreur interne ou un partenaire.
    """
    async with async_session() as session:
        stmt = select(DeliveryMission).where(
            DeliveryMission.id == mission_id, DeliveryMission.business_id == business_id
        )
        mission = (await session.execute(stmt)).scalar_one_or_none()
        if not mission:
            raise HTTPException(status_code=404, detail="Mission introuvable")

        assignment_type = AssignmentType(payload.assignment_type)

        if assignment_type == AssignmentType.INTERNAL:
            if not payload.driver_id:
                raise HTTPException(status_code=400, detail="driver_id obligatoire pour une attribution interne")
            stmt_d = select(User).where(
                User.id == payload.driver_id,
                User.business_id == business_id,
                User.role == UserRole.LIVREUR,
            )
            driver = (await session.execute(stmt_d)).scalar_one_or_none()
            if not driver:
                raise HTTPException(status_code=400, detail="Livreur interne introuvable ou non assignable")

            mission.assignment_type = AssignmentType.INTERNAL
            mission.driver_id = payload.driver_id
            mission.partner_id = None
        else:
            if not payload.partner_id:
                raise HTTPException(status_code=400, detail="partner_id obligatoire pour un partenaire externe")
            stmt_p = select(DeliveryPartner).where(
                DeliveryPartner.id == payload.partner_id,
                DeliveryPartner.business_id == business_id,
                DeliveryPartner.active == True,
            )
            partner = (await session.execute(stmt_p)).scalar_one_or_none()
            if not partner:
                raise HTTPException(status_code=400, detail="Partenaire introuvable ou inactif")

            mission.assignment_type = AssignmentType.PARTNER
            mission.partner_id = payload.partner_id
            mission.driver_id = None

        mission.status = MissionStatus.ASSIGNED
        mission.assigned_at = datetime.now(timezone.utc)
        if payload.notes:
            mission.notes = payload.notes

        await session.commit()
        await session.refresh(mission)

        if mission.driver_id and payload.driver_id and driver and driver.phone_number:
            try:
                msg_driver = (
                    f"🛵 *MaliAgent — Course #{str(mission.id)[:8]} assignée !*\n\n"
                    f"• Commande : `#{str(mission.order_id)[:8]}`\n"
                    f"• Destination : {mission.delivery_address}\n"
                    f"• Client : {mission.customer_name or 'Client'} ({mission.customer_phone or 'N/A'})\n\n"
                    f"👉 Accédez à votre cockpit coursier :\n"
                    f"{settings.public_base_url}/driver"
                )
                await send_text_message(to=driver.phone_number, body=msg_driver)
            except Exception as e:
                logger.warning(f"Notification WhatsApp coursier échouée: {e}")

        return {
            "id": str(mission.id),
            "status": mission.status.value,
            "assignment_type": mission.assignment_type.value,
            "driver_id": str(mission.driver_id) if mission.driver_id else None,
            "partner_id": str(mission.partner_id) if mission.partner_id else None,
            "message": "Mission attribuée avec succès",
        }


# ================= ENDPOINTS LIVREURS & PARTENAIRES =================


@router.get("/drivers")
async def list_drivers(
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Retourne la liste des livreurs internes de la boutique.
    """
    async with async_session() as session:
        stmt = (
            select(User)
            .where(
                User.business_id == business_id,
                User.role == UserRole.LIVREUR,
                User.is_active == True,
            )
            .order_by(User.first_name.asc())
        )
        drivers = (await session.execute(stmt)).scalars().all()

        return [
            {
                "id": str(d.id),
                "name": f"{d.first_name} {d.last_name}",
                "first_name": d.first_name,
                "last_name": d.last_name,
                "email": d.email,
                "phone_number": d.phone_number,
                "driver_type": d.driver_type.value if d.driver_type else "internal",
                "is_available": d.is_available,
            }
            for d in drivers
        ]


@router.post("/drivers", status_code=201)
async def create_driver(
    payload: DriverCreateIn,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Crée un nouveau livreur rattaché à la boutique avec son compte d'accès.
    """
    clean_first = payload.first_name.strip()
    clean_last = payload.last_name.strip()
    clean_phone = re.sub(r"[^0-9+]", "", payload.phone_number.strip())

    if not clean_first or not clean_last:
        raise HTTPException(status_code=400, detail="Le prénom et le nom sont obligatoires")
    if not clean_phone:
        raise HTTPException(status_code=400, detail="Le numéro de téléphone est obligatoire")

    phone_digits = re.sub(r"[^0-9]", "", clean_phone)[-8:]
    biz_suffix = str(business_id)[:4]
    clean_email = payload.email.strip().lower() if (payload.email and payload.email.strip()) else None
    clean_password = payload.password.strip() if (payload.password and payload.password.strip()) else None
    driver_email = clean_email or f"coursier.{phone_digits}.{biz_suffix}@maliagent.ml"
    driver_password = clean_password or "MaliCoursier2026!"

    async with async_session() as session:
        existing = (await session.execute(select(User).where(User.email == driver_email))).scalar_one_or_none()
        if existing:
            if not clean_email:
                driver_email = f"coursier.{phone_digits}.{secrets.token_hex(3)}@maliagent.ml"
            else:
                raise HTTPException(status_code=400, detail=f"Un compte avec l'email {driver_email} existe déjà.")

        driver_type = DriverType.INTERNAL if payload.driver_type == "internal" else DriverType.PARTNER

        new_driver = User(
            business_id=business_id,
            first_name=clean_first,
            last_name=clean_last,
            email=driver_email,
            password_hash=hash_password(driver_password),
            phone_number=clean_phone,
            role=UserRole.LIVREUR,
            driver_type=driver_type,
            is_available=True,
            is_active=True,
        )
        session.add(new_driver)
        await session.commit()
        await session.refresh(new_driver)

        return {
            "id": str(new_driver.id),
            "name": f"{new_driver.first_name} {new_driver.last_name}",
            "first_name": new_driver.first_name,
            "last_name": new_driver.last_name,
            "email": new_driver.email,
            "phone_number": new_driver.phone_number,
            "driver_type": new_driver.driver_type.value if new_driver.driver_type else "internal",
            "is_available": new_driver.is_available,
            "initial_password": driver_password,
            "message": "Livreur créé avec succès",
        }


@router.get("/fleet/drivers")
async def list_fleet_drivers(business_id: uuid.UUID = Depends(get_current_business_id)):
    return await list_drivers(business_id=business_id)


@router.post("/fleet/drivers", status_code=201)
async def create_fleet_driver(payload: DriverCreateIn, business_id: uuid.UUID = Depends(get_current_business_id)):
    return await create_driver(payload=payload, business_id=business_id)


@router.patch("/drivers/{driver_id}")
async def update_driver(
    driver_id: uuid.UUID,
    payload: DriverUpdateIn,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Modifie les informations d'un livreur ou sa disponibilité depuis le cockpit commerçant.
    """
    async with async_session() as session:
        stmt = select(User).where(
            User.id == driver_id,
            User.business_id == business_id,
            User.role == UserRole.LIVREUR,
        )
        driver = (await session.execute(stmt)).scalar_one_or_none()
        if not driver:
            raise HTTPException(status_code=404, detail="Livreur introuvable pour cette boutique")

        if payload.first_name is not None:
            driver.first_name = payload.first_name.strip()
        if payload.last_name is not None:
            driver.last_name = payload.last_name.strip()
        if payload.phone_number is not None:
            driver.phone_number = payload.phone_number.strip()
        if payload.driver_type is not None:
            driver.driver_type = DriverType.INTERNAL if payload.driver_type == "internal" else DriverType.PARTNER
        if payload.is_available is not None:
            driver.is_available = payload.is_available
        if payload.is_active is not None:
            driver.is_active = payload.is_active

        await session.commit()
        await session.refresh(driver)

        return {
            "id": str(driver.id),
            "name": f"{driver.first_name} {driver.last_name}",
            "first_name": driver.first_name,
            "last_name": driver.last_name,
            "email": driver.email,
            "phone_number": driver.phone_number,
            "driver_type": driver.driver_type.value if driver.driver_type else "internal",
            "is_available": driver.is_available,
            "is_active": driver.is_active,
            "message": "Livreur mis à jour avec succès",
        }


@router.delete("/drivers/{driver_id}")
async def delete_driver(
    driver_id: uuid.UUID,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Désactive un livreur de la flotte boutique (soft delete).
    """
    async with async_session() as session:
        stmt = select(User).where(
            User.id == driver_id,
            User.business_id == business_id,
            User.role == UserRole.LIVREUR,
        )
        driver = (await session.execute(stmt)).scalar_one_or_none()
        if not driver:
            raise HTTPException(status_code=404, detail="Livreur introuvable pour cette boutique")

        driver.is_active = False
        driver.is_available = False
        await session.commit()

        return {"status": "deleted", "id": str(driver_id), "message": "Livreur désactivé de la flotte"}


@router.get("/partners")
async def list_partners(
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Retourne la liste des flottes et partenaires logistiques de la boutique.
    """
    async with async_session() as session:
        stmt = (
            select(DeliveryPartner)
            .where(DeliveryPartner.business_id == business_id)
            .order_by(DeliveryPartner.name.asc())
        )
        partners = (await session.execute(stmt)).scalars().all()

        return [
            {
                "id": str(p.id),
                "name": p.name,
                "contact_name": p.contact_name,
                "phone_number": p.phone_number,
                "address": p.address,
                "active": p.active,
                "notes": p.notes,
            }
            for p in partners
        ]


@router.post("/partners", status_code=201)
async def create_partner(
    payload: CreatePartnerRequest,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """
    Enregistre un nouveau partenaire de livraison pour la boutique.
    """
    clean_name = payload.name.strip()
    clean_phone = re.sub(r"[^0-9+]", "", payload.phone_number.strip())
    if not clean_name:
        raise HTTPException(status_code=400, detail="Le nom du partenaire est obligatoire")
    if not clean_phone:
        raise HTTPException(status_code=400, detail="Le numéro de téléphone est obligatoire")

    async with async_session() as session:
        partner = DeliveryPartner(
            business_id=business_id,
            name=clean_name,
            contact_name=payload.contact_name.strip() if payload.contact_name else None,
            phone_number=clean_phone,
            address=payload.address.strip() if payload.address else None,
            notes=payload.notes.strip() if payload.notes else None,
            active=True,
        )
        session.add(partner)
        await session.commit()
        await session.refresh(partner)

        return {
            "id": str(partner.id),
            "name": partner.name,
            "phone_number": partner.phone_number,
            "contact_name": partner.contact_name,
            "message": "Partenaire de livraison enregistré avec succès",
        }


@router.get("/fleet/partners")
async def list_fleet_partners(business_id: uuid.UUID = Depends(get_current_business_id)):
    return await list_partners(business_id=business_id)


@router.post("/fleet/partners", status_code=201)
async def create_fleet_partner(payload: CreatePartnerRequest, business_id: uuid.UUID = Depends(get_current_business_id)):
    return await create_partner(payload=payload, business_id=business_id)


# ================= ENDPOINTS LIVREUR MOBILE (SPRINT 10) =================


@router.get("/driver/missions")
async def list_driver_missions(
    driver: User = Depends(get_current_driver),
    status: str | None = Query(None),
):
    """
    Retourne les missions assignées au livreur connecté.
    Intègre les liens de navigation GPS 1-clic (Google Maps / Waze).
    """
    async with async_session() as session:
        stmt = (
            select(DeliveryMission)
            .where(
                DeliveryMission.driver_id == driver.id,
                DeliveryMission.business_id == driver.business_id,
            )
            .order_by(DeliveryMission.created_at.desc())
        )
        if status:
            stmt = stmt.where(DeliveryMission.status == status)

        missions = (await session.execute(stmt)).scalars().all()
        results = [_serialize_mission(m, include_otp=False) for m in missions]
        return {"missions": results, "total": len(results)}


@router.post("/driver/missions/{mission_id}/accept")
async def driver_accept_mission(
    mission_id: uuid.UUID,
    driver: User = Depends(get_current_driver),
):
    """
    Le livreur accepte formellement la mission qui lui est confiée.
    """
    async with async_session() as session:
        stmt = select(DeliveryMission).where(
            DeliveryMission.id == mission_id,
            DeliveryMission.driver_id == driver.id,
        )
        mission = (await session.execute(stmt)).scalar_one_or_none()
        if not mission:
            raise HTTPException(status_code=404, detail="Mission introuvable pour ce livreur")

        mission.status = MissionStatus.ASSIGNED
        await session.commit()
        return {"id": str(mission.id), "status": mission.status.value, "message": "Mission acceptée"}


@router.post("/driver/missions/{mission_id}/pickup")
async def driver_pickup_parcel(
    mission_id: uuid.UUID,
    driver: User = Depends(get_current_driver),
):
    """
    Le livreur confirme la récupération du colis chez le commerçant.
    """
    async with async_session() as session:
        stmt = select(DeliveryMission).where(
            DeliveryMission.id == mission_id,
            DeliveryMission.driver_id == driver.id,
        )
        mission = (await session.execute(stmt)).scalar_one_or_none()
        if not mission:
            raise HTTPException(status_code=404, detail="Mission introuvable pour ce livreur")

        mission.status = MissionStatus.PICKED_UP
        mission.picked_up_at = datetime.now(timezone.utc)
        await session.commit()
        return {
            "id": str(mission.id),
            "status": mission.status.value,
            "picked_up_at": mission.picked_up_at.isoformat(),
            "message": "Colis récupéré en boutique",
        }


@router.post("/driver/missions/{mission_id}/start-route")
async def driver_start_route(
    mission_id: uuid.UUID,
    driver: User = Depends(get_current_driver),
):
    """
    Le livreur signale son départ en route vers l'adresse du client.
    Envoie une notification WhatsApp automatique au client avec lien de tracking en direct et code secret OTP.
    """
    async with async_session() as session:
        stmt = select(DeliveryMission).where(
            DeliveryMission.id == mission_id,
            DeliveryMission.driver_id == driver.id,
        )
        mission = (await session.execute(stmt)).scalar_one_or_none()
        if not mission:
            raise HTTPException(status_code=404, detail="Mission introuvable pour ce livreur")

        mission.status = MissionStatus.IN_TRANSIT
        await session.commit()

        # Notification WhatsApp automatique vers le client
        raw_phone = (mission.customer_phone or "").strip().lstrip("+").replace(" ", "")
        if raw_phone:
            base_url = getattr(settings, "public_base_url", "http://localhost:8000")
            tracking_url = f"{base_url}/api/delivery/track/{mission.order_id}"
            body_msg = (
                f"🛵 *MaliAgent Livraison en cours*\n\n"
                f"Bonjour {mission.customer_name or 'cher client'},\n"
                f"Votre livreur ({driver.first_name} {driver.last_name}) est en route avec votre commande !\n\n"
                f"📍 *Suivre votre livraison en direct* :\n{tracking_url}\n\n"
                f"🔐 *Votre code secret de réception* : *{mission.otp_code}*\n"
                f"(Communiquez ce code au livreur uniquement lorsque vous recevez le colis)."
            )
            try:
                from app.whatsapp.client import send_text_message

                await send_text_message(to=raw_phone, body=body_msg)
            except Exception as e:
                logger.warning(f"Impossible d'envoyer la notification WhatsApp de livraison: {e}")

        return {
            "id": str(mission.id),
            "status": mission.status.value,
            "message": "Course en route vers le client",
        }


@router.post("/driver/missions/{mission_id}/location")
async def driver_update_location(
    mission_id: uuid.UUID,
    payload: LocationUpdateRequest,
    driver: User = Depends(get_current_driver),
):
    """
    Met à jour la position GPS en direct du livreur sur le terrain.
    """
    async with async_session() as session:
        stmt = select(DeliveryMission).where(
            DeliveryMission.id == mission_id,
            DeliveryMission.driver_id == driver.id,
        )
        mission = (await session.execute(stmt)).scalar_one_or_none()
        if not mission:
            raise HTTPException(status_code=404, detail="Mission introuvable pour ce livreur")

        mission.current_latitude = payload.latitude
        mission.current_longitude = payload.longitude
        await session.commit()

        return {
            "id": str(mission.id),
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "message": "Position GPS mise à jour",
        }


@router.post("/driver/missions/{mission_id}/verify-otp")
async def driver_verify_otp(
    mission_id: uuid.UUID,
    payload: VerifyOtpRequest,
    driver: User = Depends(get_current_driver),
):
    """
    Valide la livraison par le code secret OTP communiqué par le client.
    Met à jour la mission en 'delivered' et synchronise la commande.
    """
    async with async_session() as session:
        stmt = select(DeliveryMission).where(
            DeliveryMission.id == mission_id,
            DeliveryMission.driver_id == driver.id,
        )
        mission = (await session.execute(stmt)).scalar_one_or_none()
        if not mission:
            raise HTTPException(status_code=404, detail="Mission introuvable pour ce livreur")

        if mission.otp_code.strip() != payload.otp_code.strip():
            raise HTTPException(
                status_code=400,
                detail="Code OTP invalide. Veuillez redemander le code secret à 6 chiffres au client.",
            )

        # Validation réussie
        mission.status = MissionStatus.DELIVERED
        mission.otp_verified = True
        mission.delivered_at = datetime.now(timezone.utc)

        # Mettre à jour également le statut de la commande associée
        stmt_order = select(Order).where(Order.id == mission.order_id)
        order = (await session.execute(stmt_order)).scalar_one_or_none()
        if order:
            order.status = OrderStatus.DELIVERED

        await session.commit()
        return {
            "id": str(mission.id),
            "order_id": str(mission.order_id),
            "status": mission.status.value,
            "otp_verified": True,
            "delivered_at": mission.delivered_at.isoformat(),
            "message": "Livraison validée avec succès par OTP client",
        }


@router.patch("/driver/availability")
async def driver_toggle_availability(
    payload: DriverAvailabilityIn,
    driver: User = Depends(get_current_driver),
):
    """
    Permet au livreur connecté de basculer son statut En service / En pause en temps réel.
    """
    async with async_session() as session:
        stmt = select(User).where(User.id == driver.id)
        db_driver = (await session.execute(stmt)).scalar_one_or_none()
        if not db_driver:
            raise HTTPException(status_code=404, detail="Livreur introuvable")

        db_driver.is_available = payload.is_available
        await session.commit()
        await session.refresh(db_driver)

        return {
            "status": "updated",
            "is_available": db_driver.is_available,
            "message": "Statut de disponibilité mis à jour avec succès",
        }


@router.get("/driver/summary")
async def driver_get_summary(
    driver: User = Depends(get_current_driver),
):
    """
    Retourne le récapitulatif journalier du coursier :
    - Nombre de livraisons réussies
    - Total espèces encaissé (Cash on delivery) à restituer à la boutique
    - Nombre de courses actives
    - Statut de disponibilité actuel
    """
    async with async_session() as session:
        stmt_m = (
            select(DeliveryMission)
            .where(
                DeliveryMission.driver_id == driver.id,
                DeliveryMission.business_id == driver.business_id,
            )
            .options(selectinload(DeliveryMission.order))
        )
        missions = (await session.execute(stmt_m)).scalars().all()

        delivered_missions = [m for m in missions if m.status == MissionStatus.DELIVERED]
        active_missions = [
            m for m in missions if m.status not in (MissionStatus.DELIVERED, MissionStatus.CANCELLED, MissionStatus.FAILED)
        ]

        total_cash = 0
        for m in delivered_missions:
            if m.order and (m.order.payment_method or "").lower() in (
                "cash",
                "cash_on_delivery",
                "especes",
                "espèces",
                "mock",
            ):
                total_cash += int(m.order.total_amount or 0)

        return {
            "driver_name": f"{driver.first_name} {driver.last_name}",
            "driver_phone": driver.phone_number,
            "is_available": driver.is_available,
            "total_delivered_count": len(delivered_missions),
            "total_cash_collected": total_cash,
            "active_missions_count": len(active_missions),
        }


# ================= PAGE PUBLIQUE DE SUIVI CLIENT WHATSAPP =================


@router.get("/track/{order_id}")
async def public_track_delivery(
    order_id: uuid.UUID,
    accept: str | None = Header(None),
    format: str | None = Query(None),
):
    """
    Page publique de suivi en direct pour le client final WhatsApp.
    Accessible sans authentification via le lien envoyé dans la conversation.
    """
    async with async_session() as session:
        stmt = (
            select(DeliveryMission)
            .where(DeliveryMission.order_id == order_id)
            .order_by(DeliveryMission.created_at.desc())
        )
        mission = (await session.execute(stmt)).scalars().first()
        if not mission:
            raise HTTPException(status_code=404, detail="Aucun suivi de livraison disponible pour cette commande")

        driver_name = f"{mission.driver.first_name} {mission.driver.last_name}" if mission.driver else "Livreur assigné"
        driver_phone = mission.driver.phone_number if mission.driver else None

        # Si le client demande du JSON
        if format == "json" or (accept and "application/json" in accept):
            return {
                "order_id": str(mission.order_id),
                "status": mission.status.value,
                "pickup_address": mission.pickup_address,
                "delivery_address": mission.delivery_address,
                "driver_name": driver_name,
                "driver_phone": driver_phone,
                "assigned_at": mission.assigned_at.isoformat() if mission.assigned_at else None,
                "picked_up_at": mission.picked_up_at.isoformat() if mission.picked_up_at else None,
                "delivered_at": mission.delivered_at.isoformat() if mission.delivered_at else None,
                "otp_verified": mission.otp_verified,
            }

        # Statuts lisibles et étapes de progression
        status_labels = {
            "pending": "En attente de prise en charge",
            "assigned": "Livreur assigné",
            "picked_up": "Colis récupéré en boutique",
            "in_transit": "En cours d'acheminement vers vous",
            "delivered": "Colis livré avec succès 🎉",
            "failed": "Livraison reportée",
            "cancelled": "Course annulée",
        }
        current_label = status_labels.get(mission.status.value, mission.status.value)

        # Calcul des étapes
        steps = [
            {"title": "Commande enregistrée", "done": True},
            {"title": "Livreur en route vers la boutique", "done": mission.status.value in ["assigned", "picked_up", "in_transit", "delivered"]},
            {"title": "Colis récupéré chez le commerçant", "done": mission.status.value in ["picked_up", "in_transit", "delivered"]},
            {"title": "En route vers votre adresse", "done": mission.status.value in ["in_transit", "delivered"]},
            {"title": "Colis remis en main propre", "done": mission.status.value == "delivered"},
        ]

        steps_html = "".join([
            f"""
            <div style="display:flex;align-items:center;margin-bottom:16px;">
                <div style="width:28px;height:28px;border-radius:50%;background:{'#10b981' if s['done'] else '#334155'};display:flex;align-items:center;justify-content:center;color:#ffffff;font-size:14px;margin-right:14px;font-weight:bold;">
                    {'✓' if s['done'] else '•'}
                </div>
                <div style="font-size:15px;color:{'#f8fafc' if s['done'] else '#94a3b8'};font-weight:{'600' if s['done'] else '400'};">
                    {s['title']}
                </div>
            </div>
            """
            for s in steps
        ])

        driver_contact_html = ""
        if driver_phone:
            driver_contact_html = f"""
            <a href="tel:{driver_phone}" style="display:inline-flex;align-items:center;justify-content:center;width:100%;padding:14px;background:#10b981;color:#ffffff;text-decoration:none;border-radius:12px;font-weight:700;font-size:16px;box-shadow:0 4px 14px rgba(16,185,129,0.3);margin-top:16px;">
                📞 Appeler le livreur ({driver_phone})
            </a>
            """

        html_content = f"""
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Suivi de Livraison — MaliAgent</title>
            <style>
                body {{
                    margin: 0;
                    padding: 20px;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    background: #0f172a;
                    color: #f8fafc;
                    display: flex;
                    justify-content: center;
                }}
                .container {{
                    max-width: 480px;
                    width: 100%;
                }}
                .card {{
                    background: rgba(30, 41, 59, 0.85);
                    backdrop-filter: blur(12px);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 20px;
                    padding: 24px;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
                    margin-bottom: 20px;
                }}
                .badge {{
                    display: inline-block;
                    padding: 6px 14px;
                    border-radius: 9999px;
                    background: rgba(16, 185, 129, 0.15);
                    color: #34d399;
                    font-weight: 700;
                    font-size: 13px;
                    border: 1px solid rgba(16, 185, 129, 0.3);
                    margin-bottom: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div style="text-align:center;margin-bottom:24px;">
                    <h2 style="margin:0;color:#10b981;font-size:24px;">🇲🇱 MaliAgent Livraison</h2>
                    <p style="margin:6px 0 0 0;color:#94a3b8;font-size:14px;">Suivi en direct de votre commande #{str(order_id)[:8]}</p>
                </div>

                <div class="card">
                    <span class="badge">{current_label}</span>
                    <h3 style="margin:0 0 8px 0;font-size:18px;">Destination : {mission.delivery_address}</h3>
                    <p style="margin:0;color:#94a3b8;font-size:14px;">Client : {mission.customer_name or 'Client'} ({mission.customer_phone})</p>
                </div>

                <div class="card">
                    <h4 style="margin:0 0 18px 0;color:#cbd5e1;font-size:16px;">Progression de la course</h4>
                    {steps_html}
                </div>

                <div class="card">
                    <h4 style="margin:0 0 8px 0;color:#cbd5e1;font-size:16px;">Votre Livreur</h4>
                    <p style="margin:0 0 4px 0;font-weight:600;font-size:17px;color:#f8fafc;">{driver_name}</p>
                    <p style="margin:0;color:#94a3b8;font-size:14px;">Livraison officielle certifiée par MaliAgent</p>
                    {driver_contact_html}
                </div>

                <div style="text-align:center;color:#64748b;font-size:12px;margin-top:20px;">
                    MaliAgent Logistics Platform &bull; Bamako, Mali
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

