"""
Tests automatisés pour le Sprint 9 (V2.0 Logistique & Flotte).
Valide :
- Création de mission et génération sécurisée du code secret OTP (6 chiffres).
- Attribution d'une mission à un livreur interne ou partenaire.
- Cloisonnement strict multi-tenant : Business A ne voit ni ne modifie les missions de Business B.
- Gestion des partenaires logistiques.
"""

import uuid
import pytest
from app.db.session import async_session
from app.models import DriverType, User, UserRole


@pytest.mark.asyncio
async def test_create_delivery_mission_and_otp(client, two_businesses):
    token_a = two_businesses["token_a"]
    order_a = two_businesses["order_a"]

    # 1. Création de la mission pour la commande A
    payload = {
        "order_id": str(order_a.id),
        "delivery_address": "Faladié Sokoro, près du goudron",
        "customer_name": "Moussa Diarra",
        "customer_phone": "+22370112233",
        "notes": "Appeler en arrivant",
    }
    resp = await client.post(
        "/api/delivery/missions",
        json=payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 201
    data = resp.json()

    assert data["order_id"] == str(order_a.id)
    assert data["status"] == "pending"
    assert "otp_code" in data
    # Le code OTP doit comporter exactement 6 chiffres
    assert len(data["otp_code"]) == 6
    assert data["otp_code"].isdigit()


@pytest.mark.asyncio
async def test_assign_mission_to_driver(client, two_businesses):
    token_a = two_businesses["token_a"]
    biz_a = two_businesses["biz_a"]
    order_a = two_businesses["order_a"]

    # 1. Créer un livreur interne pour Business A
    async with async_session() as session:
        driver = User(
            business_id=biz_a.id,
            email=f"livreur_{uuid.uuid4().hex[:6]}@alpha.ml",
            password_hash="dummyhash",
            first_name="Bakary",
            last_name="Coulibaly",
            role=UserRole.LIVREUR,
            driver_type=DriverType.INTERNAL,
            phone_number="+22375556677",
            is_available=True,
        )
        session.add(driver)
        await session.commit()
        driver_id = str(driver.id)

    # 2. Créer la mission
    resp_create = await client.post(
        "/api/delivery/missions",
        json={"order_id": str(order_a.id)},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    mission_id = resp_create.json()["id"]

    # 3. Assigner la mission au livreur
    resp_assign = await client.patch(
        f"/api/delivery/missions/{mission_id}/assign",
        json={"assignment_type": "internal", "driver_id": driver_id},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_assign.status_code == 200
    data = resp_assign.json()
    assert data["status"] == "assigned"
    assert data["driver_id"] == driver_id


@pytest.mark.asyncio
async def test_delivery_missions_multi_tenant_isolation(client, two_businesses):
    token_a = two_businesses["token_a"]
    token_b = two_businesses["token_b"]
    order_a = two_businesses["order_a"]

    # 1. Créer une mission pour Business A
    resp_create = await client.post(
        "/api/delivery/missions",
        json={"order_id": str(order_a.id)},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_create.status_code == 201
    mission_a_id = resp_create.json()["id"]

    # 2. Business B tente de lister les missions : ne doit PAS voir la mission de A
    resp_list_b = await client.get(
        "/api/delivery/missions",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_list_b.status_code == 200
    mission_ids_b = [m["id"] for m in resp_list_b.json()["missions"]]
    assert mission_a_id not in mission_ids_b

    # 3. Business B tente d'accéder directement au détail de la mission de A : doit retourner 404
    resp_detail_b = await client.get(
        f"/api/delivery/missions/{mission_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_detail_b.status_code == 404


@pytest.mark.asyncio
async def test_delivery_partners_flow(client, two_businesses):
    token_a = two_businesses["token_a"]

    # 1. Création d'un partenaire logistique
    partner_payload = {
        "name": "Djoliba Flash Livraison",
        "contact_name": "Seydou Keita",
        "phone_number": "+22378889900",
        "address": "Badalabougou Rue 20",
    }
    resp = await client.post(
        "/api/delivery/partners",
        json=partner_payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 201
    partner_data = resp.json()
    assert partner_data["name"] == "Djoliba Flash Livraison"

    # 2. Listing des partenaires
    resp_list = await client.get(
        "/api/delivery/partners",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_list.status_code == 200
    partners = resp_list.json()
    assert any(p["id"] == partner_data["id"] for p in partners)
