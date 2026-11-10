"""اشتراكاتُ الركّاب (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٣، SPEC §٩٧/١٣).

**تمسّ جدولَ مال** — فتُعرض على المالك قبل الرفع:
- **`wallet_transaction_type` + `rider_plan_payment`** (مدينٌ وحدَه: ثمنُ الاشتراك من محفظة الراكب)، **وإعادةُ بناء قيد الإشارة** بها
  (نمطُ `0154`). **لا صفَّ قائمٌ يتغيّر**، ولا قيدَ يُكتب بالترحيلة.
- ثلاثةُ جداولَ جديدة: `rider_plans` (الخطط) و`rider_plan_subscriptions` (اشتراكٌ مدفوعٌ بشروطه المجمَّدة) و`rider_plan_uses` (خصمٌ لكلِّ رحلة).
- **والمفتاحُ `rider_plans_enabled` مطفأ** — لا خطّةَ تُباع قبل أن يضعها المالكُ ويُشعله.

**والنزولُ** يحذف الجداول ويعيد القيدَ دون `rider_plan_payment` — **ويسقط عمداً إن وُجد قيدٌ به**.

Revision ID: 0156
Revises: 0155
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0156"
down_revision = "0155"
branch_labels = None
depends_on = None

#: **منسوخةٌ لا مستوردة** — قوائمُ `models/wallet.py` يومَ كُتبت
_CREDITS = (
    "topup", "ride_earning", "transfer_in", "refund", "tip", "referral_bonus", "advance", "cancellation_compensation",
    "guarantee_fee", "guarantee_refund", "guarantee_compensation", "commute_credit", "commute_incentive", "intercity_refund",
    "intercity_earning", "cashback", "taxo_card", "goal_reward",
)
_DEBITS_BEFORE = (
    "ride_payment", "commission", "transfer_out", "withdrawal", "subscription_payment", "tip_payment", "advance_repayment",
    "cancellation_fee", "skin_purchase", "guarantee_hold", "guarantee_penalty", "commute_prepay", "intercity_hold",
)
_DEBITS_AFTER = (*_DEBITS_BEFORE, "rider_plan_payment")
_SIGNED = ("adjustment", "rounding")


def _listed(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _rebuild(debits: tuple[str, ...]) -> None:
    op.drop_constraint(op.f("ck_wallet_transactions_wallet_amount_sign_by_type"), "wallet_transactions", type_="check")
    op.create_check_constraint(
        "wallet_amount_sign_by_type",
        "wallet_transactions",
        f"(type IN ({_listed(_CREDITS)}) AND amount > 0) OR "
        f"(type IN ({_listed(debits)}) AND amount < 0) OR "
        f"(type IN ({_listed(_SIGNED)}) AND amount <> 0)",
    )


def _stamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


_BEARERS = "bearer IN ('taxo', 'captain')"


def upgrade() -> None:
    op.execute("ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS 'rider_plan_payment'")
    op.execute("COMMIT")
    _rebuild(_DEBITS_AFTER)

    op.create_table(
        "rider_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", postgresql.ENUM(name="country_code", create_type=False), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(12, 3), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("per_ride_cap", sa.Numeric(12, 3), nullable=False),
        sa.Column("monthly_cap", sa.Numeric(12, 3), nullable=False),
        sa.Column("terms", sa.Text(), nullable=True),
        sa.Column("bearer", sa.String(8), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_stamps(),
        sa.CheckConstraint("days BETWEEN 7 AND 365", name=op.f("ck_rider_plans_rider_plan_days")),
        sa.CheckConstraint("price > 0", name=op.f("ck_rider_plans_rider_plan_price")),
        sa.CheckConstraint("discount_percent > 0 AND discount_percent <= 50", name=op.f("ck_rider_plans_rider_plan_percent")),
        sa.CheckConstraint("per_ride_cap > 0 AND monthly_cap >= per_ride_cap", name=op.f("ck_rider_plans_rider_plan_caps")),
        sa.CheckConstraint(_BEARERS, name=op.f("ck_rider_plans_rider_plan_bearer")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_rider_plans_created_by_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rider_plans")),
    )
    op.create_index(op.f("ix_rider_plans_country_code"), "rider_plans", ["country_code"])
    op.create_table(
        "rider_plan_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price_paid", sa.Numeric(12, 3), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("per_ride_cap", sa.Numeric(12, 3), nullable=False),
        sa.Column("monthly_cap", sa.Numeric(12, 3), nullable=False),
        sa.Column("bearer", sa.String(8), nullable=False),
        *_stamps(),
        sa.CheckConstraint("ends_at > starts_at", name=op.f("ck_rider_plan_subscriptions_rider_plan_sub_window")),
        sa.CheckConstraint(_BEARERS, name=op.f("ck_rider_plan_subscriptions_rider_plan_sub_bearer")),
        sa.ForeignKeyConstraint(["rider_id"], ["users.id"], name=op.f("fk_rider_plan_subscriptions_rider_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["rider_plans.id"], name=op.f("fk_rider_plan_subscriptions_plan_id_rider_plans"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rider_plan_subscriptions")),
    )
    op.create_index(op.f("ix_rider_plan_subscriptions_rider_id"), "rider_plan_subscriptions", ["rider_id"])
    op.create_index(op.f("ix_rider_plan_subscriptions_plan_id"), "rider_plan_subscriptions", ["plan_id"])
    op.create_table(
        "rider_plan_uses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ride_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(12, 3), nullable=False),
        *_stamps(),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["rider_plan_subscriptions.id"],
            name=op.f("fk_rider_plan_uses_subscription_id_rider_plan_subscriptions"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["ride_id"], ["rides.id"], name=op.f("fk_rider_plan_uses_ride_id_rides"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rider_plan_uses")),
        sa.UniqueConstraint("ride_id", name=op.f("uq_rider_plan_uses_ride_id")),
    )
    op.create_index(op.f("ix_rider_plan_uses_subscription_id"), "rider_plan_uses", ["subscription_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_rider_plan_uses_subscription_id"), table_name="rider_plan_uses")
    op.drop_table("rider_plan_uses")
    op.drop_index(op.f("ix_rider_plan_subscriptions_plan_id"), table_name="rider_plan_subscriptions")
    op.drop_index(op.f("ix_rider_plan_subscriptions_rider_id"), table_name="rider_plan_subscriptions")
    op.drop_table("rider_plan_subscriptions")
    op.drop_index(op.f("ix_rider_plans_country_code"), table_name="rider_plans")
    op.drop_table("rider_plans")
    _rebuild(_DEBITS_BEFORE)
