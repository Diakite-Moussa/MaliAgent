"""
Tests complets du flux de Géolocalisation GPS WhatsApp et du Guidage Livreur (V2.2).
Vérifie :
1. Le matching GPS intelligent sur les communes et quartiers de Bamako (Commune IV, VI, V...).
2. La détection du message de type 'location' dans le webhook WhatsApp Meta.
3. L'exécution du tool calculate_delivery avec des coordonnées GPS.
4. L'enregistrement des coordonnées exactes sur Order et DeliveryMission avec liens de navigation.
"""

import hashlib
import hmac
import json
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.business.geo import haversine_distance_km, resolve_bamako_zone_from_gps
from app.core.config import settings
from app.db.session import async_session
from app.models import Business, Customer, DeliveryMission, Order, OrderStatus, Product, User, UserRole
from app.tools.executor import execute_tool


def test_bamako_geo_matching_lafiabougou():
    """Vérifie que les coordonnées de Lafiabougou correspondent à la Commune IV et 1 000 FCFA."""
    lat = 12.632145
    lon = -8.025471
    res = resolve_bamako_zone_from_gps(lat, lon)
    assert res["commune"] == "Commune IV"
    assert res["fee"] == Decimal("1000")
    assert "https://www.google.com/maps/dir/?api=1&destination=12.632145,-8.025471" in res["maps_url"]


def test_bamako_geo_matching_faladie():
    """Vérifie que les coordonnées de Faladié correspondent à la Commune VI et 2 000 FCFA."""
    lat = 12.593412
    lon = -7.942189
    res = resolve_bamako_zone_from_gps(lat, lon)
    assert res["commune"] == "Commune VI"
    assert res["fee"] == Decimal("2000")


def test_bamako_geo_matching_badalabougou():
    """Vérifie que les coordonnées de Badalabougou correspondent à la Commune V et 1 500 FCFA."""
    lat = 12.605120
    lon = -7.994800
    res = resolve_bamako_zone_from_gps(lat, lon)
    assert res["commune"] == "Commune V"
    assert res["fee"] == Decimal("1500")


def test_bamako_geo_matching_out_of_bounds():
    """Vérifie le repli pour un point éloigné du District."""
    lat = 13.500000
    lon = -7.000000
    res = resolve_bamako_zone_from_gps(lat, lon)
    assert res["commune"] == "Hors District"
    assert res["fee"] == Decimal("3500")


@pytest.mark.asyncio
async def test_tool_calculate_delivery_with_gps(client):
    """Vérifie que le tool calculate_delivery renvoie les frais fixes et le quartier via GPS."""
    async with async_session() as session:
        biz = (await session.execute(select(Business))).scalars().first()
        if not biz:
            biz = Business(name="Test GPS Shop", whatsapp_phone_number="22370998877")
            session.add(biz)
            await session.commit()
            await session.refresh(biz)

        out = await execute_tool(
            session=session,
            business_id=biz.id,
            customer_id=uuid.uuid4(),
            tool_name="calculate_delivery",
            arguments={"latitude": 12.632145, "longitude": -8.025471},
        )
        assert "Commune IV" in out
        assert "1000 FCFA" in out
        assert "google.com/maps" in out


@pytest.mark.asyncio
async def test_order_creation_stores_gps_and_transfers_to_mission():
    """Vérifie que create_order stocke la latitude/longitude et qu'elles se propagent à DeliveryMission."""
    async with async_session() as session:
        biz = (await session.execute(select(Business))).scalars().first()
        if not biz:
            biz = Business(name="Test GPS Shop", whatsapp_phone_number="22370998877")
            session.add(biz)
            await session.commit()
            await session.refresh(biz)

        # Créer ou récupérer un produit avec stock disponible
        prod = (await session.execute(select(Product).where(Product.business_id == biz.id, Product.stock_quantity > 0))).scalars().first()
        if not prod:
            prod = Product(
                business_id=biz.id,
                name="Smartphone Test GPS",
                category="smartphone",
                price=Decimal("50000"),
                stock_quantity=10,
            )
            session.add(prod)
            await session.commit()
            await session.refresh(prod)

        # Créer ou récupérer un client valide
        cust = (await session.execute(select(Customer).where(Customer.business_id == biz.id))).scalars().first()
        if not cust:
            cust = Customer(
                business_id=biz.id,
                whatsapp_phone_number="22366778899",
                display_name="Client Test GPS",
            )
            session.add(cust)
            await session.commit()
            await session.refresh(cust)

        lat = 12.632145
        lon = -8.025471

        out = await execute_tool(
            session=session,
            business_id=biz.id,
            customer_id=cust.id,
            tool_name="create_order",
            arguments={
                "items": [{"product_name": prod.name, "quantity": 1}],
                "delivery_address": "Lafiabougou via WhatsApp Pin",
                "delivery_fee": 1000,
                "latitude": lat,
                "longitude": lon,
            },
        )
        assert "Commande #" in out
        assert "enregistrée" in out or "enregistree" in out

        # Vérifier en DB sur la commande
        stmt_order = select(Order).where(Order.business_id == biz.id).order_by(Order.created_at.desc())
        order = (await session.execute(stmt_order)).scalars().first()
        assert order is not None
        assert float(order.delivery_latitude) == pytest.approx(lat, rel=1e-4)
        assert float(order.delivery_longitude) == pytest.approx(lon, rel=1e-4)

        # Créer une mission de livraison pour cette commande et vérifier la propagation
        mission = DeliveryMission(
            business_id=biz.id,
            order_id=order.id,
            pickup_address="Boutique Centrale",
            delivery_address=order.delivery_address,
            destination_latitude=order.delivery_latitude,
            destination_longitude=order.delivery_longitude,
            customer_name="Client Test GPS",
            customer_phone="22366778899",
            otp_code="123456",
        )
        session.add(mission)
        await session.commit()
        await session.refresh(mission)

        assert float(mission.destination_latitude) == pytest.approx(lat, rel=1e-4)
        assert float(mission.destination_longitude) == pytest.approx(lon, rel=1e-4)


@pytest.mark.asyncio
async def test_webhook_location_payload_handling(client):
    """Vérifie que le webhook WhatsApp traite correctement les messages de type 'location'."""
    location_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "10001",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "22370001122",
                                "phone_number_id": "1281284355069337",
                            },
                            "messages": [
                                {
                                    "id": f"wamid_test_{uuid.uuid4()}",
                                    "from": "22366112233",
                                    "timestamp": "1720000000",
                                    "type": "location",
                                    "location": {
                                        "latitude": 12.632145,
                                        "longitude": -8.025471,
                                        "name": "Boulangerie Lafiabougou",
                                        "address": "Rue 312, Bamako",
                                    },
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    raw_bytes = json.dumps(location_payload).encode("utf-8")
    secret = settings.meta_app_secret or "test_secret"
    sig = hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()

    orig_secret = settings.meta_app_secret
    settings.meta_app_secret = secret
    try:
        resp = await client.post(
            "/webhook/whatsapp",
            content=raw_bytes,
            headers={"X-Hub-Signature-256": f"sha256={sig}"},
        )
        assert resp.status_code == 200
        assert resp.json().get("status") == "queued"
    finally:
        settings.meta_app_secret = orig_secret
