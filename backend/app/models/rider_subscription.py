"""اشتراكُ الراكب — المشوارُ الثابت (SPEC §٦٣-ج/٦، قرارُ المالك ٢٠٢٦-١٠-٠٧).

**شهرٌ مدفوعٌ مقدّماً بسعر رحلةٍ مجمَّد** — والمالُ عند TAXO يُصرف رحلةً رحلة، **وما لم يُستعمل يعود رصيداً لا نقداً**. **والنقطتان
عددان لا `geography`**: الاشتراكُ لا يُسأل جغرافياً، وما يُسأل هو الحجزُ الذي يُولَّد منه بعموده الجغرافيّ.

**وأيامُ الأسبوع قناعُ بتات** بترتيب `date.weekday()` في بايثون (الإثنين = ١، الأحد = ٦٤) — **رقمٌ واحدٌ لا قائمةٌ تتكرّر فيها الأيام**.
**وأيامُ التعليق قائمةُ تواريخ** (JSONB) — قليلةٌ بحدٍّ من اللوحة، ولا تُسأل إلا من اشتراكها.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Float, ForeignKey, Numeric, SmallInteger, String, Time, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode

ACTIVE = "active"
ENDED = "ended"
CANCELLED = "cancelled"


class RiderSubscription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "rider_subscriptions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'ended', 'cancelled') AND weekdays BETWEEN 1 AND 127 AND rides_total > 0 "
            "AND price_per_ride > 0 AND amount_paid > 0 AND ends_on >= starts_on",
            name="rider_subscription_valid",
        ),
    )

    rider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False)
    pickup_lat: Mapped[float] = mapped_column(Float, nullable=False)
    pickup_lng: Mapped[float] = mapped_column(Float, nullable=False)
    pickup_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dropoff_lat: Mapped[float] = mapped_column(Float, nullable=False)
    dropoff_lng: Mapped[float] = mapped_column(Float, nullable=False)
    dropoff_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    weekdays: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    go_time: Mapped[time] = mapped_column(Time, nullable=False)
    #: وقتُ العودة — و`NULL` مشوارٌ ذهابٌ وحدَه
    return_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    #: **يمتدّ بيومٍ لكلِّ يومٍ يُعلَّق** — التعليقُ يُرحَّل إلى ما بعد آخر يوم
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    #: **سعرُ الرحلة الواحدة مجمَّداً** — لا يتأثّر بالذروة ولا بالمسافة الفعليّة، وعليه العمولةُ كأيِّ أجرة
    price_per_ride: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    rides_total: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    suspended_days: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    #: **الكبتنُ المعتمد** — يصير كذلك بقبوله العرض، ويفكّه الراكبُ أو هو
    driver_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("drivers.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=ACTIVE, server_default=text("'active'"))
    #: **متى رُدّ ما لم يُستعمل** — مرّةً واحدة
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
