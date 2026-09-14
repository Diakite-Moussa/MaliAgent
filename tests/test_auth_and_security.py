"""
Tests d'authentification et de sécurité des accès (Section 18 et 25 du cahier des charges).
"""

import pytest
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


@pytest.mark.asyncio
async def test_public_invoices_accessible_without_token(client):
    """
    Vérifie que l'accès aux factures PDF (/invoices/{invoice_number}) reste
    accessible publiquement pour les acheteurs WhatsApp sans compte dashboard.
    """
    # Une facture qui n'existe pas doit renvoyer 404, PAS 401 Unauthorized
    resp = await client.get("/invoices/FAC-INEXISTANTE")
    assert resp.status_code == 404, f"Attendu 404 (non trouvé), reçu {resp.status_code}"
