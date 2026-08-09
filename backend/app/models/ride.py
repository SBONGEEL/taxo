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
    String,
    cast,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode, Currency, RideStatus, VehicleCategory

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
)

# حالات تعني «الكبتن مشغول» — شرط التوزيع في المرحلة 4 يقرأ نفس القائمة
ACTIVE_DRIVER_STATUSES: tuple[RideStatus, ...] = (
    RideStatus.ACCEPTED,
    RideStatus.ARRIVED,
    RideStatus.IN_PROGRESS,
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
        # حارس ضد سباق طلبين متزامنين — الخدمة تفحص أيضاً لترجع رسالة مفهومة
        Index(
            "uq_rides_active_rider",
            "rider_id",
            unique=True,
            postgresql_where=text(_status_in(ACTIVE_RIDER_STATUSES)),
        ),
        Index(
            "uq_rides_active_driver",
            "driver_id",
            unique=True,
            postgresql_where=text(_status_in(ACTIVE_DRIVER_STATUSES)),
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

    # من Mapbox Directions — تُستدعى من الخلفية حصراً (SPEC القسم 2)
    distance_km: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    duration_min: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)

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

    cancelled_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

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

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_RIDER_STATUSES

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<Ride {self.id} ({self.status})>"
