"""بين المدن (SPEC §٦٣-ج/٧) — مساراتٌ من اللوحة، وتصاريحُ بعد فحص المركبة، ورحلاتٌ يعلنها الكبتن، وحجوزُ مقاعدَ مدفوعةٌ مقدّماً.

**ثلاثةُ أنواعٍ في الدفتر**: `intercity_hold` (مدينٌ على الراكب بلا دائن — المالُ عند TAXO) · `intercity_refund` (يعود كاملاً) ·
`intercity_earning` (يصل الكبتنَ عند الإنهاء، **وعليه العمولة** بقيدها القائم)؛ **ومصدرٌ ثانٍ للدَّين** (`intercity_commission`) لعمولة
ما قبضه نقداً. **ومعها إعادةُ بناء قيد الإشارة.**

**والمهلةُ اقتراحي ساعتان** (`service_settings.intercity_cancel_deadline_hours`). **ولا جدولَ مالٍ قائمٌ يُمسّ.** **و`downgrade` مقيسٌ
لا مقروء**: قيمُ التعداد لا تُنزع، **وقيدٌ بنوعٍ جديدٍ يُسقط التراجع** — مالٌ محفوظٌ لحجزٍ قائمٍ لا يُمحى أثرُه.

Revision ID: 0096
Revises: 0095
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0096"
down_revision = "0095"
branch_labels = None
depends_on = None

CREDITS = (
    "topup", "ride_earning", "transfer_in", "refund", "tip", "referral_bonus", "advance",
    "cancellation_compensation", "guarantee_fee", "guarantee_refund", "guarantee_compensation",
    "commute_credit", "commute_incentive",
)
DEBITS = (
    "ride_payment", "commission", "transfer_out", "withdrawal", "subscription_payment", "tip_payment",
    "advance_repayment", "cancellation_fee", "skin_purchase", "guarantee_hold", "guarantee_penalty", "commute_prepay",
)
NEW_CREDITS = ("intercity_refund", "intercity_earning")
NEW_DEBITS = ("intercity_hold",)
COUNTRY = postgresql.ENUM("LY", "JO", name="country_code", create_type=False)


def _sign_constraint(credits: tuple[str, ...], debits: tuple[str, ...]) -> str:
    def listed(values: tuple[str, ...]) -> str:
        return ", ".join(f"'{value}'" for value in values)

    return (
        f"(type IN ({listed(credits)}) AND amount > 0) OR "
        f"(type IN ({listed(debits)}) AND amount < 0) OR "
        "(type IN ('adjustment') AND amount <> 0)"
    )


def _rebuild(credits: tuple[str, ...], debits: tuple[str, ...]) -> None:
    op.drop_constraint(
        op.f("ck_wallet_transactions_wallet_amount_sign_by_type"), "wallet_transactions", type_="check"
    )
    op.create_check_constraint("wallet_amount_sign_by_type", "wallet_transactions", _sign_constraint(credits, debits))


def _stamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    for value in NEW_CREDITS + NEW_DEBITS:
        op.execute(f"ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS '{value}'")
    op.execute("ALTER TYPE driver_debt_source ADD VALUE IF NOT EXISTS 'intercity_commission'")
    op.execute("COMMIT")
    _rebuild(CREDITS + NEW_CREDITS, DEBITS + NEW_DEBITS)

    op.add_column(
        "service_settings",
        sa.Column("intercity_cancel_deadline_hours", sa.SmallInteger(), server_default=sa.text("2"), nullable=False),
    )
    op.create_check_constraint(
        "service_settings_intercity_valid", "service_settings", "intercity_cancel_deadline_hours BETWEEN 1 AND 48"
    )

    op.create_table(
        "intercity_routes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", COUNTRY, nullable=False),
        sa.Column("from_city", sa.String(length=60), nullable=False),
        sa.Column("to_city", sa.String(length=60), nullable=False),
        sa.Column("from_lat", sa.Float(), nullable=False),
        sa.Column("from_lng", sa.Float(), nullable=False),
        sa.Column("from_point", sa.String(length=255), nullable=False),
        sa.Column("to_lat", sa.Float(), nullable=False),
        sa.Column("to_lng", sa.Float(), nullable=False),
        sa.Column("to_point", sa.String(length=255), nullable=False),
        sa.Column("price_car", sa.Numeric(12, 3), nullable=False),
        sa.Column("price_seat", sa.Numeric(12, 3), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_stamps(),
        sa.CheckConstraint("price_car > 0 AND price_seat > 0", name=op.f("ck_intercity_routes_intercity_route_prices")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_intercity_routes")),
    )
    op.create_index(op.f("ix_intercity_routes_country_code"), "intercity_routes", ["country_code"])

    op.create_table(
        "intercity_permits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seats", sa.SmallInteger(), nullable=False),
        sa.Column("insurance_expires_on", sa.Date(), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_stamps(),
        sa.CheckConstraint("seats >= 4", name=op.f("ck_intercity_permits_intercity_permit_seats")),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_intercity_permits")),
    )
    op.create_index(op.f("ix_intercity_permits_driver_id"), "intercity_permits", ["driver_id"])

    op.create_table(
        "intercity_trips",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("route_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("departs_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seats_offered", sa.SmallInteger(), nullable=False),
        sa.Column("min_seats", sa.SmallInteger(), nullable=False),
        sa.Column("price_car_at_trip", sa.Numeric(12, 3), nullable=False),
        sa.Column("price_seat_at_trip", sa.Numeric(12, 3), nullable=False),
        sa.Column("commission_percent_at_trip", sa.Numeric(5, 2), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'open'"), nullable=False),
        sa.Column("departed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.String(length=32), nullable=True),
        *_stamps(),
        sa.CheckConstraint(
            "status IN ('open', 'departed', 'completed', 'cancelled') AND seats_offered BETWEEN 1 AND 8 "
            "AND min_seats BETWEEN 1 AND seats_offered",
            name=op.f("ck_intercity_trips_intercity_trip_valid"),
        ),
        sa.ForeignKeyConstraint(["route_id"], ["intercity_routes.id"]),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_intercity_trips")),
    )
    op.create_index(op.f("ix_intercity_trips_route_id"), "intercity_trips", ["route_id"])
    op.create_index(op.f("ix_intercity_trips_driver_id"), "intercity_trips", ["driver_id"])

    op.create_table(
        "intercity_bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seats", sa.SmallInteger(), nullable=False),
        sa.Column("whole_car", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 3), nullable=False),
        sa.Column("payment", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'booked'"), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        *_stamps(),
        sa.CheckConstraint(
            "status IN ('booked', 'cancelled', 'refunded', 'completed') AND seats >= 1 AND amount > 0 "
            "AND payment IN ('wallet', 'cash') AND (whole_car OR payment = 'wallet') AND (NOT whole_car OR payment = 'cash')",
            name=op.f("ck_intercity_bookings_intercity_booking_valid"),
        ),
        sa.ForeignKeyConstraint(["trip_id"], ["intercity_trips.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rider_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_intercity_bookings")),
    )
    op.create_index(op.f("ix_intercity_bookings_trip_id"), "intercity_bookings", ["trip_id"])
    op.create_index(op.f("ix_intercity_bookings_rider_id"), "intercity_bookings", ["rider_id"])


def downgrade() -> None:
    for table in ("intercity_bookings", "intercity_trips", "intercity_permits", "intercity_routes"):
        op.drop_table(table)
    op.drop_constraint(op.f("ck_service_settings_service_settings_intercity_valid"), "service_settings", type_="check")
    op.drop_column("service_settings", "intercity_cancel_deadline_hours")
    _rebuild(CREDITS, DEBITS)
