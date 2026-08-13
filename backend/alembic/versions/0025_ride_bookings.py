"""الرحلات المجدولة — جدولُ الحجوزات (SPEC القسم 5.11، المرحلة 12-ط)

جدولٌ واحدٌ وتعدادٌ واحد. **ولا قيمةَ جديدةً على `ride_status`** — وهذا هو القرارُ
المحوريّ مرئياً في الترحيلة: الحجزُ ليس رحلة، فلا حالةَ `scheduled` تُضاف إلى
دورة حياة الرحلة ولا تُعاد بناءُ فهارسِ «الرحلة النشطة الواحدة».

والمفتاحُ `scheduled_rides_enabled` بلا ترحيلة: `feature_flags.feature_key` عمودٌ
نصّيٌّ يحرسه تعدادُ الطبقة العليا (استثناءٌ مقصود في `models/base.py`).
"""

from __future__ import annotations

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # النوعُ يُنشأ صريحاً، **ثم يُشار إليه بـ`create_type=False`** في العمود:
    # بغير الثانية يُصدر `create_table` أمرَ إنشاءٍ ثانياً للنوع نفسِه فتفشل
    # الترقية بـ«type already exists» — نفسُ فخِّ `0003`، ووقع هنا مرةً
    postgresql.ENUM(
        "pending", "dispatched", "missed", "cancelled", name="booking_status"
    ).create(op.get_bind(), checkfirst=True)
    booking_status = postgresql.ENUM(
        "pending",
        "dispatched",
        "missed",
        "cancelled",
        name="booking_status",
        create_type=False,
    )

    op.create_table(
        "ride_bookings",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("rider_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "country_code",
            postgresql.ENUM("LY", "JO", name="country_code", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "pickup_point",
            geoalchemy2.types.Geography(
                geometry_type="POINT", srid=4326, spatial_index=False
            ),
            nullable=False,
        ),
        sa.Column("pickup_address", sa.String(255), nullable=True),
        sa.Column(
            "dropoff_point",
            geoalchemy2.types.Geography(
                geometry_type="POINT", srid=4326, spatial_index=False
            ),
            nullable=False,
        ),
        sa.Column("dropoff_address", sa.String(255), nullable=True),
        sa.Column(
            "vehicle_category",
            postgresql.ENUM(
                "economy", "comfort", name="vehicle_category", create_type=False
            ),
            nullable=False,
        ),
        sa.Column(
            "gender_preference",
            postgresql.ENUM(
                "any", "male", "female", name="gender_preference", create_type=False
            ),
            nullable=False,
        ),
        sa.Column(
            "payment_method_hint",
            postgresql.ENUM(
                "cash",
                "cliq",
                "card",
                "wallet",
                "promo",
                name="payment_method",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", booking_status, nullable=False),
        sa.Column("ride_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("estimated_fare_at_booking", sa.Numeric(12, 3), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["rider_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cancelled_by"], ["users.id"], ondelete="SET NULL"),
        # `SET NULL` لا `CASCADE`: حجزٌ يُمحى لأن رحلتَه مُحيت يمحو أثرَ ما وقع
        sa.ForeignKeyConstraint(["ride_id"], ["rides.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("ride_id"),
        sa.CheckConstraint(
            "(status <> 'dispatched') OR (ride_id IS NOT NULL)",
            name="booking_dispatched_has_ride",
        ),
        sa.CheckConstraint(
            "estimated_fare_at_booking IS NULL OR estimated_fare_at_booking >= 0",
            name="booking_estimate_not_negative",
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ix_ride_bookings_rider_id", "ride_bookings", ["rider_id"], if_not_exists=True
    )
    op.create_index(
        "ix_ride_bookings_scheduled_at",
        "ride_bookings",
        ["scheduled_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_ride_bookings_status", "ride_bookings", ["status"], if_not_exists=True
    )
    # فهرسٌ **جزئيٌّ** لما ينتظر: المهمةُ تسأل كلَّ دقيقة، والجدولُ ينمو بالمنفَّذ
    op.create_index(
        "ix_ride_bookings_due",
        "ride_bookings",
        ["scheduled_at"],
        postgresql_where=sa.text("status = 'pending'"),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_ride_bookings_due", table_name="ride_bookings", if_exists=True)
    op.drop_index("ix_ride_bookings_status", table_name="ride_bookings", if_exists=True)
    op.drop_index(
        "ix_ride_bookings_scheduled_at", table_name="ride_bookings", if_exists=True
    )
    op.drop_index(
        "ix_ride_bookings_rider_id", table_name="ride_bookings", if_exists=True
    )
    op.drop_table("ride_bookings", if_exists=True)
    # postgres لا يحذف نوع ENUM مع جدوله — ومن أنشأه يحذفه (قاعدةُ `0002`)
    op.execute("DROP TYPE IF EXISTS booking_status")
