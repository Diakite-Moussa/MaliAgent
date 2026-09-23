"""
Tests automatisés du support Vocal & Multilingue (Bambara / Français) — Version V0.5.
Vérifie :
1. La détection linguistique (Français vs Bambara vs Mixte).
2. La transcription audio STT (Speech-To-Text).
3. La synthèse vocale TTS et le streaming audio public sécurisé.
4. L'orchestration bilingue et la mise à jour des préférences client.
5. La réception des notes vocales dans le webhook WhatsApp Meta.
"""

import hashlib
import hmac
import json
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.api.audio import store_outgoing_audio
from app.core.config import settings
from app.db.session import async_session
from app.models import Business, Customer
from app.agent.orchestrator import run_agent_turn
from app.voice.languages import detect_language
from app.voice.stt.mock import MockSTTProvider
from app.voice.tts.mock import MockTTSProvider


def test_language_detection():
    """Vérifie la détection précise du Français et du Bambara."""
    # Français
    assert detect_language("Bonjour, je cherche un chargeur rapide Samsung") == "fr"
    assert detect_language("Combien coûte la livraison pour Lafiabougou ?") == "fr"

    # Bambara
    assert detect_language("I ni ce, Samsung Galaxy A15 sɔngɔ ye joli ye ?") == "bm"
    assert detect_language("I ni sogoma, n b'a fɛ ka san") == "bm"
    assert detect_language("Aw ni baara, wari joli ye ?") == "bm"
    assert detect_language("A bɛ yen wa ?") == "bm"


@pytest.mark.asyncio
async def test_stt_transcription():
    """Vérifie le fonctionnement du provider STT mock avec détection de langue."""
    provider = MockSTTProvider()

    # 1. Audio générique
    res = await provider.transcribe(b"fake_audio_stream")
    assert res.text != ""
    assert res.detected_language == "fr"

    # 2. Audio personnalisé avec Bambara
    custom_bytes = b"MOCK_AUDIO:I ni ce, n b'a fe ka Samsung A15 san"
    res_bm = await provider.transcribe(custom_bytes)
    assert "Samsung A15" in res_bm.text
    assert res_bm.detected_language == "bm"


@pytest.mark.asyncio
async def test_tts_synthesis_and_audio_endpoint(client):
    """Vérifie la synthèse audio TTS et l'endpoint de streaming audio public."""
    tts = MockTTSProvider()
    res = await tts.synthesize("Votre commande a été confirmée avec succès.", language="fr")
    assert len(res.audio_bytes) > 0

    audio_id, public_url = store_outgoing_audio(res.audio_bytes, res.mime_type)
    assert audio_id != ""
    assert f"/api/audio/outgoing/{audio_id}" in public_url

    # Vérification du téléchargement via l'API FastAPI
    resp = await client.get(f"/api/audio/outgoing/{audio_id}")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("audio/")
    assert len(resp.content) == len(res.audio_bytes)

    # 404 sur fichier inexistant
    resp_404 = await client.get("/api/audio/outgoing/fichier_inexistant.ogg")
    assert resp_404.status_code == 404


@pytest.mark.asyncio
async def test_run_agent_turn_with_voice(client):
    """Vérifie que run_agent_turn génère une note vocale et met à jour les préférences client."""
    async with async_session() as session:
        biz = (await session.execute(select(Business))).scalars().first()
        if not biz:
            biz = Business(name="Boutique Test Voice", whatsapp_phone_number="22379998811")
            session.add(biz)
            await session.commit()
            await session.refresh(biz)

        phone = f"2237000{uuid.uuid4().hex[:4]}"
        msg = "Bonjour, avez-vous des écouteurs AirPods en stock ?"

        reply_text, voice_url = await run_agent_turn(
            session=session,
            business_id=biz.id,
            user_message=msg,
            customer_phone_number=phone,
            is_voice=True,
            return_voice_url=True,
        )

        assert reply_text != ""
        assert voice_url is not None
        assert "/api/audio/outgoing/" in voice_url

        # Vérifier en DB que le client a été marqué avec preference voice
        stmt = select(Customer).where(Customer.whatsapp_phone_number == phone)
        cust = (await session.execute(stmt)).scalar_one_or_none()
        assert cust is not None
        assert cust.preferred_channel_type == "voice"
        assert cust.preferred_language == "fr"


@pytest.mark.asyncio
async def test_webhook_audio_message_payload_handling(client):
    """Vérifie que le webhook WhatsApp gère les messages de type 'audio' / note vocale."""
    audio_payload = {
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
                                    "id": f"wamid_voice_{uuid.uuid4()}",
                                    "from": "22366112233",
                                    "timestamp": "1720000000",
                                    "type": "audio",
                                    "audio": {
                                        "id": "media_id_12345",
                                        "mime_type": "audio/ogg; codecs=opus",
                                        "voice": True,
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

    raw_bytes = json.dumps(audio_payload).encode("utf-8")
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
