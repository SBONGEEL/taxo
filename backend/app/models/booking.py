"""الرحلات المجدولة — الحجز (SPEC القسم 5.11، المرحلة 12-ط).

**والحجزُ ليس رحلة، وهذا الملفُّ كلُّه نتيجةُ تلك الجملة** (قرارُ المالك
2026-08-13). صفُّ `rides` يُولد لحظةَ التنفيذ لا لحظةَ الحجز، لأن رحلةً بحالة
`scheduled` تنتظر تكسر ثلاثةَ أشياء قائمة:

1. **`uq_rides_active_rider`** — «رحلةٌ نشطةٌ واحدةٌ لكل راكب» فهرسٌ في القاعدة،
   فحجزٌ لغدٍ يمنع صاحبَه من طلب رحلةٍ اليوم. وهذا وحده يكفي.
2. **`commission_percent_at_ride` مجمَّدةٌ عند الإنشاء** — صفٌّ يُنشأ قبل أسبوع
   يجمّد عمولةً قد تتغيّر مرتين قبل أن يتحرك أحد.
3. **كلُّ قائمةِ حالاتٍ نشطة** وإطارُ المقبس واستعلامُ الأهلية — درسُ `at_stop`:
   قيمةٌ واحدةٌ نُسيت في قائمتين فكذبت الشاشتان.

**ولا عمودَ لنتيجة التنفيذ.** الحالاتُ ثلاثٌ وحدها: `pending` قبل الموعد،
و`dispatched` بعد أن سُلّم إلى التوزيع (وحينها `ride_id` مكتوب)، و`missed` أو
`cancelled`. وما جرى بعد التسليم **تقوله الرحلةُ نفسُها** — فعمودُ `fulfilled` أو
`no_driver` هنا بيتٌ ثانٍ لقيمةٍ لها بيت، ويفترق عنه أولَ مرةٍ يُلغى فيها راكبٌ
رحلةً وُجد لها كبتن. وهي قاعدةُ «لا عمودَ مشتقّاً» التي بُني عليها رصيدُ المحفظة
وحالُ الاشتراك واستحقاقُ الإحالة.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, column_property, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import (
    BookingStatus,
    CountryCode,
    GenderPreference,
    PaymentMethod,
    VehicleCategory,
)
from app.models.ride import _latitude, _longitude, _point_column

# **الحالاتُ التي ما زالت تنتظر تنفيذاً** — منها يُبنى الفهرسُ الجزئي الذي تقرؤه
# المهمةُ الدورية كلَّ دقيقة، فلا تمرّ على حجوزٍ حُسمت.
OPEN_BOOKING_STATUSES: tuple[BookingStatus, ...] = (BookingStatus.PENDING,)


class RideBooking(UUIDMixin, TimestampMixin, Base):
    """حجزُ رحلةٍ لموعدٍ قادم."""

    __tablename__ = "ride_bookings"
    __table_args__ = (
        # **الوصلةُ والحالةُ لا تفترقان**: `dispatched` بلا رحلةٍ يعني حجزاً
        # سُلّم إلى لا شيء، وهو ما لا يستطيع أحدٌ تفسيرَه بعد شهر
        CheckConstraint(
            "(status <> 'dispatched') OR (ride_id IS NOT NULL)",
            name="booking_dispatched_has_ride",
        ),
        CheckConstraint(
            "estimated_fare_at_booking IS NULL OR estimated_fare_at_booking >= 0",
            name="booking_estimate_not_negative",
        ),
        # فهرسٌ جزئيٌّ لما ينتظر: المهمةُ تسأل كلَّ دقيقة، والجدولُ ينمو بالمنفَّذ
        Index(
            "ix_ride_bookings_due",
            "scheduled_at",
            postgresql_where="status = 'pending'",
        ),
    )

    rider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False
    )

    pickup_point: Mapped[str] = mapped_column(_point_column(), nullable=False)
    pickup_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dropoff_point: Mapped[str] = mapped_column(_point_column(), nullable=False)
    dropoff_address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    vehicle_category: Mapped[VehicleCategory] = mapped_column(
        pg_enum(VehicleCategory, "vehicle_category"), nullable=False
    )
    # تفضيلُ الجنس **يُخزَّن كما اختارته**: الخدمةُ قد تُطفأ بين الحجز والتنفيذ،
    # وحينها تُنشأ الرحلةُ بلا تفضيلٍ **ويُبلَّغ صاحبُها** (القسم 5.11) — ولا
    # يُمحى المخزَّن، فهو اختيارُها ويعود إن عادت الخدمة
    gender_preference: Mapped[GenderPreference] = mapped_column(
        pg_enum(GenderPreference, "gender_preference"),
        nullable=False,
        default=GenderPreference.ANY,
    )
    # **تلميحٌ لا التزام**: القنواتُ تُقرأ لحظةَ الدفع من مفاتيح الدولة، وهذا
    # ما تُرسمه شاشةُ التأكيد مسبقاً — كما في الطلب الفوري
    payment_method_hint: Mapped[PaymentMethod | None] = mapped_column(
        pg_enum(PaymentMethod, "payment_method"), nullable=True
    )

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    status: Mapped[BookingStatus] = mapped_column(
        pg_enum(BookingStatus, "booking_status"),
        nullable=False,
        default=BookingStatus.PENDING,
        index=True,
    )

    # الرحلةُ المولودةُ عنه — تُكتب لحظةَ التسليم إلى التوزيع، وبها يُقرأ «ما صار
    # بحجزي» بلا تخمين. و`SET NULL` لا `CASCADE`: حجزٌ يُمحى لأن رحلتَه مُحيت
    # يمحو أثرَ ما وقع فعلاً
    ride_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rides.id", ondelete="SET NULL"), nullable=True, unique=True
    )

    # **اسمُه يقول إنه تقديرٌ لحظةَ الحجز** لا أجرة: التسعيرُ عند التنفيذ (القسم
    # 5.11)، وعمودٌ باسم `fare` يُقرأ التزاماً بعد شهر
    estimated_fare_at_booking: Mapped[Decimal | None] = mapped_column(
        MONEY, nullable=True
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # أثرُ الإبلاغ عن تخطٍّ أو عن تفضيلٍ لم يُنفَّذ — يمنع تكرارَه في كل دورة.
    # عمودٌ لا مفتاحُ Redis (كتنبيه الاشتراك) لأن الصفَّ قائمٌ أصلاً
    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    pickup_lat: Mapped[float] = column_property(_latitude(pickup_point))
    pickup_lng: Mapped[float] = column_property(_longitude(pickup_point))
    dropoff_lat: Mapped[float] = column_property(_latitude(dropoff_point))
    dropoff_lng: Mapped[float] = column_property(_longitude(dropoff_point))

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<RideBooking {self.id} ({self.status}) @{self.scheduled_at}>"
