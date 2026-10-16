"""
Tests unitaires et d'intégration pour la Priorité 2 :
- Gestion réelle des ruptures partielles (paniers multi-articles et allow_partial)
- Garde-fous anti-hallucination généralisés (cancel_order, create_order, escalate_to_human, generate_invoice)
- Garantie de restauration du stock lors de l'annulation
"""

from decimal import Decimal
import uuid
import pytest
from sqlalchemy import select

from app.agent.orchestrator import run_agent_turn
from app.db.session import async_session
from app.models import Business, Conversation, Customer, Order, OrderItem, OrderStatus, Product
from app.tools.executor import _cancel_order, _create_order, execute_tool


@pytest.fixture
async def setup_catalog_data():
    """Crée un environnement avec une boutique et un catalogue diversifié pour tester les stocks."""
    async with async_session() as session:
        biz = Business(
            name=f"Boutique Stock-{uuid.uuid4().hex[:6]}",
            whatsapp_phone_number=f"+22375{uuid.uuid4().hex[:6]}",
            currency="XOF",
        )
        session.add(biz)
        await session.flush()

        cust = Customer(
            business_id=biz.id,
            whatsapp_phone_number=f"+22376{uuid.uuid4().hex[:6]}",
            display_name="Client Test Stock",
        )
        session.add(cust)
        await session.flush()

        # P1: Stock abondant (10 unités)
        p1 = Product(
            business_id=biz.id,
            name="Chargeur 25W Type-C Original",
            category="Accessoires",
            price=Decimal("12000.00"),
            stock_quantity=10,
        )
        # P2: Stock limité / partiel (2 unités)
        p2 = Product(
            business_id=biz.id,
            name="Écouteurs Sans Fil Pro",
            category="Audio",
            price=Decimal("25000.00"),
            stock_quantity=2,
        )
        # P3: Alternative pour les écouteurs
        p3 = Product(
            business_id=biz.id,
            name="Écouteurs Bluetooth Bass",
            category="Audio",
            price=Decimal("20000.00"),
            stock_quantity=5,
        )
        # P4: Rupture totale (0 unité)
        p4 = Product(
            business_id=biz.id,
            name="Montre Connectée Sport",
            category="Montres",
            price=Decimal("35000.00"),
            stock_quantity=0,
        )
        session.add_all([p1, p2, p3, p4])
        await session.commit()

        return {
            "biz_id": biz.id,
            "cust_id": cust.id,
            "phone": cust.whatsapp_phone_number,
            "p1_id": p1.id,
            "p2_id": p2.id,
            "p3_id": p3.id,
            "p4_id": p4.id,
        }


@pytest.mark.asyncio
async def test_partial_stock_multi_article_report(setup_catalog_data):
    """
    Vérifie qu'un panier multi-articles avec rupture partielle et totale
    renvoie une synthèse complète article par article sans bloquer brutalement.
    """
    data = setup_catalog_data
    biz_id = data["biz_id"]
    cust_id = data["cust_id"]

    async with async_session() as session:
        # Demande : 2x Chargeur (dispo 10), 5x Écouteurs Pro (dispo 2 -> partiel), 1x Montre (dispo 0 -> rupture)
        items = [
            {"product_name": "Chargeur 25W Type-C Original", "quantity": 2},
            {"product_name": "Écouteurs Sans Fil Pro", "quantity": 5},
            {"product_name": "Montre Connectée Sport", "quantity": 1},
        ]

        result = await _create_order(
            session=session,
            business_id=biz_id,
            customer_id=cust_id,
            items=items,
            delivery_address="Hamdallaye ACI 2000",
            delivery_fee=1000,
            allow_partial=False,
        )

        assert "Analyse de disponibilité" in result or "Ruptures partielles" in result
        assert "Articles disponibles immédiatement" in result
        assert "2x Chargeur 25W Type-C Original" in result
        assert "Écouteurs Sans Fil Pro" in result
        assert "2 disponible(s)" in result
        assert "Montre Connectée Sport" in result
        assert "0 unité en stock" in result
        assert "Options possibles" in result


@pytest.mark.asyncio
async def test_partial_stock_allow_partial_execution(setup_catalog_data):
    """
    Vérifie que lorsque allow_partial=True est activé, la commande est validée
    avec les unités réellement disponibles et le stock est correctement décrémenté.
    """
    data = setup_catalog_data
    biz_id = data["biz_id"]
    cust_id = data["cust_id"]

    async with async_session() as session:
        items = [
            {"product_name": "Chargeur 25W Type-C Original", "quantity": 3},  # dispo 10 -> prend 3
            {"product_name": "Écouteurs Sans Fil Pro", "quantity": 5},        # dispo 2 -> prend 2
        ]

        result = await _create_order(
            session=session,
            business_id=biz_id,
            customer_id=cust_id,
            items=items,
            delivery_address="Badalabougou",
            delivery_fee=1500,
            allow_partial=True,
        )

        assert "confirmée et enregistrée avec succès" in result
        assert "Note d'ajustement" in result
        assert "Écouteurs Sans Fil Pro (ajusté à 2 unité(s))" in result

        # Vérification en base de la décrémentation des stocks
        p1 = (await session.execute(select(Product).where(Product.id == data["p1_id"]))).scalar_one()
        p2 = (await session.execute(select(Product).where(Product.id == data["p2_id"]))).scalar_one()

        assert p1.stock_quantity == 7   # 10 - 3
        assert p2.stock_quantity == 0   # 2 - 2 (tout le stock partiel a été pris)


@pytest.mark.asyncio
async def test_guaranteed_stock_restoration_on_cancellation(setup_catalog_data):
    """
    Vérifie la garantie absolue de réapprovisionnement du stock lors de l'annulation d'une commande.
    """
    data = setup_catalog_data
    biz_id = data["biz_id"]
    cust_id = data["cust_id"]

    async with async_session() as session:
        # 1. Passer une commande
        items = [{"product_name": "Chargeur 25W Type-C Original", "quantity": 4}]
        order_msg = await _create_order(
            session=session,
            business_id=biz_id,
            customer_id=cust_id,
            items=items,
            delivery_address="Faladié",
            delivery_fee=1500,
        )
        assert "confirmée et enregistrée" in order_msg

        # Vérifier stock décrémenté
        p1 = (await session.execute(select(Product).where(Product.id == data["p1_id"]))).scalar_one()
        assert p1.stock_quantity == 6  # 10 - 4

        # 2. Annulation de la commande
        cancel_msg = await _cancel_order(
            session=session,
            business_id=biz_id,
            customer_id=cust_id,
            order_ref=None,  # Sélectionne automatiquement la dernière commande active
            reason="Erreur de commande par le client",
        )
        assert "annulée avec succès" in cancel_msg
        assert "remis en stock" in cancel_msg

        # 3. Vérifier réapprovisionnement garanti du stock
        await session.refresh(p1)
        assert p1.stock_quantity == 10  # 6 + 4 = 10


@pytest.mark.asyncio
async def test_guardrail_prevents_unfulfilled_cancellation(setup_catalog_data):
    """
    Vérifie que si un client demande une annulation, le système garantit
    l'appel au tool cancel_order ou l'exécute de manière déterministe.
    """
    data = setup_catalog_data
    biz_id = data["biz_id"]
    phone = data["phone"]

    async with async_session() as session:
        # Créer d'abord une commande en base
        p1 = (await session.execute(select(Product).where(Product.id == data["p1_id"]))).scalar_one()
        cust = (await session.execute(select(Customer).where(Customer.whatsapp_phone_number == phone))).scalar_one()

        order = Order(
            business_id=biz_id,
            customer_id=cust.id,
            delivery_address="ACI 2000",
            delivery_fee=Decimal("1000.00"),
            status=OrderStatus.PENDING,
        )
        session.add(order)
        await session.flush()

        item = OrderItem(
            order_id=order.id,
            product_id=p1.id,
            quantity=2,
            unit_price_snapshot=p1.price,
        )
        p1.stock_quantity -= 2
        session.add(item)
        await session.commit()
        assert p1.stock_quantity == 8

        # Le client demande l'annulation sur WhatsApp
        reply = await run_agent_turn(
            session=session,
            business_id=biz_id,
            user_message="Je souhaite annuler ma commande svp",
            customer_phone_number=phone,
        )

        assert "annul" in reply.lower()

        # Vérifier que la commande en base est bien passée à CANCELLED
        await session.refresh(order)
        assert order.status == OrderStatus.CANCELLED

        # Vérifier que le stock est réapprovisionné (8 + 2 = 10)
        await session.refresh(p1)
        assert p1.stock_quantity == 10
