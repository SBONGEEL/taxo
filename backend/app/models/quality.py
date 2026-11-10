"""**درجةُ جودة الكبتن** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٣) — الترحيلة `0151`.

* `quality_settings` — لكلِّ دولة: المفتاح، **وأوزانُ المكوّنات الخمسة** (القبول · الإلغاء · التقييم · الشكاوى · الرحلاتُ المكتملة)،
  وكم متراً تقدّمُ الدرجةُ الكاملةُ الكبتنَ في ترتيب التوزيع، وعتبةُ الإنذار.
* `driver_quality_scores` — صفٌّ لكلِّ كبتنٍ في كلِّ يوم (مهمّةٌ يوميّة): الدرجةُ ٠–١٠٠ ومكوّناتُها — **وهو التاريخُ الذي يراه المشرف**.

**لا مالَ هنا.**
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, SmallInteger, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode


class QualitySetting(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "quality_settings"
    __table_args__ = (
        UniqueConstraint("country_code", name="quality_settings_country"),
        CheckConstraint(
            "w_acceptance >= 0 AND w_cancellation >= 0 AND w_rating >= 0 AND w_complaints >= 0 AND w_completed >= 0"
            " AND w_acceptance + w_cancellation + w_rating + w_complaints + w_completed > 0",
            name="quality_weights_valid",
        ),
        CheckConstraint("dispatch_bonus_m BETWEEN 0 AND 1000", name="quality_bonus_range"),
        CheckConstraint("warn_below BETWEEN 0 AND 100", name="quality_warn_range"),
    )

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False)
    #: **مطفأٌ افتراضاً** — الدرجةُ تُحسب وتُرى دائماً، والمفتاحُ يحكم أثرَها في التوزيع والإنذار
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    w_acceptance: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("30"))
    w_cancellation: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("25"))
    w_rating: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("25"))
    w_complaints: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("10"))
    w_completed: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("10"))
    #: كم متراً تقدّمُ الدرجةُ ١٠٠ الكبتنَ في الترتيب (بالنسبة: ٥٠ ⇐ نصفُها) — كخصم المستوى
    dispatch_bonus_m: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("150"))
    #: دونها يصله إنذارٌ بنصائح (مرّةً في الأسبوع)
    warn_below: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("50"))


class DriverQualityScore(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "driver_quality_scores"
    __table_args__ = (
        UniqueConstraint("driver_id", "day", name="driver_quality_scores_day"),
        CheckConstraint("score BETWEEN 0 AND 100", name="driver_quality_score_range"),
    )

    driver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    #: المكوّناتُ ٠…١ والأعدادُ التي بُنيت عليها — ما يراه الكبتنُ «ما يؤثّر فيها»
    components: Mapped[dict] = mapped_column(JSONB, nullable=False)
