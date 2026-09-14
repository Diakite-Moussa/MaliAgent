"""
Résout un Business à partir du numéro WhatsApp qui a reçu le message.
"""

import re

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Business


def normalize_phone_number(raw: str) -> str:
    """
    Ne garde que les chiffres d'un numéro de téléphone.

    Meta envoie `display_phone_number` sans "+" ni espaces (ex.
    "15556640413"), alors qu'un numéro peut être saisi/affiché sous des
    formats variés ("+1 (555) 664-0413", "1-555-664-0413", ...). On
    compare toujours des numéros normalisés pour éviter les faux négatifs
    de lookup — c'est ce qui causait des messages reçus mais jamais
    répondus (business introuvable en silence).
    """
    return re.sub(r"\D", "", raw or "")


async def get_business_by_whatsapp_number(
    session: AsyncSession, whatsapp_phone_number: str
) -> Business | None:
    normalized = normalize_phone_number(whatsapp_phone_number)
    stmt = select(Business).where(
        or_(
            Business.whatsapp_phone_number == normalized,
            func.regexp_replace(Business.whatsapp_phone_number, r"\D", "", "g") == normalized,
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
