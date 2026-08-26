"""Speech-to-text via faster-whisper."""

from dataclasses import dataclass
from functools import lru_cache

from app.config import get_settings


class ModelUnavailableError(RuntimeError):
    pass


@lru_cache
def _get_model():
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ModelUnavailableError(
            "Transcription requires 'faster-whisper' — install backend/requirements.txt to enable this feature."
        ) from exc

    settings = get_settings()
    return WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")


def is_available() -> bool:
    try:
        _get_model()
        return True
    except ModelUnavailableError:
        return False


@dataclass
class TranscriptionResult:
    text: str
    language: str


def transcribe(audio_path: str) -> TranscriptionResult:
    model = _get_model()
    segments, info = model.transcribe(audio_path, beam_size=5)
    text = " ".join(segment.text.strip() for segment in segments)
    return TranscriptionResult(text=text.strip(), language=info.language or "")
