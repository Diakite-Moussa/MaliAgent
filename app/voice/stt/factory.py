"""
Factory d'instanciation du Provider STT configuré.
"""

from app.core.config import settings
from app.voice.stt.base import STTProvider
from app.voice.stt.mock import MockSTTProvider
from app.voice.stt.whisper_cloud import WhisperCloudSTTProvider


def get_stt_provider() -> STTProvider:
    provider_name = settings.stt_provider.lower().strip()
    if provider_name in ("whisper", "whisper_cloud", "groq"):
        return WhisperCloudSTTProvider()
    return MockSTTProvider()
