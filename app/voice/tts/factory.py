"""
Factory d'instanciation du Provider TTS configuré.
"""

from app.core.config import settings
from app.voice.tts.base import TTSProvider
from app.voice.tts.edge_provider import EdgeTTSProvider
from app.voice.tts.mock import MockTTSProvider


def get_tts_provider() -> TTSProvider:
    provider_name = settings.tts_provider.lower().strip()
    if provider_name in ("edge", "neural"):
        return EdgeTTSProvider()
    return MockTTSProvider()
