from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[3] == جذر المستودع
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """إعدادات التطبيق.

    مصدر الأسرار: متغيرات البيئة أولاً، ثم `.env.local` في جذر المستودع.
    هنا **أسرار البنية التحتية فقط** (DB, Redis, JWT, مفتاح التشفير).
    مفاتيح المزودين الخارجيين مكانها جدول `provider_credentials` (المرحلة 2).
    """

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env.local", REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "TAXO"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://taxo:taxo@localhost:5432/taxo"
    redis_url: str = "redis://localhost:6379/0"
    sql_echo: bool = False

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # تشفير provider_credentials at rest
    credentials_encryption_key: str | None = None

    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 300

    # بثّ الموقع عبر REST: الكبتن يبث كل 3 ثوانٍ (20 في الدقيقة)، والسقف
    # يترك هامشاً لإعادة المحاولة بعد انقطاع (SPEC القسم 10)
    location_rate_limit_requests: int = 30
    location_rate_limit_window_seconds: int = 60

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
    ]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
