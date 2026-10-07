"""بين المدن (SPEC §٦٣-ج/٧، قرارُ المالك ٢٠٢٦-١٠-٠٧) — **يُبنى مطفأً، والمالكُ يتحقّق من القانون قبل إشعاله**.

أربعةُ جداول: **المسار** (يضيفه المالكُ بسعري السيارة والمقعد) · **التصريح** (بعد فحص المركبة: ٢٠١٥ فأحدث · ٤ مقاعد · تأمينٌ ساري) ·
**الرحلة** (يعلنها الكبتنُ نفسُه — «سيّدُ نفسه»: ينطلق أو لا، وكم مقعداً، وأقلُّ عددٍ ينطلق به) · **الحجز** (مقاعدُ مدفوعةٌ مقدّماً من
المحفظة، أو السيارةُ كاملةً نقداً). **والأسعارُ تُجمَّد على الرحلة لحظةَ إعلانها ثمّ على الحجز** — تعديلُ المسار يحكم ما يأتي.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Numeric, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode


class IntercityRoute(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "intercity_routes"
    __table_args__ = (CheckConstraint("price_car > 0 AND price_seat > 0", name="intercity_route_prices"),)

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False, index=True)
    from_city: Mapped[str] = mapped_column(String(60), nullable=False)
    to_city: Mapped[str] = mapped_column(String(60), nullable=False)
    #: **نقطتا التجمّع** — يُلتقى فيهما، لا عنوانُ كلِّ راكب
    from_lat: Mapped[float] = mapped_column(Float, nullable=False)
    from_lng: Mapped[float] = mapped_column(Float, nullable=False)
    from_point: Mapped[str] = mapped_column(String(255), nullable=False)
    to_lat: Mapped[float] = mapped_column(Float, nullable=False)
    to_lng: Mapped[float] = mapped_column(Float, nullable=False)
    to_point: Mapped[str] = mapped_column(String(255), nullable=False)
    price_car: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    price_seat: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class IntercityPermit(UUIDMixin, TimestampMixin, Base):
    """**يمنحه مشرفٌ بعد فحص المركبة**، ويسقط وحدَه بانتهاء التأمين، ويُسحب بيده (`revoked_at`) — **لا يُحذف**."""

    __tablename__ = "intercity_permits"
    __table_args__ = (CheckConstraint("seats >= 4", name="intercity_permit_seats"),)

    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False, index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False)
    seats: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    insurance_expires_on: Mapped[date] = mapped_column(Date, nullable=False)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IntercityTrip(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "intercity_trips"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'departed', 'completed', 'cancelled') AND seats_offered BETWEEN 1 AND 8 "
            "AND min_seats BETWEEN 1 AND seats_offered",
            name="intercity_trip_valid",
        ),
    )

    route_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("intercity_routes.id"), nullable=False, index=True)
    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False, index=True)
    departs_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    seats_offered: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    #: **أقلُّ عددٍ ينطلق به — ولو واحداً** (نصُّ المالك)؛ وعند المهلة إن لم يبلغه المحجوزُ تُلغى الرحلةُ بالردّ
    min_seats: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    price_car_at_trip: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    price_seat_at_trip: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    #: **نسبةُ العمولة مجمَّدةً لحظةَ إعلان الرحلة** — وهي لحظةُ «قبول» الكبتن هنا (§25.11)
    commission_percent_at_trip: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open", server_default=text("'open'"))
    departed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)


class IntercityBooking(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "intercity_bookings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('booked', 'cancelled', 'refunded', 'completed') AND seats >= 1 AND amount > 0 "
            "AND payment IN ('wallet', 'cash') AND (whole_car OR payment = 'wallet') AND (NOT whole_car OR payment = 'cash')",
            name="intercity_booking_valid",
        ),
    )

    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("intercity_trips.id", ondelete="CASCADE"), nullable=False, index=True)
    rider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    seats: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    #: **السيارةُ كاملةً نقداً، والمقعدُ من المحفظة** (§٦٣-د/٨) — والقيدُ في القاعدة يحرس الاقتران
    whole_car: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    payment: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="booked", server_default=text("'booked'"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
