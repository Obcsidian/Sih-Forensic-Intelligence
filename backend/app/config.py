from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./forensai.db"

    secret_key: str = "demo-insecure-secret-change-me"
    access_token_expire_minutes: int = 480
    algorithm: str = "HS256"

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    storage_dir: str = "./storage"

    whisper_model: str = "small"

    cors_origins: str = "http://localhost:3000"

    # AI Gateway configuration
    ai_gateway_enabled: bool = True
    ai_gateway_api_key: str = ""
    ai_gateway_base_url: str = "https://api.omniroute.dev/v1"
    ai_gateway_chat_model: str = "auto"
    ai_gateway_vision_model: str = "auto"
    ai_gateway_embedding_model: str = "auto"
    ai_gateway_audio_model: str = "auto"
    ai_gateway_timeout: float = 60.0
    ai_gateway_max_retries: int = 3
    ai_gateway_daily_limit: int = 5000
    ai_fallback_local: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def storage_path(self) -> Path:
        p = Path(self.storage_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
