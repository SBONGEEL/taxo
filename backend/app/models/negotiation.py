"""«تفاوض» على السعر (SPEC §٩٢، `design/NEGOTIATE.md`) — الترحيلة `0142`.

- **`negotiation_settings`** صفٌّ لكلِّ دولة. **والغيابُ مطفأ**: سوقٌ بلا صفٍّ لا تفاوضَ فيه، **والميزةُ تُشحن مطفأة** (§٩٢-ب).
- **`ride_fare_offers`** سجلُّ ما جرى على سعر رحلة: عرضُ الراكب · عرضٌ مقابل · قبول · رفض · انقضاء. **للّوحة ولحدِّ الإساءة**، ولا
  يدخله مالٌ ولا يُحسب منه شيء — **السعرُ المتّفق عليه يُكتب على الرحلة نفسِها** (`rides.negotiated_fare`).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, SmallInteger, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode


class NegotiationSetting(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "negotiation_settings"

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False)
    #: **مطفأٌ افتراضاً** — المالكُ يشعله من اللوحة
    enabled: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    #: **أقلُّ عرضٍ نسبةً من تقدير TAXO** — والأعلى من الحدّين يحكم
    min_percent: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("70"))
    #: **أقلُّ عرضٍ مبلغاً ثابتاً** — فارغٌ = لا حدَّ ثابت
    min_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    driver_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("20"))
    rider_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("20"))
    #: **سقفُ العرض المقابل نسبةً فوق عرض الراكب** — فارغٌ = مطفأ
    max_counter_percent: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    #: **عددُ الكباتن الذين يُجرَّبون** — فارغٌ = محاولاتُ التوزيع القائمة في السوق
    max_drivers: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    #: **الفئاتُ التي يُتاح فيها بمفاتيح `ride_categories`** — فارغةٌ = كلُّها، ولا قائمةُ فئاتٍ ثانية (§٩٢-ب)
    categories: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, default=list, server_default=text("'{}'")
    )

    __table_args__ = (
        UniqueConstraint("country_code", name="negotiation_settings_country"),
        CheckConstraint("min_percent BETWEEN 10 AND 100", name="negotiation_min_percent_range"),
        CheckConstraint("min_amount IS NULL OR min_amount >= 0", name="negotiation_min_amount_non_negative"),
        CheckConstraint("driver_timeout_seconds BETWEEN 5 AND 120", name="negotiation_driver_timeout_range"),
        CheckConstraint("rider_timeout_seconds BETWEEN 5 AND 120", name="negotiation_rider_timeout_range"),
        CheckConstraint(
            "max_counter_percent IS NULL OR max_counter_percent BETWEEN 1 AND 500", name="negotiation_counter_cap_range"
        ),
        CheckConstraint("max_drivers IS NULL OR max_drivers BETWEEN 1 AND 50", name="negotiation_max_drivers_range"),
    )


class RideFareOffer(UUIDMixin, TimestampMixin, Base):
    """**سطرٌ لكلِّ فعلٍ على سعر رحلة** — يُكتب ولا يُعدَّل."""

    __tablename__ = "ride_fare_offers"

    ride_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("rides.id", ondelete="CASCADE"), nullable=False
    )
    #: فارغٌ لعرض الراكب نفسِه
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True
    )
    #: `rider_offer` · `counter` · `driver_accept` · `driver_decline` · `rider_accept` · `rider_reject` · `expired`
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('rider_offer', 'counter', 'driver_accept', 'driver_decline', 'rider_accept', 'rider_reject', 'expired')",
            name="ride_fare_offer_kind",
        ),
        Index("ix_ride_fare_offers_ride_id", "ride_id"),
    )
