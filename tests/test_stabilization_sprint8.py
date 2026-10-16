"""
Tests automatisés pour le Sprint 8 (Stabilisation & Production-Readiness).
Vérifie :
1. La politique de retry avec backoff exponentiel du client WhatsApp Meta.
2. L'absence de retry sur les erreurs 4xx (400, 401).
3. Le diagnostic du Token Manager WhatsApp.
4. L'endpoint de healthcheck enrichi (/health) et ses métriques.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.agent.orchestrator import _extract_photo_payload
from app.whatsapp.client import _is_retryable_whatsapp_error, send_image_message, send_text_message
from app.whatsapp.token_manager import get_token_quick_status, inspect_token


def test_retryable_error_filter():
    """Vérifie le filtrage strict des erreurs éligibles au retry."""
    # Erreurs réseau -> doivent être retentées
    assert _is_retryable_whatsapp_error(httpx.ConnectError("Connection refused")) is True
    assert _is_retryable_whatsapp_error(httpx.TimeoutException("Read timeout")) is True

    # Erreurs serveur 5xx -> doivent être retentées
    resp_500 = httpx.Response(status_code=500, request=httpx.Request("POST", "http://test"))
    assert _is_retryable_whatsapp_error(httpx.HTTPStatusError("Server Error", request=resp_500.request, response=resp_500)) is True

    resp_503 = httpx.Response(status_code=503, request=httpx.Request("POST", "http://test"))
    assert _is_retryable_whatsapp_error(httpx.HTTPStatusError("Service Unavailable", request=resp_503.request, response=resp_503)) is True

    # Erreurs client 4xx -> NE doivent PAS être retentées
    resp_400 = httpx.Response(status_code=400, request=httpx.Request("POST", "http://test"))
    assert _is_retryable_whatsapp_error(httpx.HTTPStatusError("Bad Request", request=resp_400.request, response=resp_400)) is False

    resp_401 = httpx.Response(status_code=401, request=httpx.Request("POST", "http://test"))
    assert _is_retryable_whatsapp_error(httpx.HTTPStatusError("Unauthorized", request=resp_401.request, response=resp_401)) is False


@pytest.mark.asyncio
async def test_whatsapp_retry_on_server_error():
    """Vérifie que send_text_message effectue jusqu'à 3 tentatives sur erreur 503."""
    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        req = httpx.Request("POST", "https://graph.facebook.com")
        if call_count < 3:
            # Échec 503 sur les 2 premiers appels
            resp = httpx.Response(status_code=503, request=req, json={"error": "temporarily_unavailable"})
            raise httpx.HTTPStatusError("Service Unavailable", request=req, response=resp)
        # Succès au 3e appel
        return httpx.Response(status_code=200, request=req, json={"messages": [{"id": "wamid.123"}]})

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        res = await send_text_message("22370001122", "Test message")
        assert res["messages"][0]["id"] == "wamid.123"
        assert call_count == 3, f"Attendu 3 appels après retry, obtenu {call_count}"


@pytest.mark.asyncio
async def test_whatsapp_no_retry_on_client_error():
    """Vérifie qu'une erreur 401 Unauthorized échoue immédiatement au 1er appel sans retry."""
    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        req = httpx.Request("POST", "https://graph.facebook.com")
        resp = httpx.Response(status_code=401, request=req, json={"error": "invalid_token"})
        raise httpx.HTTPStatusError("Unauthorized", request=req, response=resp)

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await send_text_message("22370001122", "Test message")

        assert exc_info.value.response.status_code == 401
        assert call_count == 1, "Une erreur 401 ne doit JAMAIS être retentée"


@pytest.mark.asyncio
async def test_send_image_message_builds_meta_payload():
    """Vérifie le payload image envoyé à l'API Cloud Meta."""
    captured = {}

    async def mock_post(*args, **kwargs):
        captured.update(kwargs)
        request = httpx.Request("POST", "https://graph.facebook.com")
        return httpx.Response(status_code=200, request=request, json={"messages": [{"id": "wamid.image"}]})

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        result = await send_image_message(
            "22370001122",
            "https://cdn.example.test/product.jpg",
            "Produit - 95000 FCFA",
        )

    assert result["messages"][0]["id"] == "wamid.image"
    assert captured["json"] == {
        "messaging_product": "whatsapp",
        "to": "22370001122",
        "type": "image",
        "image": {
            "link": "https://cdn.example.test/product.jpg",
            "caption": "Produit - 95000 FCFA",
        },
    }


def test_extract_photo_payload_removes_machine_marker():
    """Le marqueur photo ne doit jamais parvenir au texte final du LLM."""
    cleaned, payload = _extract_photo_payload(
        '__PHOTO_PAYLOAD__{"url":"https://cdn.example.test/photo.jpg","caption":"Produit"}__END__\n'
        "Photo envoyée."
    )

    assert cleaned == "Photo envoyée."
    assert payload == {"url": "https://cdn.example.test/photo.jpg", "caption": "Produit"}


def test_token_quick_status():
    """Vérifie le diagnostic local du token WhatsApp."""
    status = get_token_quick_status()
    assert isinstance(status, dict)
    assert "configured" in status
    assert "phone_number_id_configured" in status


@pytest.mark.asyncio
async def test_inspect_token_mock():
    """Vérifie l'analyse de debug_token Meta avec un token valide."""
    fake_debug_response = {
        "data": {
            "app_id": "1234567890",
            "type": "USER",
            "is_valid": True,
            "scopes": ["whatsapp_business_messaging"],
            "expires_at": 1800000000,
        }
    }

    async def mock_get(*args, **kwargs):
        req = httpx.Request("GET", "https://graph.facebook.com/debug_token")
        return httpx.Response(status_code=200, request=req, json=fake_debug_response)

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        result = await inspect_token(input_token="EAABtestToken12345")
        assert result["is_valid"] is True
        assert result["status"] == "valid"
        assert result["app_id"] == "1234567890"
        assert "whatsapp_business_messaging" in result["scopes"]


@pytest.mark.asyncio
async def test_enriched_health_endpoint(client):
    """Vérifie le format complet de la route /health enrichie."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] in ["ok", "degraded"]
    assert "version" in data
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], (int, float))

    components = data["components"]
    assert "database" in components
    assert components["database"]["status"] == "connected"
    assert components["database"]["latency_ms"] is not None
    assert isinstance(components["database"]["latency_ms"], (int, float))

    assert "llm_provider" in components
    assert "whatsapp_meta" in components
