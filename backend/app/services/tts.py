"""Text-to-speech for accessible playback of flagged evidence/case summaries.

Uses pyttsx3 (Windows SAPI5 / macOS NSSpeechSynthesizer / espeak on Linux) —
zero model downloads, works offline out of the box, which matters more for a
live demo than Piper/Coqui's higher voice quality. Piper is a drop-in swap
for production if voice quality matters more than zero-setup reliability.
"""

import uuid
from pathlib import Path

from app.config import get_settings


class ModelUnavailableError(RuntimeError):
    pass


def is_available() -> bool:
    try:
        import pyttsx3  # noqa: F401

        return True
    except ImportError:
        return False


def synthesize(text: str) -> Path:
    try:
        import pyttsx3
    except ImportError as exc:
        raise ModelUnavailableError(
            "Text-to-speech requires 'pyttsx3' — install backend/requirements.txt to enable this feature."
        ) from exc

    settings = get_settings()
    output_dir = settings.storage_path / "tts"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{uuid.uuid4().hex}.wav"

    engine = pyttsx3.init()
    engine.save_to_file(text, str(output_path))
    engine.runAndWait()
    return output_path
