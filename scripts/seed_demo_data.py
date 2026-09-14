"""
Insère un Business de démo + quelques produits + zones de livraison,
pour tester l'agent avec de vraies données en base.
Idempotent : réutilise le business s'il existe déjà.

Usage : python scripts/seed_demo_data.py
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.asyncio_compat import use_selector_event_loop_on_windows  # noqa: E402
from app.db.session import async_session  # noqa: E402
from app.models import Business, DeliveryZone, Product  # noqa: E402

use_selector_event_loop_on_windows()


async def main():
    async with async_session() as session:
        # 1. Business
        stmt = select(Business).where(Business.whatsapp_phone_number == "15556640413")
        business = (await session.execute(stmt)).scalar_one_or_none()

        if not business:
            business = Business(
                name="Boutique Demo",
                whatsapp_phone_number="15556640413",
                currency="XOF",
            )
            session.add(business)
            await session.flush()
            print(f"Nouveau Business créé : {business.id}")
        else:
            print(f"Business existant trouvé : {business.id} ({business.name})")

        # 2. Produits
        stmt_prod = select(Product).where(Product.business_id == business.id)
        existing_products = (await session.execute(stmt_prod)).scalars().all()

        if not existing_products:
            products = [
                Product(
                    business_id=business.id,
                    name="Samsung A15",
                    category="téléphone",
                    price=Decimal("95000"),
                    stock_quantity=4,
                ),
                Product(
                    business_id=business.id,
                    name="iPhone 13",
                    category="téléphone",
                    price=Decimal("350000"),
                    stock_quantity=0,
                ),
                Product(
                    business_id=business.id,
                    name="Riz 25kg",
                    category="alimentation",
                    price=Decimal("18000"),
                    stock_quantity=50,
                ),
            ]
            session.add_all(products)
            print(f"{len(products)} produits créés.")
        else:
            print(f"{len(existing_products)} produits déjà en base.")

        # 3. Zones de livraison
        stmt_zones = select(DeliveryZone).where(DeliveryZone.business_id == business.id)
        existing_zones = (await session.execute(stmt_zones)).scalars().all()

        if not existing_zones:
            zones = [
                DeliveryZone(
                    business_id=business.id,
                    name="Zone 1 — Centre-ville / Rive Gauche (ACI 2000, Hamdallaye, Badalabougou)",
                    keywords="aci, aci 2000, hamdallaye, badalabougou, lafiabougou, centre, centre-ville, fleuve",
                    fee=Decimal("1000"),
                    estimated_time="1h à 2h",
                    active=True,
                ),
                DeliveryZone(
                    business_id=business.id,
                    name="Zone 2 — Rive Droite / Commune VI (Faladié, Yirimadio, Niamakoro, Sotuba)",
                    keywords="faladié, faladie, yirimadio, niamakoro, sotuba, daoudabougou, banankabougou, commune 6",
                    fee=Decimal("1500"),
                    estimated_time="2h à 4h",
                    active=True,
                ),
                DeliveryZone(
                    business_id=business.id,
                    name="Zone 3 — Périphérie (Kati, Moribabougou, Baguinéda)",
                    keywords="kati, moribabougou, baguinéda, baguineda, koulikoro, périphérie",
                    fee=Decimal("2500"),
                    estimated_time="Dans la journée",
                    active=True,
                ),
                DeliveryZone(
                    business_id=business.id,
                    name="Retrait en magasin / Boutique",
                    keywords="magasin, boutique, sur place, retrait, passer chercher, venir chercher",
                    fee=Decimal("0"),
                    estimated_time="Immédiat (aux heures d'ouverture)",
                    active=True,
                ),
            ]
            session.add_all(zones)
            print(f"{len(zones)} zones de livraison créées.")
        else:
            print(f"{len(existing_zones)} zones de livraison déjà en base.")

        await session.commit()
        print("Initialisation des données terminée avec succès.")


if __name__ == "__main__":
    asyncio.run(main())