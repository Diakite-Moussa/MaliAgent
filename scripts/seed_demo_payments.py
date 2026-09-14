"""
Initialise des transactions de démonstration pour la Boutique Demo.
Génère :
1. Une transaction Wave en attente de validation (avec lien mockup cliquable)
2. Une transaction Orange Money validée (SUCCESS) avec réconciliation
3. Une transaction Wave échouée (FAILED)
"""

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.asyncio_compat import use_selector_event_loop_on_windows
use_selector_event_loop_on_windows()

from sqlalchemy import select
from app.db.session import async_session
from app.models import Business, Customer, Order
from app.payments.service import payment_service


async def seed():
    async with async_session() as session:
        b = (await session.execute(select(Business).where(Business.name == "Boutique Demo"))).scalar_one_or_none()
        if not b:
            print("❌ Boutique Demo non trouvée")
            return

        orders = (await session.execute(select(Order).where(Order.business_id == b.id))).scalars().all()
        if not orders:
            print("❌ Aucune commande trouvée")
            return

        print(f"📦 Boutique Demo ({b.name}) : {len(orders)} commandes trouvées.")

        # 1. Transaction Wave en attente (sur o1)
        o1 = orders[0]
        c1 = (await session.execute(select(Customer).where(Customer.id == o1.customer_id))).scalar_one_or_none()
        phone1 = c1.whatsapp_phone_number if c1 else "+22370112233"

        p1 = await payment_service.initiate_payment(
            session=session,
            business_id=b.id,
            order_id=o1.id,
            provider="wave",
            customer_phone=phone1,
        )
        print(f"✅ 1. Transaction Wave créée : {p1.transaction_reference} (Statut: {p1.status.value})")
        print(f"   Lien : {p1.checkout_url}")

        # 2. Transaction Orange Money validée (sur o2)
        if len(orders) > 1:
            o2 = orders[1]
            c2 = (await session.execute(select(Customer).where(Customer.id == o2.customer_id))).scalar_one_or_none()
            phone2 = c2.whatsapp_phone_number if c2 else "+22376998877"

            p2 = await payment_service.initiate_payment(
                session=session,
                business_id=b.id,
                order_id=o2.id,
                provider="orange_money",
                customer_phone=phone2,
            )
            # Validation via simulate_payment
            res2 = await payment_service.simulate_payment(
                session=session,
                transaction_reference=p2.transaction_reference,
                outcome="success",
            )
            print(f"✅ 2. Transaction Orange Money validée : {p2.transaction_reference} -> {res2.get('payment_status')}")

        # 3. Transaction Wave échouée (sur o3)
        if len(orders) > 2:
            o3 = orders[2]
            c3 = (await session.execute(select(Customer).where(Customer.id == o3.customer_id))).scalar_one_or_none()
            phone3 = c3.whatsapp_phone_number if c3 else "+22365432100"

            p3 = await payment_service.initiate_payment(
                session=session,
                business_id=b.id,
                order_id=o3.id,
                provider="wave",
                customer_phone=phone3,
            )
            res3 = await payment_service.simulate_payment(
                session=session,
                transaction_reference=p3.transaction_reference,
                outcome="failed",
            )
            print(f"✅ 3. Transaction Wave échouée : {p3.transaction_reference} -> {res3.get('payment_status')}")

        print("\n🎉 Transactions de démonstration créées avec succès pour Boutique Demo !")


if __name__ == "__main__":
    asyncio.run(seed())
