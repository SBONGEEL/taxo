"""نقاطُ الولاء (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٤، SPEC §٩٧/١٤).

**تمسّ جدولَ مال** — فتُعرض على المالك قبل الرفع:
- **`wallet_transaction_type` + `loyalty_reward`** (دائنٌ وحدَه من TAXO: استبدالُ النقاط رصيداً)، **وإعادةُ بناء قيد الإشارة** بها (نمطُ
  `0154`). **لا صفَّ قائمٌ يتغيّر**، ولا قيدَ يُكتب بالترحيلة.
- جدولان: `loyalty_rules` (قاعدةُ كلِّ دولة) و`loyalty_earnings` (نقاطُ كلِّ رحلة وما بقي منها وانتهاؤها).
- **والمفتاحُ `loyalty_enabled` مطفأ** — لا نقاطَ تُكسب ولا تُستبدل قبل أن يضع المالكُ القاعدةَ ويُشعله.

**والنزولُ** يحذف الجدولين ويعيد القيدَ دون `loyalty_reward` — **ويسقط عمداً إن وُجد قيدٌ به**.

Revision ID: 0157
Revises: 0156
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0157"
down_revision = "0156"
branch_labels = None
depends_on = None

#: **منسوخةٌ لا مستوردة** — قوائمُ `models/wallet.py` يومَ كُتبت
_CREDITS_BEFORE = (
    "topup", "ride_earning", "transfer_in", "refund", "tip", "referral_bonus", "advance", "cancellation_compensation",
    "guarantee_fee", "guarantee_refund", "guarantee_compensation", "commute_credit", "commute_incentive", "intercity_refund",
    "intercity_earning", "cashback", "taxo_card", "goal_reward",
)
_CREDITS_AFTER = (*_CREDITS_BEFORE, "loyalty_reward")
_DEBITS = (
    "ride_payment", "commission", "transfer_out", "withdrawal", "subscription_payment", "tip_payment", "advance_repayment",
    "cancellation_fee", "skin_purchase", "guarantee_hold", "guarantee_penalty", "commute_prepay", "intercity_hold",
    "rider_plan_payment",
)
_SIGNED = ("adjustment", "rounding")


def _listed(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _rebuild(credits: tuple[str, ...]) -> None:
    op.drop_constraint(op.f("ck_wallet_transactions_wallet_amount_sign_by_type"), "wallet_transactions", type_="check")
    op.create_check_constraint(
        "wallet_amount_sign_by_type",
        "wallet_transactions",
        f"(type IN ({_listed(credits)}) AND amount > 0) OR "
        f"(type IN ({_listed(_DEBITS)}) AND amount < 0) OR "
        f"(type IN ({_listed(_SIGNED)}) AND amount <> 0)",
    )


def _stamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.execute("ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS 'loyalty_reward'")
    op.execute("COMMIT")
    _rebuild(_CREDITS_AFTER)

    op.create_table(
        "loyalty_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", postgresql.ENUM(name="country_code", create_type=False), nullable=False),
        sa.Column("points_per_ride", sa.Integer(), nullable=False),
        sa.Column("expiry_days", sa.Integer(), nullable=False),
        sa.Column("silver_threshold", sa.Integer(), nullable=False),
        sa.Column("gold_threshold", sa.Integer(), nullable=False),
        sa.Column("silver_bonus_percent", sa.Integer(), nullable=False),
        sa.Column("gold_bonus_percent", sa.Integer(), nullable=False),
        sa.Column("redeem_points", sa.Integer(), nullable=False),
        sa.Column("redeem_value", sa.Numeric(12, 3), nullable=False),
        *_stamps(),
        sa.CheckConstraint("points_per_ride > 0", name=op.f("ck_loyalty_rules_loyalty_points_per_ride")),
        sa.CheckConstraint("expiry_days BETWEEN 30 AND 1095", name=op.f("ck_loyalty_rules_loyalty_expiry")),
        sa.CheckConstraint("gold_threshold > silver_threshold AND silver_threshold > 0", name=op.f("ck_loyalty_rules_loyalty_tiers")),
        sa.CheckConstraint(
            "silver_bonus_percent BETWEEN 0 AND 100 AND gold_bonus_percent BETWEEN 0 AND 100", name=op.f("ck_loyalty_rules_loyalty_bonus")
        ),
        sa.CheckConstraint("redeem_points > 0 AND redeem_value > 0", name=op.f("ck_loyalty_rules_loyalty_redeem")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_loyalty_rules")),
        sa.UniqueConstraint("country_code", name="uq_loyalty_rules_country"),
    )
    op.create_table(
        "loyalty_earnings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ride_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("remaining", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *_stamps(),
        sa.CheckConstraint("points > 0 AND remaining BETWEEN 0 AND points", name=op.f("ck_loyalty_earnings_loyalty_earning_points")),
        sa.ForeignKeyConstraint(["rider_id"], ["users.id"], name=op.f("fk_loyalty_earnings_rider_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ride_id"], ["rides.id"], name=op.f("fk_loyalty_earnings_ride_id_rides"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_loyalty_earnings")),
        sa.UniqueConstraint("ride_id", name=op.f("uq_loyalty_earnings_ride_id")),
    )
    op.create_index(op.f("ix_loyalty_earnings_rider_id"), "loyalty_earnings", ["rider_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_loyalty_earnings_rider_id"), table_name="loyalty_earnings")
    op.drop_table("loyalty_earnings")
    op.drop_table("loyalty_rules")
    _rebuild(_CREDITS_BEFORE)
