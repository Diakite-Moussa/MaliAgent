"""
Script de recette bout-en-bout (E2E) pour la V2.1 : Paiements Mobile Money (Orange Money & Wave Mali).

Simule l'ensemble du cycle transactionnel :
1. Authentification Commerçant & Création d'une commande
2. WhatsApp Agent : Le client choisit de payer par Wave -> Tool initiate_payment
3. Vérification du statut avant règlement -> Tool check_payment_status (En attente)
4. Simulation du paiement client -> Webhook opérateur reçu & Réconciliation automatique
   (Payment = SUCCESS, Order = PAID & CONFIRMED, Invoice = PAID, Notification WhatsApp)
5. Test d'idempotence absolue : Le même webhook rejoué est détecté comme déjà traité
6. Scénario Orange Money : Push USSD simulé et validation
7. Scénario Rejet / Échec : Solde insuffisant -> Commande maintenue en non payée
8. Consultation de l'historique des transactions côté Dashboard Commerçant

Usage : python scripts/test_v2_1_payment_flow.py
"""

import asyncio
from decimal import Decimal
import sys
from pathlib import Path
import uuid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.core.security import hash_password
from app.db.session import async_session
from app.main import app
from app.models import Business, Customer, Invoice, Order, OrderItem, OrderStatus, Product, User, UserRole
from app.models.payment import Payment, PaymentStatus
from app.payments.gateways.mock import MockPaymentGateway
from app.payments.service import payment_service
from app.tools.executor import execute_tool

use_selector_event_loop_on_windows()


async def run_v2_1_payment_e2e_recette():
    print("=" * 70)
    print("🚀 RECETTE FINALE V2.1 — PAIEMENTS DIGITAUX MOBILE MONEY (WAVE & OM)")
    print("=" * 70)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # -------------------------------------------------------------
        # 1. Provisioning & Authentification Commerçant
        # -------------------------------------------------------------
        print("\n🔑 1. Initialisation de la boutique pilote & Connexion...")
        async with async_session() as session:
            stmt = select(Business).where(Business.name == "Bamako Tech Express")
            biz = (await session.execute(stmt)).scalar_one_or_none()
            if not biz:
                biz = Business(
                    name="Bamako Tech Express",
                    whatsapp_phone_number="+22370001122",
                    currency="XOF",
                )
                session.add(biz)
                await session.flush()

            # Utilisateur Commerçant
            user_stmt = select(User).where(User.email == "admin@maliagent.ml")
            user = (await session.execute(user_stmt)).scalar_one_or_none()
            if not user:
                user = User(
                    email="admin@maliagent.ml",
                    password_hash=hash_password("Password123!"),
                    role=UserRole.ADMIN,
                    business_id=biz.id,
                    full_name="Directeur Bamako Tech",
                    is_active=True,
                )
                session.add(user)
            else:
                user.password_hash = hash_password("Password123!")
                user.business_id = biz.id
                user.is_active = True
            await session.flush()

            # Produit
            prod_stmt = select(Product).where(Product.business_id == biz.id)
            prod = (await session.execute(prod_stmt)).scalars().first()
            if not prod:
                prod = Product(
                    business_id=biz.id,
                    name="Écouteurs Bluetooth Pro",
                    category="Accessoires",
                    price=Decimal("15000.00"),
                    stock_quantity=50,
                )
                session.add(prod)
                await session.flush()

            # Client
            cust_stmt = select(Customer).where(Customer.whatsapp_phone_number == "+22376998877")
            cust = (await session.execute(cust_stmt)).scalar_one_or_none()
            if not cust:
                cust = Customer(
                    business_id=biz.id,
                    whatsapp_phone_number="+22376998877",
                    display_name="Ibrahim Traoré",
                )
                session.add(cust)
                await session.flush()

            # Création d'une commande test
            order = Order(
                business_id=biz.id,
                customer_id=cust.id,
                status=OrderStatus.PENDING,
                delivery_address="Badalabougou Rue 14",
                delivery_fee=Decimal("1500.00"),
                payment_status="unpaid",
            )
            session.add(order)
            await session.flush()

            item = OrderItem(
                order_id=order.id,
                product_id=prod.id,
                quantity=1,
                unit_price_snapshot=Decimal("15000.00"),
            )
            session.add(item)

            # Facture associée
            inv_num = f"INV-RECETTE-{uuid.uuid4().hex[:6].upper()}"
            invoice = Invoice(
                business_id=biz.id,
                order_id=order.id,
                invoice_number=inv_num,
                subtotal=Decimal("15000.00"),
                delivery_fee=Decimal("1500.00"),
                total=Decimal("16500.00"),
                status="issued",
            )
            total_amount = Decimal("16500.00")
            session.add(invoice)
            await session.commit()

            biz_id = biz.id
            order_id = order.id
            customer_id = cust.id

        # Connexion API commerçant
        login_res = await client.post(
            "/api/auth/login",
            json={"email": "admin@maliagent.ml", "password": "Password123!"},
        )
        assert login_res.status_code == 200, f"Erreur login: {login_res.text}"
        token = login_res.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}
        print("   ✅ Commerçant authentifié avec succès.")
        print(f"   📦 Commande #{str(order_id)[:8].upper()} créée : {int(total_amount):,} FCFA (Statut: PENDING, UNPAID)")

        # -------------------------------------------------------------
        # 2. WhatsApp : Le client demande à payer par Wave
        # -------------------------------------------------------------
        print("\n📱 2. WhatsApp Agent : Le client demande à payer par Wave...")
        async with async_session() as session:
            reply_wa = await execute_tool(
                session=session,
                business_id=biz_id,
                customer_id=customer_id,
                tool_name="initiate_payment",
                arguments={"provider": "wave", "order_ref": str(order_id)[:8]},
            )
        print("   🤖 Réponse WhatsApp formulée par l'Agent :")
        for line in reply_wa.strip().split("\n"):
            print(f"      {line}")

        # Récupérer la référence de transaction
        async with async_session() as session:
            p_stmt = select(Payment).where(Payment.order_id == order_id)
            payment = (await session.execute(p_stmt)).scalar_one()
            tx_ref = payment.transaction_reference
            print(f"   ✅ Transaction créée en base : {tx_ref} (Statut: {payment.status.value})")

        # -------------------------------------------------------------
        # 3. WhatsApp : Le client vérifie le statut avant règlement
        # -------------------------------------------------------------
        print("\n⏳ 3. Le client demande : « Est-ce que mon paiement est validé ? »...")
        async with async_session() as session:
            status_reply = await execute_tool(
                session=session,
                business_id=biz_id,
                customer_id=customer_id,
                tool_name="check_payment_status",
                arguments={"order_ref": str(order_id)[:8]},
            )
        print(f"   🤖 Réponse Agent : {status_reply.strip()}")

        # -------------------------------------------------------------
        # 4. Simulation du paiement client & Webhook Opérateur
        # -------------------------------------------------------------
        print("\n🌊 4. Le client valide son paiement dans Wave (Simulation du Webhook opérateur)...")
        event_id_unique = f"wh_wave_{uuid.uuid4().hex[:8]}"
        wh_payload = MockPaymentGateway.build_simulated_webhook(
            transaction_reference=tx_ref,
            outcome="success",
            event_id=event_id_unique,
            amount=total_amount,
        )

        wh_res = await client.post("/api/payments/webhook/wave", json=wh_payload)
        assert wh_res.status_code == 200
        print("   ✅ Webhook opérateur accepté :", wh_res.json())

        # Vérification de la réconciliation en base
        async with async_session() as session:
            refreshed_order = (await session.execute(select(Order).where(Order.id == order_id))).scalar_one()
            refreshed_inv = (await session.execute(select(Invoice).where(Invoice.order_id == order_id))).scalar_one()
            refreshed_pay = (await session.execute(select(Payment).where(Payment.transaction_reference == tx_ref))).scalar_one()

            print(f"   🟢 Statut Paiement : {refreshed_pay.status.value.upper()} (Validé à: {refreshed_pay.paid_at})")
            print(f"   🟢 Statut Commande : {refreshed_order.status.value.upper()} (payment_status: {refreshed_order.payment_status.upper()})")
            print(f"   🟢 Statut Facture  : {refreshed_inv.status.upper()} (Réf règlement: {refreshed_inv.payment_reference})")
            assert refreshed_order.payment_status == "paid"
            assert refreshed_order.status == OrderStatus.CONFIRMED
            assert refreshed_inv.status == "paid"

        # -------------------------------------------------------------
        # 5. Test d'idempotence absolue
        # -------------------------------------------------------------
        print("\n🛡️ 5. Test d'idempotence absolue (Renvoi du même webhook opérateur)...")
        dup_res = await client.post("/api/payments/webhook/wave", json=wh_payload)
        assert dup_res.status_code == 200
        assert dup_res.json()["status"] == "already_processed"
        print("   ✅ Webhook dupliqué détecté et neutralisé :", dup_res.json()["status"])

        # -------------------------------------------------------------
        # 6. Scénario Orange Money : Push USSD simulé
        # -------------------------------------------------------------
        print("\n🍊 6. Scénario Orange Money sur nouvelle commande...")
        async with async_session() as session:
            om_order = Order(
                business_id=biz_id,
                customer_id=customer_id,
                status=OrderStatus.PENDING,
                delivery_address="Faladié SEMA",
                delivery_fee=Decimal("1500.00"),
                payment_status="unpaid",
            )
            session.add(om_order)
            await session.flush()
            om_item = OrderItem(order_id=om_order.id, product_id=prod.id, quantity=1, unit_price_snapshot=Decimal("15000.00"))
            session.add(om_item)
            await session.commit()
            om_order_id = om_order.id

        async with async_session() as session:
            om_reply = await execute_tool(
                session=session,
                business_id=biz_id,
                customer_id=customer_id,
                tool_name="initiate_payment",
                arguments={"provider": "orange_money", "customer_phone": "76123456", "order_ref": str(om_order_id)[:8]},
            )
        print("   🤖 Réponse Agent Orange Money :")
        for line in om_reply.strip().split("\n"):
            print(f"      {line}")

        # -------------------------------------------------------------
        # 7. Scénario Échec / Rejet (Solde insuffisant)
        # -------------------------------------------------------------
        print("\n⚠️ 7. Scénario d'échec / rejet (Solde insuffisant)...")
        async with async_session() as session:
            fail_p_stmt = select(Payment).where(Payment.order_id == om_order_id)
            om_payment = (await session.execute(fail_p_stmt)).scalar_one()
            om_tx_ref = om_payment.transaction_reference

        fail_payload = MockPaymentGateway.build_simulated_webhook(
            transaction_reference=om_tx_ref,
            outcome="failed",
        )
        fail_res = await client.post("/api/payments/webhook/orange-money", json=fail_payload)
        assert fail_res.status_code == 200

        async with async_session() as session:
            chk_order = (await session.execute(select(Order).where(Order.id == om_order_id))).scalar_one()
            chk_pay = (await session.execute(select(Payment).where(Payment.transaction_reference == om_tx_ref))).scalar_one()
            print(f"   ❌ Paiement rejeté : {chk_pay.status.value.upper()}")
            print(f"   🔒 Commande maintenue en non-payée : {chk_order.payment_status.upper()} ({chk_order.status.value.upper()})")
            assert chk_pay.status == PaymentStatus.FAILED
            assert chk_order.payment_status == "unpaid"

        # -------------------------------------------------------------
        # 8. Consultation des paiements dans l'API Dashboard
        # -------------------------------------------------------------
        print("\n📊 8. Consultation de l'historique des paiements dans l'API Dashboard...")
        dash_res = await client.get("/api/payments", headers=auth_headers)
        assert dash_res.status_code == 200
        payments_list = dash_res.json()
        print(f"   ✅ {len(payments_list)} transaction(s) récupérée(s) pour la boutique :")
        for p in payments_list[:3]:
            paid_str = f"| Réglé à: {p['paid_at'][:19]}" if p.get("paid_at") else ""
            print(f"      • [{p['provider'].upper()}] {p['transaction_reference']} : {int(Decimal(str(p['amount']))):,} {p['currency']} -> Statut: {p['status'].upper()} {paid_str}")

    print("\n" + "=" * 70)
    print("🎉 RECETTE FINALE V2.1 VALIDÉE AVEC SUCCÈS À 100% !")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_v2_1_payment_e2e_recette())
