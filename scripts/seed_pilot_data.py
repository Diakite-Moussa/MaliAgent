"""
Script de seeding des boutiques pilotes réelles de Bamako pour MaliAgent (Sprint 7).
Initialise :
1. Bamako Tech Express (High-Tech, smartphones & accessoires)
2. Djoliba Style & Beauté (Mode, Bazin & Cosmétiques)
3. Zones de livraison complètes des 6 communes du District de Bamako
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.db.session import async_session
from app.models import Business, DeliveryZone, Product

use_selector_event_loop_on_windows()

BAMAKO_ZONES = [
    {
        "name": "Commune IV (ACI 2000, Hamdallaye, Lafiabougou)",
        "fee": Decimal("1000"),
        "keywords": ["aci", "aci 2000", "hamdallaye", "lafiabougou", "sebenikoro", "djicoroni"],
    },
    {
        "name": "Commune III (Centre Commercial, Darsalam, Ouolofobougou)",
        "fee": Decimal("1000"),
        "keywords": ["centre-ville", "grand marche", "darsalam", "ouolofobougou", "badialan"],
    },
    {
        "name": "Commune II (Hippodrome, Niaréla, Bozola, Quinzambougou)",
        "fee": Decimal("1500"),
        "keywords": ["hippodrome", "niarela", "bozola", "bagadadji", "quinzambougou", "tsf", "bougouba"],
    },
    {
        "name": "Commune I (Korofina, Sotuba, Djelibougou, Fadjiguila)",
        "fee": Decimal("1500"),
        "keywords": ["korofina", "sotuba", "djelibougou", "fadjiguila", "doumanzana", "banconi"],
    },
    {
        "name": "Commune V (Badalabougou, Baco Djicoroni, Torokorobougou, Daoudabougou)",
        "fee": Decimal("1500"),
        "keywords": ["badalabougou", "baco djicoroni", "torokorobougou", "daoudabougou", "sabalibougou"],
    },
    {
        "name": "Commune VI (Faladié, Sogoniko, Banankabougou, Yirimadio, Kalaban Coura)",
        "fee": Decimal("2000"),
        "keywords": ["faladie", "faladié", "sogoniko", "banankabougou", "yirimadio", "kalaban coura", "kalaban", "magnambougou", "missabougou", "senou", "sénou"],
    },
    {
        "name": "Retrait sur place en boutique",
        "fee": Decimal("0"),
        "keywords": ["retrait", "sur place", "boutique", "magasin", "je passe chercher", "venir chercher"],
    },
]

PILOT_BUSINESSES = [
    {
        "name": "Bamako Tech Express",
        "phone": "22370001122",
        "currency": "XOF",
        "products": [
            {"name": "iPhone 13 128Go Reconditionné A+", "category": "smartphone", "price": Decimal("380000"), "stock": 4},
            {"name": "Samsung Galaxy A15 128Go Neuf", "category": "smartphone", "price": Decimal("95000"), "stock": 8},
            {"name": "Écouteurs AirPods Pro 2", "category": "audio", "price": Decimal("145000"), "stock": 6},
            {"name": "Chargeur Rapide 25W Type-C Original", "category": "accessoire", "price": Decimal("12500"), "stock": 25},
            {"name": "Powerbank Oraimo 20000mAh Dual USB", "category": "accessoire", "price": Decimal("18000"), "stock": 15},
            {"name": "Coque Antichoc Silicone Renforcée", "category": "accessoire", "price": Decimal("3500"), "stock": 40},
            {"name": "Câble Fast Charge Type-C 2m", "category": "accessoire", "price": Decimal("2500"), "stock": 50},
            {"name": "Smartwatch Oraimo Watch 4 Pro", "category": "montre", "price": Decimal("28000"), "stock": 0},
        ],
    },
    {
        "name": "Djoliba Style & Beauté",
        "phone": "22376663344",
        "currency": "XOF",
        "products": [
            {"name": "Ensemble Bazin Riche Brodé Getzner", "category": "mode", "price": Decimal("65000"), "stock": 5},
            {"name": "Robe Soie de Médine Plissée", "category": "mode", "price": Decimal("25000"), "stock": 12},
            {"name": "Sac à main cuir artisanal de vachette", "category": "maroquinerie", "price": Decimal("35000"), "stock": 3},
            {"name": "Parfum Musc Blanc d'Arabie 100ml", "category": "parfum", "price": Decimal("15000"), "stock": 10},
            {"name": "Pack Soins Beurre de Karité & Argan Bio", "category": "cosmetique", "price": Decimal("9500"), "stock": 20},
            {"name": "Voile Chiffon Premium Noir", "category": "accessoire", "price": Decimal("4000"), "stock": 30},
        ],
    },
]


async def seed_pilot_data():
    print("=== SEEDING DES BOUTIQUES PILOTES MALIAGENT (SPRINT 7) ===")

    async with async_session() as session:
        existing_businesses = (await session.execute(select(Business))).scalars().all()
        demo_business = existing_businesses[0] if existing_businesses else None

        businesses_to_configure = []

        for p_biz in PILOT_BUSINESSES:
            stmt = select(Business).where(Business.whatsapp_phone_number == p_biz["phone"])
            biz = (await session.execute(stmt)).scalar_one_or_none()

            if not biz:
                biz = Business(
                    name=p_biz["name"],
                    whatsapp_phone_number=p_biz["phone"],
                    currency=p_biz["currency"],
                )
                session.add(biz)
                await session.flush()
                print(f"[+] Création boutique pilote : {biz.name} ({biz.whatsapp_phone_number})")
            else:
                print(f"[*] Boutique existante : {biz.name}")

            businesses_to_configure.append((biz, p_biz["products"]))

        if demo_business:
            businesses_to_configure.append((demo_business, []))

        for biz, products in businesses_to_configure:
            existing_zones = (
                await session.execute(select(DeliveryZone).where(DeliveryZone.business_id == biz.id))
            ).scalars().all()

            if len(existing_zones) < len(BAMAKO_ZONES):
                for z_data in BAMAKO_ZONES:
                    already = any(z.name == z_data["name"] for z in existing_zones)
                    if not already:
                        zone = DeliveryZone(
                            business_id=biz.id,
                            name=z_data["name"],
                            fee=z_data["fee"],
                            keywords=z_data["keywords"],
                        )
                        session.add(zone)
                print(f"   -> {len(BAMAKO_ZONES)} zones de livraison configurées pour {biz.name}")

            for p_data in products:
                stmt_prod = select(Product).where(
                    Product.business_id == biz.id,
                    Product.name == p_data["name"],
                )
                prod = (await session.execute(stmt_prod)).scalar_one_or_none()
                if not prod:
                    prod = Product(
                        business_id=biz.id,
                        name=p_data["name"],
                        category=p_data["category"],
                        price=p_data["price"],
                        stock_quantity=p_data["stock"],
                    )
                    session.add(prod)
                    print(f"   + Produit : {prod.name} ({int(prod.price)} FCFA, stock={prod.stock_quantity})")

        await session.commit()
        print("\n[SUCCESS] Seeding des donnees pilotes termine avec succes !")


if __name__ == "__main__":
    asyncio.run(seed_pilot_data())
