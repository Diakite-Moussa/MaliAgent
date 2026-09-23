"""
Mock STT Provider pour tests unitaires, développement local et démonstrations.
"""

from app.voice.languages import detect_language
from app.voice.stt.base import STTProvider, TranscriptionResult


class MockSTTProvider(STTProvider):
    """
    Provider STT simulé. Permet d'injecter des transcriptions personnalisées
    ou d'utiliser des transcriptions par défaut sans appel réseau.
    """

    def __init__(self, default_text: str | None = None):
        self.default_text = default_text

    async def transcribe(
        self, audio_bytes: bytes, mime_type: str = "audio/ogg; codecs=opus"
    ) -> TranscriptionResult:
        # Si un texte de test est passé sous forme d'octets UTF-8 préfixés
        if audio_bytes and audio_bytes.startswith(b"MOCK_AUDIO:"):
            raw_text = audio_bytes.decode("utf-8", errors="ignore").replace("MOCK_AUDIO:", "").strip()
            lang = detect_language(raw_text)
            return TranscriptionResult(
                text=raw_text,
                detected_language=lang,
                confidence=0.98,
                duration_seconds=3.5,
            )

        text = self.default_text or "Bonjour, je voudrais savoir si vous avez le Samsung Galaxy A15 en stock ?"
        lang = detect_language(text)
        return TranscriptionResult(
            text=text,
            detected_language=lang,
            confidence=0.95,
            duration_seconds=3.0,
        )
