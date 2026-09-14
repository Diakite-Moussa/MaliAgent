"""
Script de provisioning pour le rôle Livreur & Partenaire Logistique (Sprint 9 - V2.0).
Crée :
1. Un livreur interne de démo ("Ousmane Traoré" - livreur.tech@maliagent.ml / Password123!)
2. Une agence partenaire de démo ("Bamako Coursiers Express")
Rattachés à la boutique pilote Bamako Tech Express.

Usage : python scripts/provision_demo_driver.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.core.security import hash_password
from app.db.session import async_session
from app.models import Business, DeliveryPartner, DriverType, User, UserRole

use_selector_event_loop_on_windows()


async def provision_demo_driver():
    print("=== PROVISIONING LIVREUR & PARTENAIRE DEMO (SPRINT 9) ===")

    async with async_session() as session:
        # Trouver la boutique pilote
        stmt = select(Business).order_by(Business.created_at.asc())
        business = (await session.execute(stmt)).scalars().first()

        if not business:
            print("[!] Aucune boutique trouvée. Veuillez d'abord exécuter scripts/seed_pilot_data.py")
            return

        print(f"[*] Rattachement à la boutique : {business.name} ({business.whatsapp_phone_number})")

        # 1. Livreur interne de démonstration
        driver_email = "livreur.tech@maliagent.ml"
        stmt_driver = select(User).where(User.email == driver_email)
        driver = (await session.execute(stmt_driver)).scalar_one_or_none()

        if not driver:
            driver = User(
                business_id=business.id,
                email=driver_email,
                password_hash=hash_password("Password123!"),
                first_name="Ousmane",
                last_name="Traoré",
                role=UserRole.LIVREUR,
                driver_type=DriverType.INTERNAL,
                phone_number="+22370001122",
                is_available=True,
                is_active=True,
            )
            session.add(driver)
            print(f"[+] Livreur créé : {driver.first_name} {driver.last_name} ({driver.email})")
        else:
            driver.role = UserRole.LIVREUR
            driver.driver_type = DriverType.INTERNAL
            driver.phone_number = "+22370001122"
            driver.is_available = True
            print(f"[*] Livreur mis à jour : {driver.email}")

        # 2. Agence partenaire de démonstration
        stmt_partner = select(DeliveryPartner).where(
            DeliveryPartner.business_id == business.id,
            DeliveryPartner.name == "Bamako Coursiers Express SARL",
        )
        partner = (await session.execute(stmt_partner)).scalar_one_or_none()

        if not partner:
            partner = DeliveryPartner(
                business_id=business.id,
                name="Bamako Coursiers Express SARL",
                contact_name="Amadou Diallo",
                phone_number="+22376002233",
                address="ACI 2000, près du monument de la Paix, Bamako",
                active=True,
                notes="Partenaire flotte moto pour livraisons express Rive Droite et Rive Gauche",
            )
            session.add(partner)
            print(f"[+] Partenaire créé : {partner.name} ({partner.phone_number})")
        else:
            print(f"[*] Partenaire existant : {partner.name}")

        await session.commit()
        print("\n[OK] Provisioning Sprint 9 terminé avec succès.")
        print(f"Identifiants Livreur : {driver_email} / Password123!")


if __name__ == "__main__":
    asyncio.run(provision_demo_driver())
