"""Unified AI gateway for all forensic analysis tasks.

Routes requests through a single configurable AI provider (default: a free
multi-model gateway) with automatic fallback to local models when the gateway
is unreachable or rate-limited. All capabilities (vision, speech, embeddings,
text reasoning) go through one client so usage is centralized and easy to
meter, swap, or self-host.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class AIGatewayConfig:
    base_url: str = "https://api.omniroute.dev/v1"
    api_key: str = ""
    chat_model: str = "auto"
    vision_model: str = "auto"
    embedding_model: str = "auto"
    audio_model: str = "auto"
    timeout_seconds: float = 60.0
    max_retries: int = 3
    cache_dir: str = "./storage/.ai_cache"
    enabled: bool = True
    fallback_to_local: bool = True
    daily_request_limit: int = 5000  # free-tier safety cap
    extra_headers: dict[str, str] = field(default_factory=dict)


def _load_config() -> AIGatewayConfig:
    settings = get_settings()
    cfg = AIGatewayConfig()
    cfg.api_key = (
        os.environ.get("AI_GATEWAY_API_KEY", "").strip()
        or settings.ai_gateway_api_key
    ).strip()
    cfg.base_url = (
        os.environ.get("AI_GATEWAY_BASE_URL", "").strip()
        or settings.ai_gateway_base_url
    ).strip()
    env_enabled = os.environ.get("AI_GATEWAY_ENABLED", "").strip()
    cfg.enabled = settings.ai_gateway_enabled if env_enabled == "" else env_enabled == "1"
    env_fallback = os.environ.get("AI_FALLBACK_LOCAL", "").strip()
    cfg.fallback_to_local = settings.ai_fallback_local if env_fallback == "" else env_fallback == "1"
    cfg.daily_request_limit = int(os.environ.get("AI_DAILY_LIMIT", "0") or settings.ai_gateway_daily_limit)
    cfg.chat_model = os.environ.get("AI_CHAT_MODEL", "") or settings.ai_gateway_chat_model
    cfg.vision_model = os.environ.get("AI_VISION_MODEL", "") or settings.ai_gateway_vision_model
    cfg.embedding_model = os.environ.get("AI_EMBEDDING_MODEL", "") or settings.ai_gateway_embedding_model
    cfg.audio_model = os.environ.get("AI_AUDIO_MODEL", "") or settings.ai_gateway_audio_model
    cfg.timeout_seconds = settings.ai_gateway_timeout
    cfg.max_retries = settings.ai_gateway_max_retries
    Path(cfg.cache_dir).mkdir(parents=True, exist_ok=True)
    return cfg


# ---------------------------------------------------------------------------
# Lightweight request counter (free-tier safety)
# ---------------------------------------------------------------------------

class _UsageMeter:
    """Per-process rolling daily counter so we never blow past a free quota."""

    def __init__(self, limit: int):
        self.limit = limit
        self.day = time.strftime("%Y-%m-%d")
        self.count = 0
        self._state_file = Path("./storage/.ai_cache/usage.json")

    def _maybe_rollover(self) -> None:
        today = time.strftime("%Y-%m-%d")
        if today != self.day:
            self.day = today
            self.count = 0
            self._persist()

    def _persist(self) -> None:
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(json.dumps({"day": self.day, "count": self.count}))
        except Exception:
            pass

    def can_make_request(self) -> bool:
        self._maybe_rollover()
        return self.count < self.limit

    def record(self) -> None:
        self._maybe_rollover()
        self.count += 1
        self._persist()


# ---------------------------------------------------------------------------
# Gateway client
# ---------------------------------------------------------------------------

class AIGatewayError(RuntimeError):
    pass


class AIGateway:
    """Thin async-friendly sync client over the unified AI provider."""

    def __init__(self, config: AIGatewayConfig | None = None):
        self.config = config or _load_config()
        self.meter = _UsageMeter(self.config.daily_request_limit)
        self._client: httpx.Client | None = None

    # -- lifecycle --------------------------------------------------------

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            for k, v in self.config.extra_headers.items():
                headers[k] = v
            self._client = httpx.Client(
                base_url=self.config.base_url,
                timeout=self.config.timeout_seconds,
                headers=headers,
            )
        return self._client

    def close(self) -> None:
        if self._client and not self._client.is_closed:
            self._client.close()
        self._client = None

    # -- core transport ---------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> dict:
        if not self.config.enabled:
            raise AIGatewayError("AI gateway disabled via AI_GATEWAY_ENABLED=0")
        if not self.config.api_key:
            raise AIGatewayError("AI_GATEWAY_API_KEY is not set")
        if not self.meter.can_make_request():
            raise AIGatewayError("Daily request limit reached for AI gateway")
        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                self.meter.record()
                r = self._get_client().request(method, path, **kwargs)
                if r.status_code == 429:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                if r.status_code >= 500:
                    last_exc = AIGatewayError(f"upstream {r.status_code}: {r.text[:200]}")
                    time.sleep(min(2 ** attempt, 8))
                    continue
                if r.status_code >= 400:
                    raise AIGatewayError(f"upstream {r.status_code}: {r.text[:300]}")
                return r.json() if r.content else {}
            except httpx.HTTPError as exc:
                last_exc = exc
                time.sleep(min(2 ** attempt, 4))
        raise AIGatewayError(f"gateway failed after {self.config.max_retries} attempts: {last_exc}")

    # -- chat / reasoning -------------------------------------------------

    def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model or self.config.chat_model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_format is not None:
            payload["response_format"] = response_format
        resp = self._request("POST", "/chat/completions", json=payload)
        try:
            return resp["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise AIGatewayError(f"unexpected chat response: {resp}") from exc

    # -- embeddings -------------------------------------------------------

    def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        if not texts:
            return []
        resp = self._request(
            "POST",
            "/embeddings",
            json={"model": model or self.config.embedding_model, "input": texts},
        )
        try:
            return [d["embedding"] for d in resp["data"]]
        except KeyError as exc:
            raise AIGatewayError(f"unexpected embedding response: {resp}") from exc

    # -- vision (image -> text) ------------------------------------------

    def vision(
        self,
        *,
        prompt: str,
        image_path: str | None = None,
        image_bytes: bytes | None = None,
        image_url: str | None = None,
        model: str | None = None,
        response_format: dict | None = None,
    ) -> str:
        content: list[dict] = [{"type": "text", "text": prompt}]
        if image_path:
            b = Path(image_path).read_bytes()
            data_url = "data:image/jpeg;base64," + base64.b64encode(b).decode()
            content.append({"type": "image_url", "image_url": {"url": data_url}})
        elif image_bytes is not None:
            data_url = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()
            content.append({"type": "image_url", "image_url": {"url": data_url}})
        elif image_url:
            content.append({"type": "image_url", "image_url": {"url": image_url}})

        messages = [{"role": "user", "content": content}]
        payload: dict[str, Any] = {
            "model": model or self.config.vision_model,
            "messages": messages,
            "temperature": 0.1,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        resp = self._request("POST", "/chat/completions", json=payload)
        try:
            return resp["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise AIGatewayError(f"unexpected vision response: {resp}") from exc

    # -- audio (transcription) -------------------------------------------

    def transcribe(self, audio_path: str, *, language: str | None = None) -> str:
        path = Path(audio_path)
        if not path.exists():
            raise AIGatewayError(f"audio file not found: {audio_path}")
        with path.open("rb") as f:
            files = {"file": (path.name, f, "application/octet-stream")}
            data: dict[str, str] = {"model": self.config.audio_model}
            if language:
                data["language"] = language
            self.meter.record()
            r = self._get_client().post("/audio/transcriptions", files=files, data=data)
        if r.status_code >= 400:
            raise AIGatewayError(f"transcription failed: {r.status_code} {r.text[:200]}")
        try:
            return r.json().get("text", "")
        except ValueError as exc:
            raise AIGatewayError(f"transcription parse error: {r.text[:200]}") from exc

    # -- text-to-speech ---------------------------------------------------

    def synthesize(self, text: str, *, voice: str = "alloy") -> bytes:
        self.meter.record()
        r = self._get_client().post(
            "/audio/speech",
            json={"model": self.config.audio_model, "input": text, "voice": voice},
        )
        if r.status_code >= 400:
            raise AIGatewayError(f"tts failed: {r.status_code} {r.text[:200]}")
        return r.content

    # -- availability -----------------------------------------------------

    def is_available(self) -> bool:
        if not self.config.enabled or not self.config.api_key:
            return False
        try:
            r = self._get_client().get("/models", timeout=5.0)
            return r.status_code < 500
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Module-level singleton + convenience helpers
# ---------------------------------------------------------------------------

_GATEWAY: AIGateway | None = None


def get_gateway() -> AIGateway:
    global _GATEWAY
    if _GATEWAY is None:
        _GATEWAY = AIGateway()
    return _GATEWAY


def is_available() -> bool:
    try:
        return get_gateway().is_available()
    except Exception:
        return False


def reset_for_tests() -> None:
    global _GATEWAY
    if _GATEWAY is not None:
        _GATEWAY.close()
    _GATEWAY = None
