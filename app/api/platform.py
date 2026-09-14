"""
Endpoints réservés au Super Administrateur / Propriétaire de la plateforme SaaS MaliAgent.
Section 6.3 du cahier des charges fonctionnel.
"""

import uuid
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_super_admin
from app.core.security import create_access_token, hash_password
from app.db.session import async_session
from app.models import AuditLog, Business, Conversation, Customer, Order, OrderStatus, Product, User, UserRole
from app.services.audit import record_audit_log

router = APIRouter(prefix="/api/platform", tags=["Platform Super Admin"])


# ================= SCHEMAS =================

class BusinessCreate(BaseModel):
    name: str
    whatsapp_phone_number: str
    currency: str = "XOF"


class BusinessUpdate(BaseModel):
    name: str | None = None
    whatsapp_phone_number: str | None = None
    is_active: bool | None = None


class UserCreatePlatform(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    role: Literal["super_admin", "admin", "vendeur", "operateur"] = "admin"
    business_id: str | None = None


class UserUpdatePlatform(BaseModel):
    is_active: bool | None = None
    role: Literal["super_admin", "admin", "vendeur", "operateur"] | None = None


# ================= 1. STATISTIQUES GLOBALES SAAS =================

@router.get("/stats")
async def get_platform_stats(_: User = Depends(get_current_super_admin)):
    """Retourne la télémétrie et les KPIs agrégés sur toute la plateforme SaaS."""
    async with async_session() as session:
        total_biz = (await session.execute(select(func.count(Business.id)))).scalar_one()
        active_biz = (
            await session.execute(select(func.count(Business.id)).where(Business.is_active.is_(True)))
        ).scalar_one()

        total_orders = (await session.execute(select(func.count(Order.id)))).scalar_one()

        # Somme du GMV : total_items_price + delivery_fee pour les commandes non annulées
        valid_orders = (
            await session.execute(
                select(Order).where(Order.status != OrderStatus.CANCELLED)
            )
        ).scalars().all()
        total_gmv = sum(o.total_amount for o in valid_orders)

        total_customers = (await session.execute(select(func.count(Customer.id)))).scalar_one()
        total_conversations = (await session.execute(select(func.count(Conversation.id)))).scalar_one()
        total_handoffs = (
            await session.execute(
                select(func.count(Conversation.id)).where(Conversation.status == "needs_human")
            )
        ).scalar_one()

        total_users = (await session.execute(select(func.count(User.id)))).scalar_one()

        return {
            "businesses": {
                "total": total_biz,
                "active": active_biz,
                "suspended": total_biz - active_biz,
            },
            "orders": {
                "total_count": total_orders,
                "total_gmv_fcfa": int(total_gmv),
            },
            "engagement": {
                "total_customers": total_customers,
                "total_conversations": total_conversations,
                "total_handoffs": total_handoffs,
            },
            "users_count": total_users,
        }


# ================= 2. GESTION DES ENTREPRISES =================

@router.get("/businesses")
async def list_businesses(
    page: int = 1,
    page_size: int = 50,
    _: User = Depends(get_current_super_admin),
):
    """Liste toutes les boutiques clientes avec leurs métriques individuelles (paginée)."""
    offset = max(0, (page - 1) * page_size)
    async with async_session() as session:
        stmt = select(Business).order_by(Business.created_at.desc()).offset(offset).limit(page_size)
        businesses = (await session.execute(stmt)).scalars().all()

        results = []
        for biz in businesses:
            orders = (
                await session.execute(
                    select(Order).where(Order.business_id == biz.id, Order.status != OrderStatus.CANCELLED)
                )
            ).scalars().all()
            revenue = sum(o.total_amount for o in orders)

            prods_count = (
                await session.execute(
                    select(func.count(Product.id)).where(Product.business_id == biz.id)
                )
            ).scalar_one()

            users_count = (
                await session.execute(
                    select(func.count(User.id)).where(User.business_id == biz.id)
                )
            ).scalar_one()

            results.append({
                "id": str(biz.id),
                "name": biz.name,
                "whatsapp_phone_number": biz.whatsapp_phone_number,
                "currency": biz.currency,
                "is_active": biz.is_active,
                "created_at": biz.created_at.isoformat() if biz.created_at else None,
                "orders_count": len(orders),
                "total_revenue": int(revenue),
                "products_count": prods_count,
                "users_count": users_count,
            })

        return results


@router.post("/businesses", status_code=201)
async def create_business(
    payload: BusinessCreate,
    request: Request,
    current_admin: User = Depends(get_current_super_admin),
):
    """Permet au Super Admin de provisionner une nouvelle entreprise cliente."""
    clean_phone = payload.whatsapp_phone_number.strip().replace("+", "").replace(" ", "")
    async with async_session() as session:
        # Vérifier l'unicité du numéro WhatsApp
        existing = (
            await session.execute(
                select(Business).where(Business.whatsapp_phone_number == clean_phone)
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Une boutique utilise déjà le numéro WhatsApp {clean_phone}",
            )

        biz = Business(
            name=payload.name.strip(),
            whatsapp_phone_number=clean_phone,
            currency=payload.currency.upper(),
            is_active=True,
        )
        session.add(biz)
        await session.flush()

        # Enregistrement dans le journal d'audit
        await record_audit_log(
            session=session,
            actor_user_id=current_admin.id,
            action="CREATE_BUSINESS",
            resource_type="business",
            resource_id=str(biz.id),
            business_id=biz.id,
            ip_address=request.client.host if request.client else None,
            details={"name": biz.name, "whatsapp_phone_number": biz.whatsapp_phone_number},
        )

        await session.commit()
        await session.refresh(biz)

        return {
            "id": str(biz.id),
            "name": biz.name,
            "whatsapp_phone_number": biz.whatsapp_phone_number,
            "currency": biz.currency,
            "is_active": biz.is_active,
        }


@router.patch("/businesses/{business_id}")
async def update_business(
    business_id: uuid.UUID,
    payload: BusinessUpdate,
    request: Request,
    current_admin: User = Depends(get_current_super_admin),
):
    """Met à jour une entreprise : activation/suspension, nom, numéro."""
    async with async_session() as session:
        biz = (
            await session.execute(select(Business).where(Business.id == business_id))
        ).scalar_one_or_none()
        if not biz:
            raise HTTPException(status_code=404, detail="Boutique introuvable")

        audit_action = "UPDATE_BUSINESS"
        if payload.is_active is False and biz.is_active is True:
            audit_action = "SUSPEND_BUSINESS"
        elif payload.is_active is True and biz.is_active is False:
            audit_action = "ACTIVATE_BUSINESS"

        if payload.name is not None:
            biz.name = payload.name.strip()
        if payload.is_active is not None:
            biz.is_active = payload.is_active
        if payload.whatsapp_phone_number is not None:
            clean_phone = payload.whatsapp_phone_number.strip().replace("+", "").replace(" ", "")
            biz.whatsapp_phone_number = clean_phone

        await record_audit_log(
            session=session,
            actor_user_id=current_admin.id,
            action=audit_action,
            resource_type="business",
            resource_id=str(biz.id),
            business_id=biz.id,
            ip_address=request.client.host if request.client else None,
            details={"is_active": biz.is_active, "name": biz.name},
        )

        await session.commit()
        return {
            "id": str(biz.id),
            "name": biz.name,
            "whatsapp_phone_number": biz.whatsapp_phone_number,
            "is_active": biz.is_active,
        }


# ================= 3. GESTION DES UTILISATEURS =================

@router.get("/users")
async def list_users(
    page: int = 1,
    page_size: int = 50,
    _: User = Depends(get_current_super_admin),
):
    """Liste tous les comptes utilisateurs enregistrés sur la plateforme (paginée)."""
    offset = max(0, (page - 1) * page_size)
    async with async_session() as session:
        stmt = select(User).order_by(User.created_at.desc()).offset(offset).limit(page_size)
        users = (await session.execute(stmt)).scalars().all()

        results = []
        for u in users:
            biz_name = None
            if u.business_id:
                biz = (
                    await session.execute(select(Business).where(Business.id == u.business_id))
                ).scalar_one_or_none()
                biz_name = biz.name if biz else None

            results.append({
                "id": str(u.id),
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "role": u.role.value if hasattr(u.role, "value") else str(u.role),
                "is_active": u.is_active,
                "business_id": str(u.business_id) if u.business_id else None,
                "business_name": biz_name,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            })
        return results


@router.post("/users", status_code=201)
async def create_user_platform(
    payload: UserCreatePlatform,
    request: Request,
    current_admin: User = Depends(get_current_super_admin),
):
    """Crée un compte utilisateur (Super Admin ou membre d'une boutique)."""
    async with async_session() as session:
        existing = (
            await session.execute(select(User).where(User.email == payload.email.lower().strip()))
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Cette adresse email est déjà utilisée")

        biz_uuid = None
        if payload.role != "super_admin":
            if not payload.business_id:
                raise HTTPException(
                    status_code=400,
                    detail="Un business_id est requis pour un compte commerçant",
                )
            try:
                biz_uuid = uuid.UUID(payload.business_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="business_id invalide")

            biz = (
                await session.execute(select(Business).where(Business.id == biz_uuid))
            ).scalar_one_or_none()
            if not biz:
                raise HTTPException(status_code=404, detail="Boutique introuvable")

        new_user = User(
            email=payload.email.lower().strip(),
            password_hash=hash_password(payload.password),
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            role=UserRole(payload.role),
            business_id=biz_uuid,
            is_active=True,
        )
        session.add(new_user)
        await session.flush()

        await record_audit_log(
            session=session,
            actor_user_id=current_admin.id,
            action="CREATE_USER",
            resource_type="user",
            resource_id=str(new_user.id),
            business_id=biz_uuid,
            ip_address=request.client.host if request.client else None,
            details={"email": new_user.email, "role": payload.role},
        )

        await session.commit()
        await session.refresh(new_user)

        return {
            "id": str(new_user.id),
            "email": new_user.email,
            "role": new_user.role.value if hasattr(new_user.role, "value") else str(new_user.role),
            "business_id": str(new_user.business_id) if new_user.business_id else None,
            "is_active": new_user.is_active,
        }


@router.patch("/users/{user_id}")
async def update_user_status(
    user_id: uuid.UUID,
    payload: UserUpdatePlatform,
    request: Request,
    current_admin: User = Depends(get_current_super_admin),
):
    """Active ou désactive un utilisateur, ou modifie son rôle."""
    if current_admin.id == user_id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas désactiver votre propre compte")

    async with async_session() as session:
        user = (
            await session.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")

        audit_action = "UPDATE_USER"
        if payload.is_active is False and user.is_active is True:
            audit_action = "DISABLE_USER"
        elif payload.is_active is True and user.is_active is False:
            audit_action = "ENABLE_USER"

        if payload.is_active is not None:
            user.is_active = payload.is_active
        if payload.role is not None:
            user.role = UserRole(payload.role)

        await record_audit_log(
            session=session,
            actor_user_id=current_admin.id,
            action=audit_action,
            resource_type="user",
            resource_id=str(user.id),
            business_id=user.business_id,
            ip_address=request.client.host if request.client else None,
            details={"is_active": user.is_active, "email": user.email},
        )

        await session.commit()
        return {
            "id": str(user.id),
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "is_active": user.is_active,
        }


# ================= 4. IMPERSONATION (INSPECTION DE BOUTIQUE) =================

@router.post("/impersonate/{business_id}")
async def impersonate_business(
    business_id: uuid.UUID,
    request: Request,
    current_admin: User = Depends(get_current_super_admin),
):
    """
    Génère un token d'accès d'impersonation éphémère (15 minutes) permettant au
    Super Admin d'inspecter une boutique en tant que commerçant (Section 15).
    """
    async with async_session() as session:
        biz = (
            await session.execute(select(Business).where(Business.id == business_id))
        ).scalar_one_or_none()
        if not biz:
            raise HTTPException(status_code=404, detail="Boutique introuvable")

        if not biz.is_active:
            raise HTTPException(status_code=400, detail="Impossible d'inspecter une boutique suspendue")

        # Durée limitée à 15 minutes
        impersonation_duration = timedelta(minutes=15)
        temp_token = create_access_token(
            user_id=str(current_admin.id),
            business_id=str(biz.id),
            expires_delta=impersonation_duration,
            impersonation=True,
            acting_as_business=str(biz.id),
            role="super_admin",
        )

        # Traçabilité obligatoire dans les logs d'audit
        await record_audit_log(
            session=session,
            actor_user_id=current_admin.id,
            action="IMPERSONATE_BUSINESS",
            resource_type="business",
            resource_id=str(biz.id),
            business_id=biz.id,
            ip_address=request.client.host if request.client else None,
            details={
                "business_name": biz.name,
                "expires_in_minutes": 15,
                "super_admin_email": current_admin.email,
            },
        )
        await session.commit()

        return {
            "impersonation_token": temp_token,
            "business_id": str(biz.id),
            "business_name": biz.name,
            "expires_in_minutes": 15,
        }


# ================= 5. JOURNAL D'AUDIT (AUDIT LOGS) =================

@router.get("/audit-logs")
async def list_audit_logs(
    page: int = 1,
    page_size: int = 50,
    action: str | None = None,
    _: User = Depends(get_current_super_admin),
):
    """Liste les événements du journal d'audit avec pagination (Section 14)."""
    offset = max(0, (page - 1) * page_size)
    async with async_session() as session:
        query = select(AuditLog).order_by(AuditLog.created_at.desc())
        if action:
            query = query.where(AuditLog.action == action)

        query = query.offset(offset).limit(page_size)
        entries = (await session.execute(query)).scalars().all()

        results = []
        for e in entries:
            results.append({
                "id": str(e.id),
                "actor_user_id": str(e.actor_user_id) if e.actor_user_id else None,
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "business_id": str(e.business_id) if e.business_id else None,
                "ip_address": e.ip_address,
                "details": e.details,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            })
        return results


# ================= 4. SUPERVISION SYSTÈME & SANTÉ =================

@router.get("/health")
async def platform_health_check(_: User = Depends(get_current_super_admin)):
    """Supervision technique des composants de la plateforme."""
    db_ok = False
    try:
        async with async_session() as session:
            await session.execute(select(1))
            db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "healthy" if db_ok else "degraded",
        "components": {
            "api": {
                "status": "online",
                "version": "0.1.0",
                "environment": settings.env,
            },
            "database": {
                "status": "connected" if db_ok else "unreachable",
                "engine": "PostgreSQL 16",
            },
            "llm_provider": {
                "model": settings.ollama_model,
                "base_url": settings.ollama_base_url,
                "configured": bool(settings.ollama_api_key),
            },
            "whatsapp_meta": {
                "configured": bool(settings.whatsapp_access_token and settings.meta_app_secret),
                "phone_number_id": settings.whatsapp_phone_number_id or "Non configuré",
            },
        },
    }
