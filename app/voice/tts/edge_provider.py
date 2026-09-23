"""
Provider TTS Neural utilisant Edge-TTS (voix naturelles françaises et multilingues).
"""

import io
import logging
from typing import Any
from app.voice.tts.base import AudioResult, TTSProvider
from app.voice.tts.mock import MockTTSProvider

logger = logging.getLogger("maliagent.voice.tts.edge")


class EdgeTTSProvider(TTSProvider):
    def __init__(self, voice_fr: str = "fr-FR-DeniseNeural", voice_bm: str = "fr-FR-HenriNeural"):
        self.voice_fr = voice_fr
        self.voice_bm = voice_bm
        self._fallback = MockTTSProvider()

    async def synthesize(self, text: str, language: str = "fr") -> AudioResult:
        clean_text = text.strip()
        if not clean_text:
            return await self._fallback.synthesize("Bonjour", language)

        try:
            import edge_tts  # type: ignore[import-not-found, import-untyped]

            voice = self.voice_bm if language == "bm" else self.voice_fr
            communicate: Any = edge_tts.Communicate(clean_text, voice)
            audio_buffer = io.BytesIO()

            async for chunk in communicate.stream():
                if isinstance(chunk, dict) and chunk.get("type") == "audio":
                    data = chunk.get("data")
                    if data:
                        audio_buffer.write(data)

            raw_bytes = audio_buffer.getvalue()
            if raw_bytes:
                return AudioResult(
                    audio_bytes=raw_bytes,
                    mime_type="audio/mpeg",
                    duration_seconds=3.0,
                )
        except ImportError:
            logger.info("edge-tts non installé dans l'environnement, utilisation du fallback.")
        except Exception as e:
            logger.warning("Erreur synthèse Edge-TTS (%s), utilisation du fallback.", e)

        return await self._fallback.synthesize(clean_text, language)
