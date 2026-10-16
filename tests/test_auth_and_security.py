"""
Tests d'authentification et de sécurité des accès (Section 18 et 25 du cahier des charges).
"""

import pytest
from app.core.config import settings
from app.core.rate_limit import auth_rate_limiter
from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_unauthenticated_requests_rejected(client):
    """Vérifie que les endpoints privés rejettent les requêtes sans Bearer token (401)."""
    endpoints = [
        ("GET", "/api/dashboard/stats"),
        ("GET", "/api/orders"),
        ("GET", "/api/products"),
        ("GET", "/api/dashboard/handoffs"),
        ("GET", "/api/orders/export-csv"),
    ]
    for method, path in endpoints:
        resp = await client.request(method, path)
        assert resp.status_code == 401, f"{method} {path} aurait dû être rejeté avec 401 mais a renvoyé {resp.status_code}"


@pytest.mark.asyncio
async def test_invalid_token_rejected(client):
    """Vérifie qu'un token invalide ou corrompu est rejeté (401)."""
    resp = await client.get(
        "/api/dashboard/stats",
        headers={"Authorization": "Bearer token_completement_invalide_12345"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_flow(client, two_businesses):
    """Vérifie le flux complet de login : rejet des mauvais identifiants et succès."""
    user_a = two_businesses["user_a"]

    # 1. Mauvais mot de passe
    bad_resp = await client.post(
        "/api/auth/login",
        json={"email": user_a.email, "password": "MauvaisMotDePasse!"},
    )
    assert bad_resp.status_code == 401
    assert "detail" in bad_resp.json()

    # 2. Bon mot de passe
    good_resp = await client.post(
        "/api/auth/login",
        json={"email": user_a.email, "password": "PassAlpha123!"},
    )
    assert good_resp.status_code == 200
    data = good_resp.json()
    assert "access_token" in data
    assert data["email"] == user_a.email
    assert data["business_id"] == str(user_a.business_id)

    # Vérifier que le cookie HttpOnly est bien injecté
    set_cookie = good_resp.headers.get("set-cookie", "").lower()
    assert "access_token=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie


@pytest.mark.asyncio
async def test_cookie_authentication_and_session_lifecycle(client, two_businesses):
    """
    Vérifie qu'un client peut s'authentifier UNIQUEMENT via son cookie HttpOnly
    (sans en-tête Authorization: Bearer), consulter /api/auth/me et se déconnecter via /api/auth/logout.
    """
    user_a = two_businesses["user_a"]

    # 1. Connexion pour obtenir le cookie
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": user_a.email, "password": "PassAlpha123!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # 2. Appel d'un endpoint protégé avec cookie uniquement (pas de Bearer header)
    resp_stats = await client.get("/api/dashboard/stats", cookies={"access_token": token})
    assert resp_stats.status_code == 200

    # 3. Appel de /api/auth/me avec le cookie
    resp_me = await client.get("/api/auth/me", cookies={"access_token": token})
    assert resp_me.status_code == 200
    me_data = resp_me.json()
    assert me_data["email"] == user_a.email
    assert me_data["business_id"] == str(user_a.business_id)

    # 4. Déconnexion via /api/auth/logout
    logout_resp = await client.post("/api/auth/logout")
    assert logout_resp.status_code == 200
    set_cookie_logout = logout_resp.headers.get("set-cookie", "")
    # Le cookie doit être supprimé / expiré (Max-Age=0)
    assert "access_token=" in set_cookie_logout or 'max-age=0' in set_cookie_logout.lower()


@pytest.mark.asyncio
async def test_public_invoices_accessible_without_token(client):
    """
    Vérifie que l'accès aux factures PDF (/invoices/{invoice_number}) reste
    accessible publiquement pour les acheteurs WhatsApp sans compte dashboard.
    """
    # Une facture qui n'existe pas doit renvoyer 404, PAS 401 Unauthorized
    resp = await client.get("/invoices/FAC-INEXISTANTE")
    assert resp.status_code == 404, f"Attendu 404 (non trouvé), reçu {resp.status_code}"


@pytest.mark.asyncio
async def test_cookie_secure_attribute_in_production(client, two_businesses):
    """
    Vérifie que l'attribut Secure est activé sur le cookie en production
    et désactivé en développement local.
    """
    user_a = two_businesses["user_a"]

    # 1. Mode Production (ou cookie_secure=True)
    orig_env = settings.env
    orig_cookie_secure = settings.cookie_secure
    try:
        settings.cookie_secure = True
        auth_rate_limiter.reset()

        resp_prod = await client.post(
            "/api/auth/login",
            json={"email": user_a.email, "password": "PassAlpha123!"},
        )
        assert resp_prod.status_code == 200
        set_cookie_prod = resp_prod.headers.get("set-cookie", "")
        assert "secure" in set_cookie_prod.lower(), "L'attribut Secure doit être présent en production"

        # 2. Mode Développement (cookie_secure=False)
        settings.cookie_secure = False
        resp_dev = await client.post(
            "/api/auth/login",
            json={"email": user_a.email, "password": "PassAlpha123!"},
        )
        assert resp_dev.status_code == 200
        set_cookie_dev = resp_dev.headers.get("set-cookie", "")
        # En dev (HTTP), secure ne doit pas être imposé
        cookie_parts = [p.strip().lower() for p in set_cookie_dev.split(";")]
        assert "secure" not in cookie_parts, "L'attribut Secure ne doit pas être imposé en dev local HTTP"

    finally:
        settings.env = orig_env
        settings.cookie_secure = orig_cookie_secure
        auth_rate_limiter.reset()


@pytest.mark.asyncio
async def test_login_rate_limiting_blocks_brute_force(client, two_businesses):
    """
    Vérifie que le rate-limiting applicatif bloque les tentatives de brute-force
    après 5 échecs consécutifs avec un statut HTTP 429 et l'en-tête Retry-After.
    """
    user_a = two_businesses["user_a"]
    auth_rate_limiter.reset()

    try:
        # 5 tentatives infructueuses autorisées (retourne 401)
        for attempt in range(5):
            bad_resp = await client.post(
                "/api/auth/login",
                json={"email": user_a.email, "password": f"FauxMdp{attempt}!"},
            )
            assert bad_resp.status_code == 401, f"La tentative {attempt+1} aurait dû être 401"

        # La 6ème tentative doit être immédiatement bloquée avec 429 Too Many Requests
        blocked_resp = await client.post(
            "/api/auth/login",
            json={"email": user_a.email, "password": "EncoreUnFauxMdp!"},
        )
        assert blocked_resp.status_code == 429
        assert "Retry-After" in blocked_resp.headers
        assert "trop de tentatives" in blocked_resp.json()["detail"].lower()

    finally:
        auth_rate_limiter.reset()

