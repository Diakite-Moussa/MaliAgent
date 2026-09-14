"""
Script de test complet pour le Sprint 4 :
Vérifie calculate_delivery, create_order, get_order_status et l'atomicité du stock.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.db.session import async_session
from app.models import Business, Customer, Order, Product
from app.tools.executor import execute_tool

use_selector_event_loop_on_windows()


async def main():
    print("=== DÉBUT DU TEST DU SPRINT 4 ===\n")

    async with async_session() as session:
        # 1. Récupération du Business de démo
        stmt = select(Business).where(Business.whatsapp_phone_number == "15556640413")
        business = (await session.execute(stmt)).scalar_one_or_none()
        assert business is not None, "Le business de démo doit exister"
        print(f"1. Business trouvé : {business.name} ({business.id})")

        # 2. Récupération ou création d'un Customer de test
        stmt_c = select(Customer).where(
            Customer.business_id == business.id,
            Customer.whatsapp_phone_number == "22370000000",
        )
        customer = (await session.execute(stmt_c)).scalar_one_or_none()
        if not customer:
            customer = Customer(
                business_id=business.id,
                whatsapp_phone_number="22370000000",
                display_name="Client Test",
            )
            session.add(customer)
            await session.flush()
        print(f"2. Customer de test : {customer.whatsapp_phone_number} ({customer.id})")

        # 3. Test de calculate_delivery
        print("\n3. Tests de calculate_delivery :")
        res1 = await execute_tool(
            session, business.id, customer.id, "calculate_delivery", {"zone": "Faladié"}
        )
        print(f"  - Faladié : {res1}")
        assert "1500 FCFA" in res1, "Faladié doit être à 1500 FCFA"

        res2 = await execute_tool(
            session, business.id, customer.id, "calculate_delivery", {"zone": "retrait boutique"}
        )
        print(f"  - Retrait : {res2}")
        assert "0 FCFA" in res2, "Le retrait doit être à 0 FCFA"

        res3 = await execute_tool(
            session, business.id, customer.id, "calculate_delivery", {"zone": "QuartierInconnu"}
        )
        print(f"  - Inconnu : {res3[:60]}...")
        assert "tarifs" in res3

        # 4. Stock initial du Samsung A15
        stmt_p = select(Product).where(
            Product.business_id == business.id, Product.name == "Samsung A15"
        )
        samsung = (await session.execute(stmt_p)).scalar_one()
        initial_stock = samsung.stock_quantity
        print(f"\n4. Stock initial Samsung A15 : {initial_stock} unités")

        # 5. Test create_order valide (1 Samsung A15)
        print("\n5. Test create_order valide (1 unité) :")
        res_order = await execute_tool(
            session,
            business.id,
            customer.id,
            "create_order",
            {
                "items": [{"product_name": "Samsung A15", "quantity": 1}],
                "delivery_address": "Faladié près de la pharmacie",
                "delivery_fee": 1500,
            },
        )
        print(f"  Résultat de la commande :\n{res_order}")
        assert "confirmée et enregistrée avec succès" in res_order

        # Vérification décrémentation stock
        await session.refresh(samsung)
        print(f"  Nouveau stock Samsung A15 en base : {samsung.stock_quantity}")
        assert samsung.stock_quantity == initial_stock - 1, "Le stock doit avoir diminué de 1"

        # 6. Test de get_order_status
        print("\n6. Test get_order_status :")
        res_status = await execute_tool(
            session, business.id, customer.id, "get_order_status", {}
        )
        print(f"  Statut retourné :\n{res_status}")
        assert "dernière commande" in res_status

        # 7. Test create_order avec stock insuffisant
        print("\n7. Test create_order avec stock insuffisant (99 unités) :")
        res_fail = await execute_tool(
            session,
            business.id,
            customer.id,
            "create_order",
            {
                "items": [{"product_name": "Samsung A15", "quantity": 99}],
                "delivery_address": "Kati",
                "delivery_fee": 2500,
            },
        )
        print(f"  Résultat : {res_fail}")
        assert "stock insuffisant" in res_fail

        # Vérification que le stock est resté intact
        await session.refresh(samsung)
        assert samsung.stock_quantity == initial_stock - 1, "Le stock ne doit pas avoir bougé"
        print(f"  Stock vérifié après rejet : {samsung.stock_quantity} (inchangé)")

    print("\n=== TOUS LES TESTS DU SPRINT 4 SONT PASSÉS AVEC SUCCÈS ! ===")


if __name__ == "__main__":
    asyncio.run(main())
