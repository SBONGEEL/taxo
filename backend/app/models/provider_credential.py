from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode, ProviderKey


class ProviderCredential(UUIDMixin, TimestampMixin, Base):
    """بيانات عقد مزود خارجي — المصدر الوحيد لمفاتيح المزودين (SPEC القسم 15).

    `credentials` مظروف JSONB مشفّر at rest: `{"v": 1, "ciphertext": "..."}`.
    لا يُقرأ إلا عبر `services/providers/credentials.py`، ولا تخرج الحقول السرية
    من الخلفية أبداً — تُقنّع في اللوحة وتُستبعد من `GET /config`.

    `country_code = NULL` يعني عقداً عاماً لكل الدول (مثل Mapbox). الفهرسان
    الجزئيان أدناه يمنعان تكرار عقد لنفس المزود لأن UNIQUE في postgres لا يقيّد
    الصفوف ذات NULL.
    """

    __tablename__ = "provider_credentials"
    __table_args__ = (
        Index(
            "uq_provider_credentials_provider_key_global",
            "provider_key",
            unique=True,
            postgresql_where=text("country_code IS NULL"),
        ),
        Index(
            "uq_provider_credentials_provider_key_country_code",
            "provider_key",
            "country_code",
            unique=True,
            postgresql_where=text("country_code IS NOT NULL"),
        ),
    )

    provider_key: Mapped[ProviderKey] = mapped_column(
        pg_enum(ProviderKey, "provider_key"), nullable=False
    )
    country_code: Mapped[CountryCode | None] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=True
    )
    credentials: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        scope = self.country_code or "global"
        return f"<ProviderCredential {self.provider_key}/{scope} active={self.is_active}>"
