"""
Package MaliAgent Voice & Multilingual (V0.5).
"""

from app.voice.languages import detect_language
from app.voice.stt.base import STTProvider, TranscriptionResult
from app.voice.stt.factory import get_stt_provider
from app.voice.tts.base import AudioResult, TTSProvider
from app.voice.tts.factory import get_tts_provider

__all__ = [
    "detect_language",
    "STTProvider",
    "TranscriptionResult",
    "get_stt_provider",
    "AudioResult",
    "TTSProvider",
    "get_tts_provider",
]
