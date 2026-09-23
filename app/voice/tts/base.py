"""
Contrat d'interface abstrait pour les providers de Synthèse Vocale (TTS).
"""

from abc import ABC, abstractmethod
from pydantic import BaseModel


class AudioResult(BaseModel):
    audio_bytes: bytes
    mime_type: str = "audio/ogg; codecs=opus"
    duration_seconds: float = 2.0


class TTSProvider(ABC):
    """Interface générique pour tout moteur de Text-To-Speech."""

    @abstractmethod
    async def synthesize(self, text: str, language: str = "fr") -> AudioResult:
        """Convertit le texte en flux audio compatible WhatsApp."""
        pass
