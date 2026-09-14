import sys
import uuid
import pytest
import pytest_asyncio
import httpx

from app.core.asyncio_compat import use_selector_event_loop_on_windows

use_selector_event_loop_on_windows()

from app.core.security import create_access_token, hash_password
from app.db.session import async_session
from app.main import app
from app.models import Business, Customer, Order, OrderItem, OrderStatus, Product, User, UserRole


@pytest_asyncio.fixture
async def two_businesses():
    """
    Crée deux boutiques distinctes (Business A et Business B) avec leurs
    produits et commandes respectifs pour tester l'étanchéité multi-tenant.
    """
    async with async_session() as session:
        uid = uuid.uuid4().hex[:8]
        # Business A
        biz_a = Business(
            name=f"Boutique Alpha {uid}",
            currency="XOF",
            whatsapp_phone_number=f"2237{uid[:7]}",
        )
        # Business B
        biz_b = Business(
            name=f"Boutique Beta {uid}",
            currency="XOF",
            whatsapp_phone_number=f"2238{uid[:7]}",
        )
        session.add_all([biz_a, biz_b])
        await session.flush()

        # Utilisateur A rattaché au Business A
        user_a = User(
            email=f"manager_a_{uuid.uuid4().hex[:6]}@alpha.ml",
            password_hash=hash_password("PassAlpha123!"),
            first_name="Alpha",
            last_name="Manager",
            role=UserRole.ADMIN,
            business_id=biz_a.id,
        )
        # Utilisateur B rattaché au Business B
        user_b = User(
            email=f"manager_b_{uuid.uuid4().hex[:6]}@beta.ml",
            password_hash=hash_password("PassBeta123!"),
            first_name="Beta",
            last_name="Manager",
            role=UserRole.ADMIN,
            business_id=biz_b.id,
        )
        session.add_all([user_a, user_b])

        # Produit A (appartient à A)
        prod_a = Product(
            business_id=biz_a.id,
            name="Produit Exclusif Alpha",
            category="téléphone",
            price=150000,
            stock_quantity=10,
        )
        # Produit B (appartient à B)
        prod_b = Product(
            business_id=biz_b.id,
            name="Produit Exclusif Beta",
            category="accessoire",
            price=25000,
            stock_quantity=5,
        )
        session.add_all([prod_a, prod_b])

        # Client et commande pour A
        client_a = Customer(
            business_id=biz_a.id,
            whatsapp_phone_number=f"2239{uid[:7]}",
            display_name="Client Alpha",
        )
        session.add(client_a)
        await session.flush()

        order_a = Order(
            business_id=biz_a.id,
            customer_id=client_a.id,
            status=OrderStatus.PENDING,
            delivery_address="Hamdallaye ACI",
            delivery_fee=1500,
        )
        session.add(order_a)

        # Client et commande pour B
        client_b = Customer(
            business_id=biz_b.id,
            whatsapp_phone_number=f"2236{uid[:7]}",
            display_name="Client Beta",
        )
        session.add(client_b)
        await session.flush()

        order_b = Order(
            business_id=biz_b.id,
            customer_id=client_b.id,
            status=OrderStatus.PENDING,
            delivery_address="Badalabougou",
            delivery_fee=2000,
        )
        session.add(order_b)

        await session.commit()

        token_a = create_access_token(user_id=str(user_a.id), business_id=str(biz_a.id))
        token_b = create_access_token(user_id=str(user_b.id), business_id=str(biz_b.id))

        return {
            "biz_a": biz_a,
            "biz_b": biz_b,
            "user_a": user_a,
            "user_b": user_b,
            "token_a": token_a,
            "token_b": token_b,
            "prod_a": prod_a,
            "prod_b": prod_b,
            "order_a": order_a,
            "order_b": order_b,
        }


@pytest_asyncio.fixture
async def client():
    """Client HTTP asynchrone pointant vers l'application FastAPI."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
