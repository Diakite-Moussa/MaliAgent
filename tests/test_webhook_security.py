"""
Tests de sécurité du Webhook WhatsApp (Meta Cloud API).
Vérifie la validation du hub.challenge et le calcul de la signature HMAC-SHA256.
"""

import hashlib
import hmac
import json
import pytest

from app.core.config import settings


@pytest.mark.asyncio
async def test_webhook_verify_token(client):
    """Vérifie le handshake initial de Meta (GET /webhook/whatsapp)."""
    # 1. Mauvais verify token -> 403
    bad_resp = await client.get(
        "/webhook/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "faux_token", "hub.challenge": "12345"},
    )
    assert bad_resp.status_code == 403

    # 2. Bon verify token -> 200 avec le challenge en clair
    good_resp = await client.get(
        "/webhook/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": settings.whatsapp_verify_token,
            "hub.challenge": "challenge_reussi_999",
        },
    )
    assert good_resp.status_code == 200
    assert good_resp.text == "challenge_reussi_999"


@pytest.mark.asyncio
async def test_webhook_signature_verification(client):
    """Vérifie que les requêtes POST non signées ou mal signées sont rejetées 403."""
    payload = json.dumps({"test": "data"}).encode("utf-8")

    # 1. Aucune signature
    resp_no_sig = await client.post("/webhook/whatsapp", content=payload)
    assert resp_no_sig.status_code == 403

    # 2. Signature invalide / altérée
    resp_bad_sig = await client.post(
        "/webhook/whatsapp",
        content=payload,
        headers={"X-Hub-Signature-256": "sha256=mauvaise_signature_fausse"},
    )
    assert resp_bad_sig.status_code == 403

    # 3. Signature HMAC-SHA256 valide
    secret = settings.meta_app_secret or "test_secret"
    valid_sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    
    # Temporairement garantir que settings.meta_app_secret correspond
    orig_secret = settings.meta_app_secret
    settings.meta_app_secret = secret
    try:
        resp_valid = await client.post(
            "/webhook/whatsapp",
            content=payload,
            headers={"X-Hub-Signature-256": f"sha256={valid_sig}"},
        )
        # Ne doit PAS renvoyer 403 (la signature est acceptée)
        assert resp_valid.status_code != 403
    finally:
        settings.meta_app_secret = orig_secret
