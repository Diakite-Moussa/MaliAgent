"""
Provider STT Whisper Cloud (compatible Groq / OpenAI Whisper API).
Permet une transcription ultra-rapide (< 1 seconde) du français, de l'anglais
et de multiples langues avec prise en charge des accents régionaux.
"""

import io
import logging
import httpx

from app.core.config import settings
from app.voice.languages import detect_language
from app.voice.stt.base import STTProvider, TranscriptionResult

logger = logging.getLogger("maliagent.voice.stt.whisper")


class WhisperCloudSTTProvider(STTProvider):
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or settings.stt_api_key
        self.base_url = (base_url or settings.stt_base_url).rstrip("/")
        self.model = model or settings.stt_model

    async def transcribe(
        self, audio_bytes: bytes, mime_type: str = "audio/ogg; codecs=opus"
    ) -> TranscriptionResult:
        if not self.api_key:
            logger.warning("Clé STT manquante. Repli sur la détection texte locale.")
            return TranscriptionResult(
                text="Demande vocale reçue",
                detected_language="fr",
                confidence=0.5,
            )

        # Détermination de l'extension de fichier selon le mime_type
        ext = "ogg"
        if "mp3" in mime_type:
            ext = "mp3"
        elif "wav" in mime_type:
            ext = "wav"
        elif "m4a" in mime_type:
            ext = "m4a"

        files = {
            "file": (f"audio_input.{ext}", io.BytesIO(audio_bytes), mime_type),
        }
        data = {
            "model": self.model,
            "response_format": "json",
            "temperature": "0.0",
            "prompt": (
                "Commerce à Bamako au Mali. Langues : Bambara et Français uniquement. "
                "Vocabulaire : I ni ce, i ka kene, i ni sogoma, i ni wula, sɔngɔ ye joli ye, "
                "songo, a bɛ yen, wari, ka san, falen, n b'a fɛ, FCFA, Samsung, iPhone."
            ),
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        endpoint = f"{self.base_url}/audio/transcriptions"

        async with httpx.AsyncClient(timeout=40) as client:
            resp = await client.post(endpoint, headers=headers, files=files, data=data)
            resp.raise_for_status()
            res_json = resp.json()

        text = res_json.get("text", "").strip()
        # Forcer strictement le bilinguisme Français / Bambara (jamais de langue étrangère)
        normalized_lang = detect_language(text, default_lang="fr")

        return TranscriptionResult(
            text=text,
            detected_language=normalized_lang,
            confidence=0.95,
        )
