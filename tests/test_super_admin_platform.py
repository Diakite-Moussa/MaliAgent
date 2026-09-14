"""
Tests de sécurité et fonctionnalités du Super Admin / Cockpit Plateforme
(Section 6.3 et 18 du cahier des charges).
"""

import uuid
import pytest
import pytest_asyncio

from app.core.security import create_access_token, hash_password
from app.db.session import async_session
from app.models import User, UserRole, Business


@pytest_asyncio.fixture
async def super_admin_context():
    """Crée un utilisateur Super Admin dédié pour les tests d'intégration."""
    async with async_session() as session:
        uid = uuid.uuid4().hex[:6]
        super_admin = User(
            email=f"platform_owner_{uid}@maliagent.ml",
            password_hash=hash_password("SuperSecretAdminPass123!"),
            first_name="Owner",
            last_name="Test",
            role=UserRole.SUPER_ADMIN,
            business_id=None,
            is_active=True,
        )
        session.add(super_admin)
        await session.commit()
        await session.refresh(super_admin)

        token = create_access_token(user_id=str(super_admin.id), business_id=None)
        return {
            "user": super_admin,
            "password": "SuperSecretAdminPass123!",
            "token": token,
        }


@pytest.mark.asyncio
async def test_platform_endpoints_reject_unauthenticated(client):
    """Vérifie que les endpoints de gestion de la plateforme rejettent les requêtes sans token (401)."""
    endpoints = [
        ("GET", "/api/platform/stats"),
        ("GET", "/api/platform/businesses"),
        ("POST", "/api/platform/businesses"),
        ("GET", "/api/platform/users"),
        ("POST", "/api/platform/users"),
        ("GET", "/api/platform/health"),
    ]
    for method, path in endpoints:
        resp = await client.request(method, path)
        assert resp.status_code == 401, f"{method} {path} attendait 401 mais a renvoyé {resp.status_code}"


@pytest.mark.asyncio
async def test_merchant_forbidden_on_platform_endpoints(client, two_businesses):
    """
    Vérifie qu'un gérant de boutique régulier (rôle admin/manager) est
    strictement rejeté avec 403 Forbidden sur tous les endpoints plateforme.
    """
    token_merchant = two_businesses["token_a"]
    headers = {"Authorization": f"Bearer {token_merchant}"}

    endpoints = [
        ("GET", "/api/platform/stats"),
        ("GET", "/api/platform/businesses"),
        ("GET", "/api/platform/users"),
        ("GET", "/api/platform/health"),
    ]
    for method, path in endpoints:
        resp = await client.request(method, path, headers=headers)
        assert resp.status_code == 403, (
            f"Un marchand régulier ne doit jamais accéder à {path}. Reçu: {resp.status_code}"
        )
        assert "Super Administrateur" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_super_admin_login_and_stats(client, super_admin_context):
    """Vérifie la connexion d'un super admin et la récupération des statistiques globales."""
    user = super_admin_context["user"]
    pwd = super_admin_context["password"]

    # 1. Login
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": pwd},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert login_data["role"] == "super_admin"
    assert login_data["business_id"] is None
    token = login_data["access_token"]

    # 2. Get platform stats
    headers = {"Authorization": f"Bearer {token}"}
    stats_resp = await client.get("/api/platform/stats", headers=headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()

    assert "businesses" in stats
    assert "orders" in stats
    assert "engagement" in stats
    assert "users_count" in stats
    assert stats["businesses"]["total"] >= 1


@pytest.mark.asyncio
async def test_super_admin_business_lifecycle(client, super_admin_context):
    """
    Vérifie le cycle de vie d'une boutique gérée par le Super Admin:
    - Création d'une nouvelle boutique
    - Liste des boutiques
    - Suspension (désactivation)
    - Réactivation
    """
    token = super_admin_context["token"]
    headers = {"Authorization": f"Bearer {token}"}

    uid = uuid.uuid4().hex[:6]
    biz_name = f"Test Store Automate {uid}"
    biz_phone = f"22365{uid[:6]}"

    # 1. Provisionner une nouvelle boutique
    create_resp = await client.post(
        "/api/platform/businesses",
        headers=headers,
        json={
            "name": biz_name,
            "whatsapp_phone_number": biz_phone,
            "currency": "XOF",
            "support_phone": "22370000000",
            "address": "ACI 2000, Bamako",
        },
    )
    assert create_resp.status_code == 201
    created_biz = create_resp.json()
    assert created_biz["name"] == biz_name
    assert created_biz["is_active"] is True
    biz_id = created_biz["id"]

    # 2. Liste des boutiques
    list_resp = await client.get("/api/platform/businesses", headers=headers)
    assert list_resp.status_code == 200
    businesses = list_resp.json()
    assert any(b["id"] == biz_id for b in businesses)

    # 3. Suspendre la boutique
    patch_resp = await client.patch(
        f"/api/platform/businesses/{biz_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_active"] is False

    # 4. Réactiver la boutique
    reactivate_resp = await client.patch(
        f"/api/platform/businesses/{biz_id}",
        headers=headers,
        json={"is_active": True},
    )
    assert reactivate_resp.status_code == 200
    assert reactivate_resp.json()["is_active"] is True


@pytest.mark.asyncio
async def test_super_admin_user_lifecycle(client, super_admin_context, two_businesses):
    """
    Vérifie la gestion des comptes utilisateurs par le Super Admin:
    - Création d'un nouvel utilisateur rattaché à une boutique
    - Désactivation du compte
    """
    token = super_admin_context["token"]
    headers = {"Authorization": f"Bearer {token}"}
    biz_a = two_businesses["biz_a"]

    uid = uuid.uuid4().hex[:6]
    user_email = f"operator_{uid}@alpha.ml"

    # 1. Créer un utilisateur
    create_resp = await client.post(
        "/api/platform/users",
        headers=headers,
        json={
            "email": user_email,
            "password": "TemporaryPassword123!",
            "first_name": "Modibo",
            "last_name": "Keita",
            "role": "operateur",
            "business_id": str(biz_a.id),
        },
    )
    assert create_resp.status_code == 201
    created_user = create_resp.json()
    assert created_user["email"] == user_email
    assert created_user["role"] == "operateur"
    assert created_user["is_active"] is True
    user_id = created_user["id"]

    # 2. Désactiver l'utilisateur
    patch_resp = await client.patch(
        f"/api/platform/users/{user_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_super_admin_system_health(client, super_admin_context):
    """Vérifie le monitoring technique système pour le Super Admin."""
    token = super_admin_context["token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/platform/health", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "healthy"
    assert "components" in data
    assert data["components"]["database"]["status"] == "connected"
    assert data["components"]["api"]["status"] == "online"


@pytest.mark.asyncio
async def test_super_admin_impersonation_flow(client, super_admin_context, two_businesses):
    """
    Vérifie le mécanisme d'impersonation sécurisé (Section 15):
    - Le Super Admin génère un token temporaire pour inspecter un Business
    - Ce token permet d'accéder aux endpoints privés de ce Business
    - L'action est tracée dans les logs d'audit
    """
    token_admin = super_admin_context["token"]
    biz_a = two_businesses["biz_a"]

    # 1. Demande d'impersonation
    imp_resp = await client.post(
        f"/api/platform/impersonate/{biz_a.id}",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert imp_resp.status_code == 200
    imp_data = imp_resp.json()
    assert "impersonation_token" in imp_data
    assert imp_data["business_id"] == str(biz_a.id)
    assert imp_data["expires_in_minutes"] == 15

    imp_token = imp_data["impersonation_token"]

    # 2. Utilisation du token d'impersonation sur les endpoints commerçant
    merchant_resp = await client.get(
        "/api/dashboard/stats",
        headers={"Authorization": f"Bearer {imp_token}"},
    )
    assert merchant_resp.status_code == 200
    stats = merchant_resp.json()
    assert "kpis" in stats
    assert "business" in stats
    assert stats["business"]["id"] == str(biz_a.id)

    # 3. Vérification de l'inscription dans les logs d'audit
    audit_resp = await client.get(
        "/api/platform/audit-logs?action=IMPERSONATE_BUSINESS",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert len(logs) >= 1
    assert any(l["resource_id"] == str(biz_a.id) for l in logs)


@pytest.mark.asyncio
async def test_super_admin_audit_logs_query(client, super_admin_context):
    """Vérifie la consultation et pagination du journal d'audit."""
    token_admin = super_admin_context["token"]
    headers = {"Authorization": f"Bearer {token_admin}"}

    resp = await client.get("/api/platform/audit-logs?page=1&page_size=10", headers=headers)
    assert resp.status_code == 200
    logs = resp.json()
    assert isinstance(logs, list)

