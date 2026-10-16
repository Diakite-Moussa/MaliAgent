"""
Endpoints de configuration et personnalisation de l'agent IA par boutique.
Section 13.14 du cahier des charges fonctionnel.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.core.deps import get_current_user
from app.db.session import async_session
from app.models import AgentConfiguration
from app.models.user import User, UserRole
from app.services.audit import record_audit_log

router = APIRouter(prefix="/api/dashboard/agent", tags=["Agent Configuration"])

ALLOWED_TONES = {"chaleureux", "formel", "concis"}
ALLOWED_LANGUAGES = {"fr", "bm"}

DEFAULT_CONFIG = {
    "agent_name": "Assistant",
    "tone": "chaleureux",
    "default_language": "fr",
    "custom_rules": None,
    "welcome_message": None,
    "enabled": True,
}


class AgentConfigOut(BaseModel):
    agent_name: str
    tone: str
    default_language: str
    custom_rules: str | None = None
    welcome_message: str | None = None
    enabled: bool


class AgentConfigUpdate(BaseModel):
    agent_name: str | None = Field(None, min_length=1, max_length=100)
    tone: str | None = None
    default_language: str | None = None
    custom_rules: str | None = Field(None, max_length=2000)
    welcome_message: str | None = Field(None, max_length=500)
    enabled: bool | None = None

    @field_validator("tone")
    @classmethod
    def check_tone(cls, v):
        if v is not None and v not in ALLOWED_TONES:
            raise ValueError(f"tone doit être l'un de : {', '.join(sorted(ALLOWED_TONES))}")
        return v

    @field_validator("default_language")
    @classmethod
    def check_language(cls, v):
        if v is not None and v not in ALLOWED_LANGUAGES:
            raise ValueError(f"default_language doit être l'un de : {', '.join(sorted(ALLOWED_LANGUAGES))}")
        return v


@router.get("/config", response_model=AgentConfigOut)
async def get_agent_config(
    current_user: User = Depends(get_current_user),
):
    """
    Retourne la configuration actuelle de l'agent IA de la boutique,
    ou les valeurs par défaut si aucune configuration n'a encore été créée.
    """
    if not current_user.business_id:
        raise HTTPException(status_code=400, detail="Aucune boutique associée à cet utilisateur")

    async with async_session() as session:
        stmt = select(AgentConfiguration).where(
            AgentConfiguration.business_id == current_user.business_id
        )
        config = (await session.execute(stmt)).scalar_one_or_none()

        if not config:
            return AgentConfigOut(**DEFAULT_CONFIG)

        return AgentConfigOut(
            agent_name=config.agent_name,
            tone=config.tone,
            default_language=config.default_language,
            custom_rules=config.custom_rules,
            welcome_message=config.welcome_message,
            enabled=config.enabled,
        )


@router.put("/config", response_model=AgentConfigOut)
async def update_agent_config(
    payload: AgentConfigUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Met à jour (ou crée si absente) la configuration de l'agent IA de la boutique.
    Réservé au rôle admin (403 pour vendeur/opérateur).
    Audit log à chaque modification.
    """
    if not current_user.business_id:
        raise HTTPException(status_code=400, detail="Aucune boutique associée à cet utilisateur")

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Action réservée aux administrateurs de la boutique",
        )

    business_id = current_user.business_id

    async with async_session() as session:
        stmt = select(AgentConfiguration).where(
            AgentConfiguration.business_id == business_id
        )
        config = (await session.execute(stmt)).scalar_one_or_none()

        if not config:
            config = AgentConfiguration(business_id=business_id, **DEFAULT_CONFIG)
            session.add(config)

        if payload.agent_name is not None:
            config.agent_name = payload.agent_name.strip()
        if payload.tone is not None:
            config.tone = payload.tone
        if payload.default_language is not None:
            config.default_language = payload.default_language
        if payload.custom_rules is not None:
            config.custom_rules = payload.custom_rules.strip() or None
        if payload.welcome_message is not None:
            config.welcome_message = payload.welcome_message.strip() or None
        if payload.enabled is not None:
            config.enabled = payload.enabled

        await session.flush()

        try:
            await record_audit_log(
                session=session,
                actor_user_id=current_user.id,
                action="UPDATE_AGENT_CONFIG",
                resource_type="agent_configuration",
                resource_id=str(config.id),
                business_id=business_id,
                ip_address=request.client.host if request.client else None,
                details={"agent_name": config.agent_name, "enabled": config.enabled},
            )
        except Exception:
            # L'audit log ne doit jamais bloquer la sauvegarde de la config.
            pass

        await session.commit()
        await session.refresh(config)

        return AgentConfigOut(
            agent_name=config.agent_name,
            tone=config.tone,
            default_language=config.default_language,
            custom_rules=config.custom_rules,
            welcome_message=config.welcome_message,
            enabled=config.enabled,
        )