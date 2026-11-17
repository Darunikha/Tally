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

    # Public URL of the frontend - used to build links in emails (reset password, verify email).
    frontend_url: str = "http://localhost:5173"

    # Email delivery: "console" (dev: prints to the server console), "resend", "smtp", or "memory" (tests).
    email_provider: str = "console"
    email_from: str = "Tally <no-reply@example.com>"
    resend_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True

    # Require a verified email before statements can be uploaded (recommended in production).
    require_email_verification: bool = False
    password_reset_minutes: int = 30
    email_verify_hours: int = 48

    # Rate limiting (stored in MongoDB so limits hold across server instances).
    rate_limit_enabled: bool = True
    # Behind a reverse proxy (Render, Nginx...) set true so the client IP comes from X-Forwarded-For.
    trust_proxy_headers: bool = False

    # Bump when the Privacy Policy / Terms change materially; stored with each user's consent.
    legal_version: str = "2026-11-17"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in ("production", "prod")

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
