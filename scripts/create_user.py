"""
Crée un utilisateur dashboard pour un Business existant.
Usage : python scripts/create_user.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.core.security import hash_password
from app.db.session import async_session
from app.models import Business, User, UserRole

use_selector_event_loop_on_windows()


async def main():
    async with async_session() as session:
        businesses = (await session.execute(select(Business))).scalars().all()
        for i, b in enumerate(businesses):
            print(f"{i}: {b.name} ({b.whatsapp_phone_number})")

        idx = int(input("\nChoisir le business (numéro) : "))
        business = businesses[idx]

        email = input("Email : ").strip().lower()
        password = input("Mot de passe : ").strip()
        first_name = input("Prénom : ").strip()
        last_name = input("Nom : ").strip()

        user = User(
            business_id=business.id,
            email=email,
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            role=UserRole.ADMIN,
        )
        session.add(user)
        await session.commit()
        print(f"\n[OK] Utilisateur {email} créé pour {business.name}.")


if __name__ == "__main__":
    asyncio.run(main())
