"""
Contrat d'interface abstrait pour les providers de Transcription Vocale (STT).
"""

from abc import ABC, abstractmethod
from pydantic import BaseModel


class TranscriptionResult(BaseModel):
    text: str
    detected_language: str = "fr"  # "fr", "bm", "en"
    confidence: float = 1.0
    duration_seconds: float | None = None


class STTProvider(ABC):
    """Interface générique pour tout moteur de Speech-To-Text."""

    @abstractmethod
    async def transcribe(
        self, audio_bytes: bytes, mime_type: str = "audio/ogg; codecs=opus"
    ) -> TranscriptionResult:
        """Transcrit le flux audio binaire en texte avec détection de la langue."""
        pass
