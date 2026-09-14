"""
Script de provisionnement du Super Administrateur (Propriétaire de la plateforme).
Section 6.3 du cahier des charges fonctionnel.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.asyncio_compat import use_selector_event_loop_on_windows
use_selector_event_loop_on_windows()

from sqlalchemy import select
from app.core.security import hash_password
from app.db.session import async_session
from app.models import User, UserRole


async def create_super_admin(email: str = "owner@maliagent.ml", password: str = "OwnerPassword123!"):
    print("=== CRÉATION DU SUPER ADMINISTRATEUR DE LA PLATEFORME ===")
    async with async_session() as session:
        stmt = select(User).where(User.email == email.lower().strip())
        existing = (await session.execute(stmt)).scalar_one_or_none()

        if existing:
            print(f"L'utilisateur {email} existe déjà.")
            existing.role = UserRole.SUPER_ADMIN
            existing.business_id = None
            existing.is_active = True
            existing.password_hash = hash_password(password)
            await session.commit()
            print(f"-> Mis à jour en SUPER_ADMIN avec succès ! Mot de passe réinitialisé : {password}")
            return existing

        super_admin = User(
            email=email.lower().strip(),
            password_hash=hash_password(password),
            first_name="Super",
            last_name="Admin",
            role=UserRole.SUPER_ADMIN,
            business_id=None,  # Autorité globale sur toute la plateforme
            is_active=True,
        )
        session.add(super_admin)
        await session.commit()
        print(f"-> Compte Super Admin créé avec succès !")
        print(f"   Email : {email}")
        print(f"   Mot de passe : {password}")
        return super_admin


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "owner@maliagent.ml"
    password = sys.argv[2] if len(sys.argv) > 2 else "OwnerPassword123!"
    asyncio.run(create_super_admin(email, password))
