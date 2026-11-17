"""Application settings, loaded from environment variables / .env (never hardcoded secrets)."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Tally API"
    environment: str = "development"

    # "mongodb://..." for a real server, or "mongomock://" for an in-memory dev/test database.
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "tally"

    jwt_secret: str = Field(default="", description="Required. Long random string.")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    max_upload_mb: int = 10
    upload_tmp_dir: str = ""  # empty -> OS temp dir
    timezone: str = "Asia/Kolkata"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.jwt_secret or len(settings.jwt_secret) < 32:
        raise RuntimeError(
            "JWT_SECRET must be set (>= 32 chars). Copy backend/.env.example to backend/.env and set it."
        )
    return settings
