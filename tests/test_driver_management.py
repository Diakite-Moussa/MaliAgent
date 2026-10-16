"""
Tests automatisés pour la gestion complète des livreurs et de la flotte logistique :
1. Création d'un livreur par le commerçant (POST /api/delivery/drivers)
2. Modification des informations et de la disponibilité par le commerçant (PATCH /api/delivery/drivers/{id})
3. Contrôle de disponibilité par le livreur lui-même (PATCH /api/delivery/driver/availability)
4. Bilan d'activité et total cash encaissé du coursier (GET /api/delivery/driver/summary)
5. Désactivation d'un livreur de la flotte (DELETE /api/delivery/drivers/{id})
6. Isolation multi-tenant stricte (Business A ne peut pas modifier un livreur de Business B)
"""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.db.session import async_session
from app.main import app
from app.models import Business, DriverType, Order, OrderStatus, User, UserRole


@pytest.fixture
async def logistics_test_data():
    """Crée deux boutiques distinctes et un livreur."""
    async with async_session() as session:
        biz_a = Business(
            name=f"Boutique Logistique A-{uuid.uuid4().hex[:6]}",
            whatsapp_phone_number=f"+22370{uuid.uuid4().hex[:6]}",
            currency="XOF",
        )
        biz_b = Business(
            name=f"Boutique Logistique B-{uuid.uuid4().hex[:6]}",
            whatsapp_phone_number=f"+22371{uuid.uuid4().hex[:6]}",
            currency="XOF",
        )
        session.add_all([biz_a, biz_b])
        await session.flush()

        # Commerçant A
        merchant_a = User(
            business_id=biz_a.id,
            email=f"merchant_a_{uuid.uuid4().hex[:6]}@test.ml",
            password_hash=hash_password("Pass123!"),
            first_name="Amadou",
            last_name="Diallo",
            role=UserRole.ADMIN,
        )
        # Commerçant B
        merchant_b = User(
            business_id=biz_b.id,
            email=f"merchant_b_{uuid.uuid4().hex[:6]}@test.ml",
            password_hash=hash_password("Pass123!"),
            first_name="Fatou",
            last_name="Traore",
            role=UserRole.ADMIN,
        )
        session.add_all([merchant_a, merchant_b])
        await session.commit()
        await session.refresh(biz_a)
        await session.refresh(biz_b)
        await session.refresh(merchant_a)
        await session.refresh(merchant_b)

        token_a = create_access_token(str(merchant_a.id), str(biz_a.id), role=UserRole.ADMIN.value)
        token_b = create_access_token(str(merchant_b.id), str(biz_b.id), role=UserRole.ADMIN.value)

        return {
            "biz_a": biz_a,
            "biz_b": biz_b,
            "merchant_a": merchant_a,
            "merchant_b": merchant_b,
            "token_a": token_a,
            "token_b": token_b,
        }


@pytest.mark.asyncio
async def test_merchant_driver_crud_flow(logistics_test_data):
    """Vérifie le cycle complet de création, listing, modification et suppression d'un coursier."""
    data = logistics_test_data
    token_a = data["token_a"]
    biz_a = data["biz_a"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Création d'un livreur interne par le commerçant A
        res_create = await client.post(
            "/api/delivery/drivers",
            json={
                "first_name": "Oumar",
                "last_name": "Sanogo",
                "phone_number": "+223 76 54 32 10",
                "email": f"oumar.{uuid.uuid4().hex[:6]}@coursier.ml",
                "driver_type": "internal",
            },
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res_create.status_code == 201
        driver_data = res_create.json()
        driver_id = driver_data["id"]
        assert driver_data["name"] == "Oumar Sanogo"
        assert driver_data["is_available"] is True
        assert "initial_password" in driver_data

        # 2. Vérification dans la liste des livreurs de la boutique A
        res_list = await client.get(
            "/api/delivery/drivers",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res_list.status_code == 200
        drivers = res_list.json()
        assert any(d["id"] == driver_id for d in drivers)

        # 3. Modification par le commerçant (changement disponibilité et nom)
        res_update = await client.patch(
            f"/api/delivery/drivers/{driver_id}",
            json={"first_name": "Oumar Junior", "is_available": False},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res_update.status_code == 200
        updated = res_update.json()
        assert updated["first_name"] == "Oumar Junior"
        assert updated["is_available"] is False

        # 4. Suppression / Désactivation de la flotte (Soft delete)
        res_delete = await client.delete(
            f"/api/delivery/drivers/{driver_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res_delete.status_code == 200
        assert res_delete.json()["status"] == "deleted"

        # 5. Vérifier que le coursier n'apparaît plus dans la liste active
        res_list_after = await client.get(
            "/api/delivery/drivers",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert not any(d["id"] == driver_id for d in res_list_after.json())


@pytest.mark.asyncio
async def test_driver_self_availability_and_summary(logistics_test_data):
    """Vérifie que le livreur peut basculer son statut En service / En pause et consulter son résumé."""
    data = logistics_test_data
    biz_a = data["biz_a"]

    # Créer un livreur en base
    async with async_session() as session:
        driver = User(
            business_id=biz_a.id,
            email=f"driver_self_{uuid.uuid4().hex[:6]}@test.ml",
            password_hash=hash_password("Pass123!"),
            first_name="Moussa",
            last_name="Kone",
            role=UserRole.LIVREUR,
            driver_type=DriverType.INTERNAL,
            phone_number="+22366112233",
            is_available=True,
            is_active=True,
        )
        session.add(driver)
        await session.commit()
        await session.refresh(driver)
        driver_id = driver.id

    driver_token = create_access_token(str(driver_id), str(biz_a.id), role=UserRole.LIVREUR.value)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Le livreur se met en pause
        res_pause = await client.patch(
            "/api/delivery/driver/availability",
            json={"is_available": False},
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert res_pause.status_code == 200
        assert res_pause.json()["is_available"] is False

        # 2. Le livreur consulte son résumé d'activité
        res_summary = await client.get(
            "/api/delivery/driver/summary",
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert res_summary.status_code == 200
        summary = res_summary.json()
        assert summary["driver_name"] == "Moussa Kone"
        assert summary["is_available"] is False
        assert "total_delivered_count" in summary
        assert "total_cash_collected" in summary

        # 3. Le livreur reprend son service
        res_resume = await client.patch(
            "/api/delivery/driver/availability",
            json={"is_available": True},
            headers={"Authorization": f"Bearer {driver_token}"},
        )
        assert res_resume.status_code == 200
        assert res_resume.json()["is_available"] is True


@pytest.mark.asyncio
async def test_driver_isolation_between_businesses(logistics_test_data):
    """Vérifie l'étanchéité multi-tenant : la Boutique B ne peut pas modifier ou supprimer le livreur de la Boutique A."""
    data = logistics_test_data
    token_a = data["token_a"]
    token_b = data["token_b"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Boutique A crée un livreur
        res_create = await client.post(
            "/api/delivery/drivers",
            json={
                "first_name": "Lassana",
                "last_name": "Keita",
                "phone_number": "+223 71 22 33 44",
            },
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res_create.status_code == 201
        driver_id = res_create.json()["id"]

        # 2. Boutique B tente de modifier le livreur de la Boutique A -> 404
        res_hijack = await client.patch(
            f"/api/delivery/drivers/{driver_id}",
            json={"first_name": "Hacked Name"},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert res_hijack.status_code == 404

        # 3. Boutique B tente de supprimer le livreur de la Boutique A -> 404
        res_del_hijack = await client.delete(
            f"/api/delivery/drivers/{driver_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert res_del_hijack.status_code == 404


@pytest.mark.asyncio
async def test_merchant_partner_crud_flow(logistics_test_data):
    """Vérifie l'enregistrement et le listing des partenaires logistiques tiers (avec routes directes et fleet aliases)."""
    data = logistics_test_data
    token_a = data["token_a"]
    token_b = data["token_b"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Boutique A enregistre un partenaire logistique
        res_create = await client.post(
            "/api/delivery/partners",
            json={
                "name": "Bamako Coursiers Express",
                "contact_name": "Ibrahima Coulibaly",
                "phone_number": "+223 70 00 00 00",
                "address": "Quartier du Fleuve, Bamako",
                "notes": "1500 FCFA par course",
            },
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res_create.status_code == 201
        partner_data = res_create.json()
        partner_id = partner_data["id"]
        assert partner_data["name"] == "Bamako Coursiers Express"

        # 2. Vérification dans la liste des partenaires de la boutique A (route standard et alias)
        res_list = await client.get(
            "/api/delivery/partners",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res_list.status_code == 200
        partners = res_list.json()
        assert any(p["id"] == partner_id for p in partners)

        res_list_fleet = await client.get(
            "/api/delivery/fleet/partners",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res_list_fleet.status_code == 200
        assert any(p["id"] == partner_id for p in res_list_fleet.json())

        # 3. Vérification isolation multi-tenant : Boutique B ne voit pas le partenaire de A
        res_list_b = await client.get(
            "/api/delivery/partners",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert res_list_b.status_code == 200
        assert not any(p["id"] == partner_id for p in res_list_b.json())
