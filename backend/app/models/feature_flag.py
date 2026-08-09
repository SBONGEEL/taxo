from __future__ import annotations

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode


class FeatureFlag(UUIDMixin, TimestampMixin, Base):
    """مفتاح ميزة لكل دولة — التفعيل من اللوحة بلا نشر كود.

    `feature_key` نص لا ENUM حتى تُضاف مفاتيح المراحل اللاحقة بلا ترحيلة؛
    القيم المسموحة تحرسها `FeatureKey` في طبقة الـ schemas.
    غياب الصف = الميزة معطّلة (لا يُفترض التفعيل أبداً).
    """

    __tablename__ = "feature_flags"
    __table_args__ = (UniqueConstraint("country_code", "feature_key"),)

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, index=True
    )
    feature_key: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<FeatureFlag {self.country_code}/{self.feature_key}={self.enabled}>"
