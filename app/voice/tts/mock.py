"""
Mock TTS Provider pour tests unitaires et développement hors-ligne.
"""

from app.voice.tts.base import AudioResult, TTSProvider

# En-tête binaire minimal OGG/Opus simulé pour tests
MINIMAL_OGG_STUB = (
    b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x01\x13OpusHead\x01\x01\x00\x00\x80\xbb\x00\x00\x00"
    b"\x00\x00MOCK_AUDIO_RESPONSE"
)


class MockTTSProvider(TTSProvider):
    """Génère un flux audio simulé pour les tests automatisés."""

    async def synthesize(self, text: str, language: str = "fr") -> AudioResult:
        # Encodage du texte dans le stub audio simulé
        payload = MINIMAL_OGG_STUB + b":" + text.encode("utf-8")
        return AudioResult(
            audio_bytes=payload,
            mime_type="audio/ogg; codecs=opus",
            duration_seconds=2.5,
        )
