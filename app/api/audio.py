"""
Endpoints et gestionnaire de fichiers audio pour les notes vocales WhatsApp.
Permet à WhatsApp de streamer et télécharger les notes vocales générées par l'agent IA.
"""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse

from app.core.config import settings

router = APIRouter(prefix="/api/audio", tags=["Audio & Voice"])

AUDIO_DIR = Path(settings.audio_storage_dir) / "outgoing"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def store_outgoing_audio(audio_bytes: bytes, mime_type: str = "audio/ogg; codecs=opus") -> tuple[str, str]:
    """
    Sauvegarde un flux audio généré par le TTS et génère son URL publique de streaming.
    Retourne:
        tuple (audio_id, public_url)
    """
    ext = "ogg"
    if "mp3" in mime_type or "mpeg" in mime_type:
        ext = "mp3"
    elif "wav" in mime_type:
        ext = "wav"

    audio_id = f"{uuid.uuid4()}.{ext}"
    file_path = AUDIO_DIR / audio_id

    with open(file_path, "wb") as f:
        f.write(audio_bytes)

    # Nettoyage préventif des anciens fichiers audio (> 48h)
    cleanup_old_audio_files(max_age_hours=48)

    public_base = settings.public_base_url.rstrip("/")
    public_url = f"{public_base}/api/audio/outgoing/{audio_id}"
    return audio_id, public_url


def cleanup_old_audio_files(max_age_hours: int = 48) -> int:
    """
    Purge les fichiers audio envoyés il y a plus de max_age_hours (WhatsApp les télécharge immédiatement).
    Garantit l'absence de saturation disque en production.
    """
    import time
    deleted_count = 0
    cutoff = time.time() - (max_age_hours * 3600)
    try:
        for audio_file in AUDIO_DIR.iterdir():
            if audio_file.is_file() and audio_file.stat().st_mtime < cutoff:
                try:
                    audio_file.unlink()
                    deleted_count += 1
                except OSError:
                    pass
    except Exception:
        pass
    return deleted_count



@router.get("/outgoing/{filename}")
async def get_outgoing_audio(filename: str):
    """
    Sert les fichiers audio vocaux de manière sécurisée aux serveurs Meta WhatsApp et aux clients.
    """
    # Protection path traversal
    safe_name = os.path.basename(filename)
    file_path = AUDIO_DIR / safe_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fichier audio introuvable")

    media_type = "audio/ogg; codecs=opus"
    if safe_name.endswith(".mp3") or safe_name.endswith(".mpeg"):
        media_type = "audio/mpeg"
    elif safe_name.endswith(".wav"):
        media_type = "audio/wav"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=86400",
        },
    )
