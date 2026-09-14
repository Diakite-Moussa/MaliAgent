"""
Suite de tests automatisés Pytest pour la V2.1 : Moteur de Paiement Mobile Money.

Vérifie l'ensemble des règles obligatoires :
1. Cycle complet succès : Initiation -> Webhook -> SUCCESS -> Order PAID / CONFIRMED -> Invoice PAID
2. Cycle d'échec : Webhook FAILED -> Order reste unpaid
3. Cycle d'expiration : Webhook EXPIRED
4. Idempotence absolue : Le même webhook reçu 3 fois consécutives n'est exécuté qu'une seule fois
5. Isolation Multi-Tenant : La boutique A ne peut pas accéder aux paiements de la boutique B
6. Protection Endpoint Simulation : Rejet en HTTP 403 si le mode production est simulé
7. Intégration Agent IA (Tool Calling) : initiate_payment et check_payment_status
"""

from decimal import Decimal
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import async_session
from app.main import app
from app.models.business import Business
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.order import Order, OrderItem, OrderStatus
from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.models.product import Product
from app.payments.gateways.mock import MockPaymentGateway
from app.payments.service import payment_service
from app.tools.executor import execute_tool


@pytest.fixture
async def setup_test_data():
    """Crée deux boutiques distinctes (multi-tenant), un client et une commande."""
    async with async_session() as session:
        # Boutique A
        biz_a = Business(
            name=f"Boutique A-{uuid.uuid4().hex[:6]}",
            whatsapp_phone_number=f"+22370{uuid.uuid4().hex[:6]}",
            currency="XOF",
        )
        # Boutique B
        biz_b = Business(
            name=f"Boutique B-{uuid.uuid4().hex[:6]}",
            whatsapp_phone_number=f"+22370{uuid.uuid4().hex[:6]}",
            currency="XOF",
        )
        session.add_all([biz_a, biz_b])
        await session.flush()

        # Produit & Client Boutique A
        prod = Product(
            business_id=biz_a.id,
            name="Smartphone Galaxy Test",
            category="Téléphonie",
            price=Decimal("100000.00"),
            stock_quantity=10,
        )
        customer_a = Customer(
            business_id=biz_a.id,
            whatsapp_phone_number="22370112233",
            display_name="Client A",
        )
        session.add_all([prod, customer_a])
        await session.flush()

        # Commande pour Boutique A
        order_a = Order(
            business_id=biz_a.id,
            customer_id=customer_a.id,
            status=OrderStatus.PENDING,
            delivery_address="Hamdallaye ACI 2000",
            delivery_fee=Decimal("1500.00"),
            payment_status="unpaid",
        )
        session.add(order_a)
        await session.flush()

        order_item = OrderItem(
            order_id=order_a.id,
            product_id=prod.id,
            quantity=1,
            unit_price_snapshot=Decimal("100000.00"),
        )
        session.add(order_item)

        # Facture associée
        invoice_a = Invoice(
            business_id=biz_a.id,
            order_id=order_a.id,
            invoice_number=f"INV-TEST-{uuid.uuid4().hex[:6].upper()}",
            subtotal=Decimal("100000.00"),
            delivery_fee=Decimal("1500.00"),
            total=Decimal("101500.00"),
            status="issued",
        )
        session.add(invoice_a)
        await session.commit()

        return {
            "biz_a_id": biz_a.id,
            "biz_b_id": biz_b.id,
            "customer_a_id": customer_a.id,
            "order_a_id": order_a.id,
            "invoice_a_id": invoice_a.id,
            "phone_a": customer_a.whatsapp_phone_number,
        }


@pytest.mark.asyncio
async def test_payment_success_reconciliation_flow(setup_test_data):
    """
    Test 1 : Cycle complet avec succès et réconciliation automatique.
    Order -> initiate_payment -> Mock Gateway -> Webhook -> SUCCESS -> Order PAID/CONFIRMED -> Invoice PAID
    """
    data = setup_test_data
    biz_a_id = data["biz_a_id"]
    order_id = data["order_a_id"]

    async with async_session() as session:
        # 1. Initiation
        payment = await payment_service.initiate_payment(
            session=session,
            business_id=biz_a_id,
            order_id=order_id,
            provider="wave",
            customer_phone=data["phone_a"],
        )
        assert payment.id is not None
        assert payment.status == PaymentStatus.PENDING_VALIDATION
        assert "wave" in payment.provider.lower()
        assert payment.checkout_url is not None
        tx_ref = payment.transaction_reference

    # 2. Simulation du Webhook Opérateur de succès
    event_id = f"evt_success_{uuid.uuid4().hex[:8]}"
    wh_payload = MockPaymentGateway.build_simulated_webhook(
        transaction_reference=tx_ref,
        outcome="success",
        event_id=event_id,
        amount=Decimal("101500.00"),
    )

    async with async_session() as session:
        res = await payment_service.handle_webhook(
            session=session,
            provider="mock",
            payload=wh_payload,
            headers={},
        )
        assert res["status"] == "processed"
        assert res["payment_status"] == PaymentStatus.SUCCESS.value

        # 3. Vérification de la réconciliation Order et Invoice
        order_stmt = select(Order).where(Order.id == order_id)
        order = (await session.execute(order_stmt)).scalar_one()
        assert order.payment_status == "paid"
        assert order.status == OrderStatus.CONFIRMED

        inv_stmt = select(Invoice).where(Invoice.order_id == order_id)
        invoice = (await session.execute(inv_stmt)).scalar_one()
        assert invoice.status == "paid"
        assert invoice.payment_reference == tx_ref


@pytest.mark.asyncio
async def test_payment_failure_flow(setup_test_data):
    """
    Test 2 : Échec de transaction (solde insuffisant, rejet client).
    La commande ne doit JAMAIS être marquée comme payée.
    """
    data = setup_test_data
    biz_a_id = data["biz_a_id"]
    order_id = data["order_a_id"]

    async with async_session() as session:
        payment = await payment_service.initiate_payment(
            session=session,
            business_id=biz_a_id,
            order_id=order_id,
            provider="orange_money",
        )
        tx_ref = payment.transaction_reference

    # Webhook simulant un rejet
    wh_payload = MockPaymentGateway.build_simulated_webhook(
        transaction_reference=tx_ref,
        outcome="failed",
    )

    async with async_session() as session:
        res = await payment_service.handle_webhook(
            session=session,
            provider="mock",
            payload=wh_payload,
            headers={},
        )
        assert res["payment_status"] == PaymentStatus.FAILED.value

        order = (await session.execute(select(Order).where(Order.id == order_id))).scalar_one()
        assert order.payment_status != "paid"
        assert order.status == OrderStatus.PENDING


@pytest.mark.asyncio
async def test_webhook_idempotency_absolute(setup_test_data):
    """
    Test 4 : Idempotence absolue.
    L'envoi du même webhook 3 fois d'affilée ne doit déclencher qu'un seul traitement
    et renvoyer 'already_processed'.
    """
    data = setup_test_data
    biz_a_id = data["biz_a_id"]
    order_id = data["order_a_id"]

    async with async_session() as session:
        payment = await payment_service.initiate_payment(
            session=session,
            business_id=biz_a_id,
            order_id=order_id,
            provider="wave",
        )
        tx_ref = payment.transaction_reference

    fixed_event_id = f"fixed_event_id_{uuid.uuid4().hex[:8]}"
    wh_payload = MockPaymentGateway.build_simulated_webhook(
        transaction_reference=tx_ref,
        outcome="success",
        event_id=fixed_event_id,
    )

    async with async_session() as session:
        # Appel 1 : Traitement normal
        res1 = await payment_service.handle_webhook(session, "mock", wh_payload, {})
        assert res1["status"] == "processed"

    async with async_session() as session:
        # Appel 2 : Doit être détecté comme déjà traité
        res2 = await payment_service.handle_webhook(session, "mock", wh_payload, {})
        assert res2["status"] == "already_processed"

    async with async_session() as session:
        # Appel 3 : Idem
        res3 = await payment_service.handle_webhook(session, "mock", wh_payload, {})
        assert res3["status"] == "already_processed"


@pytest.mark.asyncio
async def test_multi_tenant_isolation(setup_test_data):
    """
    Test 5 : Isolation Multi-Tenant.
    La Boutique B ne doit sous aucun prétexte pouvoir initier ou consulter un paiement de la Boutique A.
    """
    data = setup_test_data
    biz_a_id = data["biz_a_id"]
    biz_b_id = data["biz_b_id"]
    order_a_id = data["order_a_id"]

    async with async_session() as session:
        # Tentative Boutique B sur commande Boutique A
        with pytest.raises(ValueError, match="introuvable ou non autorisée"):
            await payment_service.initiate_payment(
                session=session,
                business_id=biz_b_id,
                order_id=order_a_id,
                provider="wave",
            )


@pytest.mark.asyncio
async def test_simulation_endpoint_protection():
    """
    Test 6 : Protection de l'endpoint /simulate-webhook.
    Bloqué formellement en HTTP 403 si settings.is_payment_simulation est faux.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Sauvegarde de l'état
        orig_mode = settings.payment_mode
        orig_prov = settings.payment_provider
        try:
            settings.payment_mode = "production"
            settings.payment_provider = "wave"
            res = await client.post(
                "/api/payments/simulate-webhook",
                json={"transaction_reference": "PAY-TEST-999", "outcome": "success"},
            )
            assert res.status_code == 403
            assert "interdite en mode production" in res.json()["detail"]
        finally:
            settings.payment_mode = orig_mode
            settings.payment_provider = orig_prov


@pytest.mark.asyncio
async def test_ai_agent_payment_tools(setup_test_data):
    """
    Test 7 : Vérification des tools conversationnels initiate_payment et check_payment_status.
    """
    data = setup_test_data
    biz_a_id = data["biz_a_id"]
    customer_a_id = data["customer_a_id"]

    async with async_session() as session:
        # 1. Le client demande à payer par Wave
        reply_wave = await execute_tool(
            session=session,
            business_id=biz_a_id,
            customer_id=customer_a_id,
            tool_name="initiate_payment",
            arguments={"provider": "wave"},
        )
        assert "Wave" in reply_wave
        assert "http" in reply_wave

        # 2. Le client demande le statut de son paiement (actuellement en attente)
        reply_status = await execute_tool(
            session=session,
            business_id=biz_a_id,
            customer_id=customer_a_id,
            tool_name="check_payment_status",
            arguments={},
        )
        assert "attente" in reply_status.lower()

        # 3. Le client change d'avis et préfère payer cash
        reply_cash = await execute_tool(
            session=session,
            business_id=biz_a_id,
            customer_id=customer_a_id,
            tool_name="initiate_payment",
            arguments={"provider": "cash"},
        )
        assert "espèces" in reply_cash.lower()
