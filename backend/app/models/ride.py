from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from geoalchemy2 import Geography, Geometry
from geoalchemy2.elements import WKTElement
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    cast,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import (
    PromoDiscountType,
    CountryCode,
    Currency,
    GenderPreference,
    RideStatus,
    VehicleCategory,
)

if TYPE_CHECKING:
    from app.models.driver import Driver
    from app.models.user import User

# حالات تعني «للراكب رحلة جارية» — يمنع طلب رحلة ثانية
ACTIVE_RIDER_STATUSES: tuple[RideStatus, ...] = (
    RideStatus.REQUESTED,
    RideStatus.SEARCHING,
    RideStatus.ACCEPTED,
    RideStatus.ARRIVED,
    RideStatus.IN_PROGRESS,
    # الوقوفُ عند محطةٍ رحلةٌ جارية لا فاصلٌ بينها وبين غيرها (المرحلة 12-ب):
    # راكبٌ ينتظر عند محطته لا يطلب رحلةً ثانية، وكبتنٌ واقفٌ لأجله ليس متاحاً
    RideStatus.AT_STOP,
)

# حالات تعني «الكبتن مشغول» — شرط التوزيع في المرحلة 4 يقرأ نفس القائمة
ACTIVE_DRIVER_STATUSES: tuple[RideStatus, ...] = (
    RideStatus.ACCEPTED,
    RideStatus.ARRIVED,
    RideStatus.IN_PROGRESS,
    RideStatus.AT_STOP,
)

# حالات نهائية لا يخرج منها انتقال
TERMINAL_STATUSES: tuple[RideStatus, ...] = (
    RideStatus.COMPLETED,
    RideStatus.CANCELLED_BY_RIDER,
    RideStatus.CANCELLED_BY_DRIVER,
    RideStatus.NO_DRIVER_FOUND,
)

# WGS84 — نفس مرجع الإحداثيات الذي تُرسله الواجهات وتفهمه Mapbox
SRID = 4326


def _point_column() -> Geography:
    """`geography(POINT,4326)`.

    `spatial_index=False`: الاستعلامات الجغرافية اللحظية تمر على Redis GEO
    (SPEC القسم 2)، وهذه الأعمدة للتخزين والتقارير.
    """
    return Geography(geometry_type="POINT", srid=SRID, spatial_index=False)


def _latitude(column: Mapped[str]):
    """خط العرض مقروءاً من عمود geography — الحساب في القاعدة لا في بايثون."""
    return func.ST_Y(cast(column, Geometry(geometry_type="POINT", srid=SRID)))


def _longitude(column: Mapped[str]):
    return func.ST_X(cast(column, Geometry(geometry_type="POINT", srid=SRID)))


def _status_in(statuses: Iterable[RideStatus]) -> str:
    """شرط فهرس جزئي مبني من نفس الثوابت أعلاه حتى لا يفترقا."""
    return "status IN (" + ", ".join(f"'{s.value}'" for s in statuses) + ")"


# مقعدُ الراكب في مجموعة المشاركة: ١ للرحلة الأولى (وكلِّ رحلةٍ منفردة)، و٢
# لشريكها. **وهو ما يحمل الحارسَ، لا `share_group_id`** — انظر `__table_args__`.
SHARE_SEAT_LEAD = 1
SHARE_SEAT_PARTNER = 2


def make_point(lat: float, lng: float) -> WKTElement:
    """نقطة WKT — ترتيبها (خط الطول، خط العرض) عكس ما تُكتب به عادةً."""
    return WKTElement(f"POINT({lng} {lat})", srid=SRID)


class Ride(UUIDMixin, TimestampMixin, Base):
    """رحلة واحدة من الطلب حتى الإنهاء أو الإلغاء (SPEC القسم 4/5).

    `created_at` هو زمن الطلب؛ لكل انتقال حالة بعده عمود زمن خاص به.
    """

    __tablename__ = "rides"
    __table_args__ = (
        CheckConstraint(
            "distance_km >= 0 AND duration_min >= 0 AND estimated_fare >= 0 "
            "AND (final_fare IS NULL OR final_fare >= 0) "
            "AND (cancellation_fee IS NULL OR cancellation_fee >= 0)",
            name="ride_amounts_non_negative",
        ),
        CheckConstraint(
            "commission_percent_at_ride >= 0 AND commission_percent_at_ride <= 100",
            name="ride_commission_percent_range",
        ),
        # قيد مستقل لا توسيعٌ للقيد أعلاه: توسيعه يعني إسقاطه وإعادة إنشائه في
        # الترحيلة على جدولٍ فيه بيانات، والمكسب لا شيء
        CheckConstraint(
            "actual_distance_km IS NULL OR actual_distance_km >= 0",
            name="ride_actual_distance_non_negative",
        ),
        # المقعدُ الثاني لا يوجد بلا مجموعة: شريكٌ بلا من يشاركه تناقضٌ في
        # الحدّ، ولولا هذا القيدُ لأمكن حجزُ المقعد الثاني لرحلةٍ منفردة
        # فيحمل الكبتنُ رحلتين لا تجمعهما مشاركة
        CheckConstraint(
            "share_seat IN (1, 2) AND (share_seat = 1 OR share_group_id IS NOT NULL)",
            name="ride_share_seat_valid",
        ),
        # حارس ضد سباق طلبين متزامنين — الخدمة تفحص أيضاً لترجع رسالة مفهومة
        Index(
            "uq_rides_active_rider",
            "rider_id",
            unique=True,
            postgresql_where=text(_status_in(ACTIVE_RIDER_STATUSES)),
        ),
        # ------------------------------ حارسُ الكبتن بعد المشاركة (12-ي)
        #
        # **المقعدُ هو المفتاح، لا المجموعة.** اقترحت المواصفةُ أولاً
        # `(driver_id, COALESCE(share_group_id, id))`، وقياسُه في
        # `test_ride_sharing_index.py` أظهر أنه **مقلوبٌ تماماً**: يرفض
        # الرحلتين اللتين وُجد ليسمح بهما (مفتاحُهما واحدٌ لأن مجموعتهما
        # واحدة)، ويسمح بما وُجد ليمنعه — رحلتان منفردتان على كبتنٍ واحد
        # (مفتاحُ كلٍّ منهما مُعرِّفُها هي، فيختلفان)، ومجموعتان على كبتنٍ
        # واحد. أي أنه كان **يُلغي الحارسَ الذي جاء ليوسّعه** بلا أن يُسقط
        # اختباراً قائماً واحداً. والتصحيحُ مثبَّتٌ في SPEC §5.12.
        #
        # وما يحرسه هذا الفهرس: **كبتنٌ له مقعدٌ واحدٌ من كلِّ رقم**، أي رحلتان
        # نشطتان على الأكثر. والرحلةُ المنفردة مقعدُها ١ دائماً، فرحلتان
        # منفردتان تتنازعان المقعدَ نفسَه ويسقط الثانية — وهكذا **ينجو الحارسُ
        # القديم بحرفه** بدل أن يُستبدل.
        Index(
            "uq_rides_active_driver",
            "driver_id",
            "share_seat",
            unique=True,
            postgresql_where=text(_status_in(ACTIVE_DRIVER_STATUSES)),
        ),
        # وحدُّ المجموعة نفسِها: راكبان لا أكثر، ولو كانا على كبتنين بخطأ.
        Index(
            "uq_rides_active_share_group",
            "share_group_id",
            "share_seat",
            unique=True,
            postgresql_where=text(
                _status_in(ACTIVE_DRIVER_STATUSES) + " AND share_group_id IS NOT NULL"
            ),
        ),
    )

    rider_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        # RESTRICT لا CASCADE: الرحلة سجل مالي، لا يُمحى بمحو حساب
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # فارغ قبل القبول (SPEC القسم 4)
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # الدولة والفئة تُثبَّتان من حساب الراكب واختياره لحظة الطلب: منهما تُختار
    # تسعيرة `pricing_rules` وتُشتق العملة، فلا يغيّر تعديلٌ لاحقٌ رحلةً قائمة
    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, index=True
    )
    vehicle_category: Mapped[VehicleCategory] = mapped_column(
        pg_enum(VehicleCategory, "vehicle_category"), nullable=False
    )

    pickup_point: Mapped[str] = mapped_column(_point_column(), nullable=False)
    pickup_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dropoff_point: Mapped[str] = mapped_column(_point_column(), nullable=False)
    dropoff_address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[RideStatus] = mapped_column(
        pg_enum(RideStatus, "ride_status"),
        nullable=False,
        default=RideStatus.REQUESTED,
        index=True,
    )

    # موعدُ الحجز الذي وُلدت منه (المرحلة 12-ط) — و`NULL` لرحلةٍ فورية.
    #
    # **تجميدٌ لا بيتٌ ثانٍ** (قرارُ المالك 2026-08-13): الرحلةُ تحمل **ما عُرض
    # على الكبتن**، كما تحمل `commission_percent_at_ride` نسبةً لا تُعاد قراءتُها
    # من الإعدادات. والحجزُ أصلٌ قد يُعدَّل أو يُلغى، والعرضُ الذي قَبِله الكبتن
    # لا يتغيّر بعده.
    #
    # **وسببُه تشغيليٌّ قبل أن يكون معمارياً**: كبتنٌ يصل فيجد الراكبَ غير جاهز
    # يُلغي ويتذمّر — والشارةُ على بطاقة العرض («موعدها ٧:٠٠») تجعله يعرف قبل أن
    # يقبل. وهي تصله بلا استعلامٍ إضافي: إطارُ العرض تسلسلٌ خالصٌ من هذا الصف
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # من Mapbox Directions — تُستدعى من الخلفية حصراً (SPEC القسم 2)
    distance_km: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    duration_min: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)

    # المسافة المقطوعة فعلاً محسوبةً من `ride_route_points` عند الإنهاء
    # (SPEC القسم 5.7). فارغة حين لا يكفي المسار نقطتين — رحلةٌ صمت فيها
    # تطبيق الكبتن لا مسافة فعلية موثوقة لها، فيبقى المقدَّر هو الحكم.
    actual_distance_km: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 3), nullable=True
    )

    estimated_fare: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    final_fare: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    cancellation_fee: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    currency: Mapped[Currency] = mapped_column(
        pg_enum(Currency, "currency"), nullable=False
    )

    # تُجمَّد لحظة الإنشاء ولا يُعاد حسابها بأثر رجعي أبداً (SPEC القسم 4/8)
    commission_percent_at_ride: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )

    # تفضيلُ جنس الكبتن **لهذه الرحلة** — يُنسخ من ملف الراكبة عند الطلب
    # ولا يُقرأ منه بعد ذلك: تغييرُ التفضيل في الملف يحكم الطلب القادم لا
    # طلباً يبحث له عن كبتنٍ الآن (نفس منطق `commission_percent_at_ride`)
    gender_preference: Mapped[GenderPreference] = mapped_column(
        pg_enum(GenderPreference, "gender_preference"),
        nullable=False,
        default=GenderPreference.ANY,
        server_default=GenderPreference.ANY.value,
    )

    # ---------------------------------------- مشاركةُ الرحلة (المرحلة 12-ي)
    #
    # **الشكلُ (ب): رحلتان في مجموعةٍ واحدة** (SPEC القسم 5.12، قرارُ المالك ١):
    # يبقى كلُّ صفِّ رحلةٍ لراكبه بملكيته ودفعته وتقييمه ونزاعه كما هي، ويجمعهما
    # هذا العمود على كبتنٍ واحد. فلا قاعدةَ مالٍ تُعاد كتابتُها، ويبقى «من يملك
    # هذه الرحلة» سؤالاً بجوابٍ واحد — وهو السؤالُ الذي يحرس كلَّ منفذ (القسم 14).
    #
    # و`NULL` تعني **رحلةً منفردة**، وهي الحالُ الغالبة.
    share_group_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True, index=True
    )
    # **المقعدُ هو ما يحرسه الفهرس** لا المجموعة (انظر `__table_args__`):
    # ١ للرحلة الأولى وكلِّ رحلةٍ منفردة، و٢ لشريكها. وافتراضُه ١ يجعل كلَّ
    # صفٍّ قائمٍ في القاعدة صحيحاً بلا ترحيلِ بيانات
    share_seat: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=SHARE_SEAT_LEAD, server_default="1"
    )

    # --- تعدد الوجهات (المرحلة 12-ب) ---
    # عددُ المحطات الوسيطة: عمودٌ لا عدٌّ للجدول، لأنه يُقرأ في كل بطاقة عرضٍ
    # وكل صفٍّ في اللوحة — وعدُّ جدولٍ لكل صفٍّ هو ما تتجنبه بقية القوائم
    stops_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )
    # أيُّ ساقٍ يسير فيها الكبتن الآن، ومنها تُنسب نقاطُ المسار. **كاتبُها
    # واحدٌ لا غير** (`rides.resume_stop` تحت قفل صف الرحلة)
    current_leg: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )
    # أربعةُ حقولِ انتظارٍ مجمَّدةٌ لحظة الإنشاء كالعمولة (SPEC القسم 5.10):
    # مشرفٌ يرفع سعر الدقيقة ورحلةٌ واقفةٌ عند محطةٍ الآن لا يجوز أن يتغيّر
    # عدّادُها تحت عين راكبها
    # ---------------------------------------------- كوبونُ الخصم (12-ز)
    #
    # **القاعدةُ مجمَّدةٌ والمبلغُ لا** (SPEC القسم 6.6): المبلغُ يعتمد على
    # `final_fare` الذي لا يُعرف قبل الإنهاء (يُعاد حسابه على المسافة الفعلية)،
    # فيُحسب مرةً عند الإنهاء ويسكن في **صفِّ دفعة `promo`** — بيتٌ واحدٌ لا
    # بيتان، وقيمةٌ لها بيتان تفترقان (درسُ `waited_minutes` في 12-ب).
    #
    # والتجميدُ كتجميد العمولة: تعديلُ الرمز في اللوحة يحكم ما يأتي بعده لا
    # رحلةً رأى صاحبُها خصمَها على الشاشة قبل أن يطلب.
    promo_code_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("promo_codes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    promo_type_at_ride: Mapped[PromoDiscountType | None] = mapped_column(
        pg_enum(PromoDiscountType, "promo_discount_type"), nullable=True
    )
    promo_value_at_ride: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    promo_cap_at_ride: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)

    stop_fee_at_ride: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.000"), server_default="0"
    )
    stop_free_minutes_at_ride: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )
    stop_price_per_min_at_ride: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.000"), server_default="0"
    )
    # صفرٌ يعني **لا سقف** لا «سقفٌ مقداره صفر» — كصفر حدِّ التحويل
    stop_max_wait_minutes_at_ride: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )

    cancelled_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # سببٌ مصنَّف بجانب النص الحر (`CancelReasonCode`). نصٌّ محروسٌ في طبقة
    # Pydantic لا `ENUM` في القاعدة، كـ`feature_flags.feature_key`
    cancel_reason_code: Mapped[str | None] = mapped_column(String(32), nullable=True)

    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    arrived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # قيم محسوبة لا أعمدة — تُقرأ مع الصف بلا استعلام إضافي
    pickup_lat: Mapped[float] = column_property(_latitude(pickup_point))
    pickup_lng: Mapped[float] = column_property(_longitude(pickup_point))
    dropoff_lat: Mapped[float] = column_property(_latitude(dropoff_point))
    dropoff_lng: Mapped[float] = column_property(_longitude(dropoff_point))

    # `foreign_keys` صريحة: بين rides وdrivers مساران (driver_id و
    # drivers.current_ride_id) فلا يستطيع SQLAlchemy الاختيار وحده
    rider: Mapped["User"] = relationship("User", foreign_keys=[rider_id])
    driver: Mapped["Driver | None"] = relationship("Driver", foreign_keys=[driver_id])
    # المحطاتُ **مرتَّبةً بالترتيب** لا بالإدراج: القراءةُ الوحيدة لها هي
    # «ما هي محطاتُ هذه الرحلة بالتتابع»، وترتيبٌ يُترك للقاعدة يتغيّر
    stops: Mapped[list["RideStop"]] = relationship(
        "RideStop",
        order_by="RideStop.sequence",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_RIDER_STATUSES

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<Ride {self.id} ({self.status})>"


class RideRoutePoint(UUIDMixin, TimestampMixin, Base):
    """نقطة واحدة من المسار الفعلي أثناء `in_progress` (SPEC القسم 5.7).

    هذه هي الاستثناء الوحيد لقاعدة «الموقع اللحظي في Redis وحده»
    (`services/geo.py`): بثّ الكبتن متطايرٌ بعمر ستين ثانية، وله هنا غرضان لا
    يؤديهما المتطاير — المسافة الفعلية التي يُعاد عليها حساب `final_fare`،
    ودليلُ «أين سار ومتى» عند الفصل في نزاع من اللوحة (القسم 13.4).

    لا عمود `recorded_at`: حمولة البث `{lat, lng, heading}` بلا زمن، فزمن
    التسجيل هو `created_at` نفسه — وعمودان لزمنٍ واحد عمودان يفترقان. الترتيب
    الزمني للمسار يمر على الفهرس المركّب أدناه.

    الصف يُكتب ولا يُعدَّل. لا مُشغّل يمنع ذلك كما في دفتر المحفظة: هذه أدلةٌ
    لا قيودٌ مالية، وكلفةُ مُشغّلٍ على جدولٍ يستقبل نقطةً كل عشرين ثانية لكل
    رحلة جارية أعلى من فائدته.
    """

    __tablename__ = "ride_route_points"
    __table_args__ = (
        # المسار يُقرأ دائماً «كل نقاط رحلةٍ مرتّبةً زمنياً» — هذا شكله
        Index("ix_ride_route_points_ride_created", "ride_id", "created_at"),
    )

    ride_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        # RESTRICT كبقية ما يتعلق بالرحلة: دليلُ النزاع لا يُمحى بمحو غيره
        ForeignKey("rides.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    point: Mapped[str] = mapped_column(_point_column(), nullable=False)
    heading: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    # أيُّ ساقٍ من الرحلة (المرحلة 12-ب): صفرٌ من الانطلاق إلى المحطة الأولى،
    # ثم واحدٌ منها إلى التالية. **تُنسخ من `rides.current_leg`** لحظة
    # الالتقاط فلا يعرفها الملتقِط من عنده ولا تُحسب من الصفوف
    leg: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )

    lat: Mapped[float] = column_property(_latitude(point))
    lng: Mapped[float] = column_property(_longitude(point))

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<RideRoutePoint {self.ride_id}>"


# أقصى ما يضيفه الراكب من محطاتٍ **وسيطة**: وجهتان وسيطتان والأخيرة
# `rides.dropoff_point` — أي ثلاثُ وجهاتٍ في الرحلة (SPEC القسم 5.10).
# ثابتُ كودٍ لا إعداد: الرقمُ قاعدةٌ في المواصفة كعدد محاولات التوزيع
MAX_INTERMEDIATE_STOPS = 2


class RideStop(UUIDMixin, TimestampMixin, Base):
    """محطةٌ وسيطة في رحلةٍ متعددة الوجهات (SPEC القسم 5.10، المرحلة 12-ب).

    **الوسيطةُ وحدها هنا**، والوجهةُ الأخيرة تبقى `rides.dropoff_point`: نقلُها
    إلى الجدول يعني إمّا تعديلَ كلِّ ما يقرؤها اليوم (التسعير والتوزيع وبطاقة
    العرض وسجل اللوحة وإطارات المقبس)، وإمّا إبقاءَ العمود **مرآةً** لآخر صفٍّ
    — ومرآةٌ تُكتب في مكانين تفترق يوماً.

    **ونافذةُ الانتظار عمودان لا ثلاثة**: `arrived_at` و`resumed_at`، والمدةُ
    تُشتق منهما. عمودُ `waited_minutes` كان سيصير زمناً ثانياً يفترق عن
    الأول — نفس سبب غياب `recorded_at` عن `ride_route_points`.

    **والزمنُ يُختم هنا لا في الواجهة** (SPEC القسم 14): مؤقتٌ في التطبيق
    يقيس ما تراه شاشةٌ لا ما وقع، ويُحتسب عليه مال.
    """

    __tablename__ = "ride_stops"
    __table_args__ = (
        # ترتيبُ المحطة في الرحلة — والقيدُ يمنع محطتين بنفس الترتيب
        UniqueConstraint("ride_id", "sequence", name="uq_ride_stops_ride_sequence"),
        CheckConstraint(
            f"sequence >= 1 AND sequence <= {MAX_INTERMEDIATE_STOPS}",
            name="ride_stop_sequence_range",
        ),
        # لا استئنافَ قبل وصول: القيدُ يمنع صفّاً يقول «انصرف ولم يصل»
        CheckConstraint(
            "resumed_at IS NULL OR arrived_at IS NOT NULL",
            name="ride_stop_resume_needs_arrival",
        ),
    )

    ride_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        # RESTRICT كبقية ما يتعلق بالرحلة: المحطة جزءٌ من فاتورة
        ForeignKey("rides.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    point: Mapped[str] = mapped_column(_point_column(), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    arrived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # لحظةُ تنبيه الطرفين ببلوغ السقف — **أثرٌ يمنع تكرار التنبيه** في كل
    # دورة كنس (نفس دور مفتاح Redis في تنبيه الاشتراك، وعمودٌ هنا لأن الصفَّ
    # قائمٌ أصلاً فلا يحتاج مفتاحاً ثانياً يعيش خارجه)
    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    lat: Mapped[float] = column_property(_latitude(point))
    lng: Mapped[float] = column_property(_longitude(point))

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<RideStop {self.ride_id}#{self.sequence}>"
