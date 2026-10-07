"""اشتراكُ الراكب — المشوارُ الثابت (SPEC §٦٣-ج/٦): اشتراكٌ شهريٌّ مدفوعٌ مقدّماً، ورحلاتٌ تُولَّد حجوزاً، وكبتنٌ معتمد.

**قناةُ دفعٍ جديدة** (`commute`) تكتبها المنصّةُ من المال المحفوظ لكلِّ رحلةٍ تُنفَّذ — كالكوبون، **وثلاثةُ أنواعٍ في الدفتر**:
`commute_prepay` (مدينٌ على الراكب بلا دائن — المالُ عند TAXO) · `commute_credit` (ما لم يُستعمل يعود رصيداً لا نقداً) ·
`commute_incentive` (حافزُ الكبتن المعتمد من TAXO، افتراضُه صفرٌ فلا قيد). **ومعها إعادةُ بناء قيد الإشارة** كـ`0092`.

**وأرقامُ المالك افتراضاتٌ للأردن** (خصمٌ ١٠٪ · حافزٌ صفر · تعليقٌ ٤ أيام) **ولليبيا خصمٌ صفرٌ يُخفيها**.

**ولا جدولَ مالٍ قائمٌ يُمسّ**: جدولٌ جديد، وعمودان فارغان على الحجز وواحدٌ على الرحلة. **و`downgrade` مقيسٌ لا مقروء**: قيمُ التعداد
لا تُنزع، **وقيدٌ بنوعٍ جديدٍ يُسقط التراجع** عمداً — مالٌ محفوظٌ لاشتراكٍ قائمٍ لا يُمحى أثرُه بتراجع.

Revision ID: 0095
Revises: 0094
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0095"
down_revision = "0094"
branch_labels = None
depends_on = None

CREDITS = (
    "topup", "ride_earning", "transfer_in", "refund", "tip", "referral_bonus", "advance",
    "cancellation_compensation", "guarantee_fee", "guarantee_refund", "guarantee_compensation",
)
DEBITS = (
    "ride_payment", "commission", "transfer_out", "withdrawal", "subscription_payment", "tip_payment",
    "advance_repayment", "cancellation_fee", "skin_purchase", "guarantee_hold", "guarantee_penalty",
)
NEW_CREDITS = ("commute_credit", "commute_incentive")
NEW_DEBITS = ("commute_prepay",)


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


def upgrade() -> None:
    op.execute("ALTER TYPE payment_method ADD VALUE IF NOT EXISTS 'commute'")
    for value in NEW_CREDITS + NEW_DEBITS:
        op.execute(f"ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS '{value}'")
    op.execute("COMMIT")
    _rebuild(CREDITS + NEW_CREDITS, DEBITS + NEW_DEBITS)

    op.add_column(
        "service_settings",
        sa.Column("commute_discount_percent", sa.Numeric(5, 2), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "service_settings",
        sa.Column("commute_captain_incentive", sa.Numeric(12, 3), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "service_settings",
        sa.Column("commute_max_suspend_days", sa.SmallInteger(), server_default=sa.text("4"), nullable=False),
    )
    op.create_check_constraint(
        "service_settings_commute_valid",
        "service_settings",
        "commute_discount_percent >= 0 AND commute_discount_percent < 100 AND commute_captain_incentive >= 0 "
        "AND commute_max_suspend_days >= 0",
    )
    op.execute("UPDATE service_settings SET commute_discount_percent = 10.00 WHERE country_code = 'JO'")

    op.create_table(
        "rider_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", postgresql.ENUM("LY", "JO", name="country_code", create_type=False), nullable=False),
        sa.Column("pickup_lat", sa.Float(), nullable=False),
        sa.Column("pickup_lng", sa.Float(), nullable=False),
        sa.Column("pickup_address", sa.String(length=255), nullable=True),
        sa.Column("dropoff_lat", sa.Float(), nullable=False),
        sa.Column("dropoff_lng", sa.Float(), nullable=False),
        sa.Column("dropoff_address", sa.String(length=255), nullable=True),
        sa.Column("weekdays", sa.SmallInteger(), nullable=False),
        sa.Column("go_time", sa.Time(), nullable=False),
        sa.Column("return_time", sa.Time(), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("price_per_ride", sa.Numeric(12, 3), nullable=False),
        sa.Column("rides_total", sa.SmallInteger(), nullable=False),
        sa.Column("amount_paid", sa.Numeric(12, 3), nullable=False),
        sa.Column("suspended_days", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'active'"), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'ended', 'cancelled') AND weekdays BETWEEN 1 AND 127 AND rides_total > 0 "
            "AND price_per_ride > 0 AND amount_paid > 0 AND ends_on >= starts_on",
            name=op.f("ck_rider_subscriptions_rider_subscription_valid"),
        ),
        sa.ForeignKeyConstraint(["rider_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"]),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rider_subscriptions")),
    )
    op.create_index(op.f("ix_rider_subscriptions_rider_id"), "rider_subscriptions", ["rider_id"])
    op.create_index(op.f("ix_rider_subscriptions_driver_id"), "rider_subscriptions", ["driver_id"])

    op.add_column("ride_bookings", sa.Column("commute_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        op.f("fk_ride_bookings_commute_id_rider_subscriptions"), "ride_bookings", "rider_subscriptions",
        ["commute_id"], ["id"],
    )
    op.create_index(
        "uq_ride_bookings_commute_slot", "ride_bookings", ["commute_id", "scheduled_at"], unique=True,
        postgresql_where=sa.text("commute_id IS NOT NULL"),
    )
    op.add_column("rides", sa.Column("commute_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        op.f("fk_rides_commute_id_rider_subscriptions"), "rides", "rider_subscriptions", ["commute_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_rides_commute_id_rider_subscriptions"), "rides", type_="foreignkey")
    op.drop_column("rides", "commute_id")
    op.drop_index("uq_ride_bookings_commute_slot", table_name="ride_bookings")
    op.drop_constraint(op.f("fk_ride_bookings_commute_id_rider_subscriptions"), "ride_bookings", type_="foreignkey")
    op.drop_column("ride_bookings", "commute_id")
    op.drop_index(op.f("ix_rider_subscriptions_driver_id"), table_name="rider_subscriptions")
    op.drop_index(op.f("ix_rider_subscriptions_rider_id"), table_name="rider_subscriptions")
    op.drop_table("rider_subscriptions")
    op.drop_constraint(op.f("ck_service_settings_service_settings_commute_valid"), "service_settings", type_="check")
    for column in ("commute_max_suspend_days", "commute_captain_incentive", "commute_discount_percent"):
        op.drop_column("service_settings", column)
    _rebuild(CREDITS, DEBITS)
