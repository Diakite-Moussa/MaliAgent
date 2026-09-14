"""
Service de journalisation des actions d'audit pour MaliAgent.
Section 14 du cahier des charges.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def record_audit_log(
    session: AsyncSession,
    action: str,
    resource_type: str,
    actor_user_id: uuid.UUID | None = None,
    resource_id: str | None = None,
    business_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """
    Enregistre un événement dans la table audit_logs.
    Ne committe pas la transaction pour permettre de faire partie de la transaction parente,
    ou utilise session.flush().
    """
    log_entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        business_id=business_id,
        ip_address=ip_address,
        details=details or {},
    )
    session.add(log_entry)
    await session.flush()
    return log_entry
