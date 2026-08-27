"""Audio transcription service.

Uses the AI gateway's audio endpoint (Whisper-compatible) when available,
falls back to local faster-whisper for high-volume or offline use.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.services.ai_gateway import AIGatewayError, get_gateway, is_available

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    text: str
    language: str


def _local_available() -> bool:
    try:
        from faster_whisper import WhisperModel  # noqa: F401
        return True
    except ImportError:
        return False


def _local_transcribe(audio_path: str) -> TranscriptionResult:
    from faster_whisper import WhisperModel

    from app.config import get_settings

    settings = get_settings()
    model = WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path, beam_size=5)
    text = " ".join(seg.text.strip() for seg in segments)
    return TranscriptionResult(text=text.strip(), language=info.language or "")


def _gateway_transcribe(audio_path: str) -> TranscriptionResult:
    g = get_gateway()
    text = g.transcribe(audio_path)
    return TranscriptionResult(text=text.strip(), language="")


def transcribe(audio_path: str) -> TranscriptionResult:
    if _local_available():
        try:
            return _local_transcribe(audio_path)
        except Exception as exc:
            logger.warning("local whisper failed: %s — falling back to gateway", exc)
    if is_available():
        try:
            return _gateway_transcribe(audio_path)
        except AIGatewayError as exc:
            logger.warning("gateway transcribe failed: %s", exc)
    return TranscriptionResult(text="", language="")


def is_available() -> bool:
    if _local_available():
        return True
    try:
        return get_gateway().is_available()
    except Exception:
        return False
