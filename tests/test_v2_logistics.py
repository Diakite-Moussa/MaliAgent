"""
Tests automatisés complets pour le Sprint 10 (V2.0 Logistique & Flotte).
Valide :
1. Le cycle de vie complet du livreur mobile :
   accept -> pickup -> start-route -> location GPS -> validation OTP.
2. La génération des liens de navigation Google Maps & Waze.
3. Le rejet strict d'un code OTP erroné (HTTP 400).
4. La synchronisation automatique du statut de la commande en 'delivered'.
5. L'étanchéité des missions entre livreurs (Driver B ne peut pas modifier la course de Driver A).
6. La page publique de suivi de livraison WhatsApp (/api/delivery/track/{order_id}) sans authentification.
"""

import uuid
import pytest

from app.core.security import create_access_token, hash_password
from app.db.session import async_session
from app.models import DeliveryMission, DriverType, Order, OrderStatus, User, UserRole


@pytest.mark.asyncio
async def test_driver_lifecycle_complete_flow(client, two_businesses):
    biz_a = two_businesses["biz_a"]
    token_a = two_businesses["token_a"]
    order_a = two_businesses["order_a"]

    # 1. Création d'un livreur pour Business A
    async with async_session() as session:
        driver = User(
            business_id=biz_a.id,
            email=f"driver_{uuid.uuid4().hex[:6]}@alpha.ml",
            password_hash=hash_password("Pass123!"),
            first_name="Seydou",
            last_name="Coulibaly",
            role=UserRole.LIVREUR,
            driver_type=DriverType.INTERNAL,
            phone_number="+22370998877",
            is_available=True,
        )
        session.add(driver)
        await session.commit()
        driver_id = driver.id

    driver_token = create_access_token(str(driver_id), str(biz_a.id), role=UserRole.LIVREUR.value)
    driver_headers = {"Authorization": f"Bearer {driver_token}"}

    # 2. Le commerçant crée la mission et l'assigne à Seydou
    resp_create = await client.post(
        "/api/delivery/missions",
        json={
            "order_id": str(order_a.id),
            "driver_id": str(driver_id),
            "delivery_address": "ACI 2000, près de la Place CAN",
            "customer_phone": "+22376112233",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_create.status_code == 201
    mission_data = resp_create.json()
    mission_id = mission_data["id"]
    otp_code = mission_data["otp_code"]

    # 3. Le livreur consulte ses missions
    resp_missions = await client.get("/api/delivery/driver/missions", headers=driver_headers)
    assert resp_missions.status_code == 200
    driver_missions = resp_missions.json()["missions"]
    assert any(m["id"] == mission_id for m in driver_missions)

    # Vérification des liens de navigation GPS (Google Maps & Waze)
    mission_item = next(m for m in driver_missions if m["id"] == mission_id)
    assert "navigation" in mission_item
    assert "google_maps" in mission_item["navigation"]
    assert "waze" in mission_item["navigation"]
    assert "google.com/maps" in mission_item["navigation"]["google_maps"]
    assert "waze.com" in mission_item["navigation"]["waze"]

    # 4. Le livreur accepte la course
    resp_accept = await client.post(
        f"/api/delivery/driver/missions/{mission_id}/accept",
        headers=driver_headers,
    )
    assert resp_accept.status_code == 200
    assert resp_accept.json()["status"] == "assigned"

    # 5. Le livreur récupère le colis en boutique
    resp_pickup = await client.post(
        f"/api/delivery/driver/missions/{mission_id}/pickup",
        headers=driver_headers,
    )
    assert resp_pickup.status_code == 200
    assert resp_pickup.json()["status"] == "picked_up"
    assert "picked_up_at" in resp_pickup.json()

    # 6. Le livreur part en route vers le client
    resp_route = await client.post(
        f"/api/delivery/driver/missions/{mission_id}/start-route",
        headers=driver_headers,
    )
    assert resp_route.status_code == 200
    assert resp_route.json()["status"] == "in_transit"

    # 7. Le livreur envoie sa géolocalisation GPS en direct
    resp_loc = await client.post(
        f"/api/delivery/driver/missions/{mission_id}/location",
        json={"latitude": 12.6392, "longitude": -8.0029},
        headers=driver_headers,
    )
    assert resp_loc.status_code == 200
    assert resp_loc.json()["latitude"] == 12.6392

    # 8. Tentative de validation avec un code OTP erroné -> Rejet 400
    resp_bad_otp = await client.post(
        f"/api/delivery/driver/missions/{mission_id}/verify-otp",
        json={"otp_code": "000000"},
        headers=driver_headers,
    )
    assert resp_bad_otp.status_code == 400
    assert "invalide" in resp_bad_otp.json()["detail"].lower()

    # 9. Validation avec le BON code OTP client
    resp_good_otp = await client.post(
        f"/api/delivery/driver/missions/{mission_id}/verify-otp",
        json={"otp_code": otp_code},
        headers=driver_headers,
    )
    assert resp_good_otp.status_code == 200
    assert resp_good_otp.json()["status"] == "delivered"
    assert resp_good_otp.json()["otp_verified"] is True

    # 10. Vérification que la commande Order est passée en 'delivered'
    async with async_session() as session:
        refreshed_order = await session.get(Order, order_a.id)
        assert refreshed_order.status == OrderStatus.DELIVERED


@pytest.mark.asyncio
async def test_driver_authorization_isolation(client, two_businesses):
    biz_a = two_businesses["biz_a"]
    token_a = two_businesses["token_a"]
    order_a = two_businesses["order_a"]

    # Créer deux livreurs distincts pour Business A
    async with async_session() as session:
        driver_1 = User(
            business_id=biz_a.id,
            email=f"driver1_{uuid.uuid4().hex[:6]}@alpha.ml",
            password_hash="hash",
            first_name="Livreur1",
            last_name="Test",
            role=UserRole.LIVREUR,
        )
        driver_2 = User(
            business_id=biz_a.id,
            email=f"driver2_{uuid.uuid4().hex[:6]}@alpha.ml",
            password_hash="hash",
            first_name="Livreur2",
            last_name="Test",
            role=UserRole.LIVREUR,
        )
        session.add_all([driver_1, driver_2])
        await session.commit()
        d1_id = driver_1.id
        d2_id = driver_2.id

    token_d1 = create_access_token(str(d1_id), str(biz_a.id), role=UserRole.LIVREUR.value)
    token_d2 = create_access_token(str(d2_id), str(biz_a.id), role=UserRole.LIVREUR.value)

    # Mission assignée au Livreur 1
    resp_create = await client.post(
        "/api/delivery/missions",
        json={"order_id": str(order_a.id), "driver_id": str(d1_id)},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    mission_id = resp_create.json()["id"]

    # Livreur 2 tente de valider ou modifier la mission du Livreur 1 -> doit être rejeté 404
    resp_hack = await client.post(
        f"/api/delivery/driver/missions/{mission_id}/pickup",
        headers={"Authorization": f"Bearer {token_d2}"},
    )
    assert resp_hack.status_code == 404


@pytest.mark.asyncio
async def test_public_tracking_endpoint(client, two_businesses):
    token_a = two_businesses["token_a"]
    order_a = two_businesses["order_a"]

    # 1. Créer une mission
    resp_create = await client.post(
        "/api/delivery/missions",
        json={"order_id": str(order_a.id), "delivery_address": "Badalabougou Rue 12"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_create.status_code == 201

    # 2. Accès public en JSON (sans token JWT)
    resp_json = await client.get(f"/api/delivery/track/{order_a.id}?format=json")
    assert resp_json.status_code == 200
    track_data = resp_json.json()
    assert track_data["order_id"] == str(order_a.id)
    assert track_data["status"] == "pending"
    assert track_data["delivery_address"] == "Badalabougou Rue 12"

    # 3. Accès public en HTML (sans token JWT)
    resp_html = await client.get(f"/api/delivery/track/{order_a.id}")
    assert resp_html.status_code == 200
    assert "text/html" in resp_html.headers.get("content-type", "")
    assert "MaliAgent Livraison" in resp_html.text
    assert "Progression de la course" in resp_html.text
