"""أهدافُ الكبتن ومكافآتُها (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٦، SPEC §٩٧/١٦).

**تمسّ جدولَ مال** — فتُعرض على المالك قبل الرفع:
- **`wallet_transaction_type` + `goal_reward`** (دائنٌ وحدَه من TAXO كحافز الإحالة)، **وإعادةُ بناء قيد الإشارة** بها (نمطُ `0097`/`0104`).
  **لا صفَّ قائمٌ يتغيّر**، ولا قيدَ يُكتب بالترحيلة.
- جدولان جديدان: `driver_goals` (الهدفُ ومكافأتُه وسقفُه) و`driver_goal_awards` (مكافأةٌ لكلِّ هدفٍ وكبتنٍ مرّةً).
- **والمفتاحُ `driver_goals_enabled` مطفأٌ** — لا مكافأةَ تُصرف قبل أن يضع المالكُ هدفاً ويُشعله.

**والنزولُ** يحذف الجدولين ويعيد القيدَ دون `goal_reward` — **ويسقط عمداً إن وُجد قيدٌ بها**: نزولٌ يمحو مالاً صُرف أسوأُ من نزولٍ يقف.

Revision ID: 0154
Revises: 0153
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0154"
down_revision = "0153"
branch_labels = None
depends_on = None

#: **منسوخةٌ لا مستوردة** — قوائمُ `models/wallet.py` يومَ كُتبت
_CREDITS_BEFORE = (
    "topup", "ride_earning", "transfer_in", "refund", "tip", "referral_bonus", "advance", "cancellation_compensation",
    "guarantee_fee", "guarantee_refund", "guarantee_compensation", "commute_credit", "commute_incentive", "intercity_refund",
    "intercity_earning", "cashback", "taxo_card",
)
_CREDITS_AFTER = (*_CREDITS_BEFORE, "goal_reward")
_DEBITS = (
    "ride_payment", "commission", "transfer_out", "withdrawal", "subscription_payment", "tip_payment", "advance_repayment",
    "cancellation_fee", "skin_purchase", "guarantee_hold", "guarantee_penalty", "commute_prepay", "intercity_hold",
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
    # ── نوعُ القيد أوّلاً — `ADD VALUE` لا يُستعمل في معاملته، فيُختم قبل ما يقرؤه (نمطُ `0097`)
    op.execute("ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS 'goal_reward'")
    op.execute("COMMIT")
    _rebuild(_CREDITS_AFTER)

    op.create_table(
        "driver_goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", postgresql.ENUM(name="country_code", create_type=False), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reward_amount", sa.Numeric(12, 3), nullable=False),
        sa.Column("budget_cap", sa.Numeric(12, 3), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_stamps(),
        sa.CheckConstraint("target > 0", name=op.f("ck_driver_goals_driver_goal_target_positive")),
        sa.CheckConstraint("reward_amount > 0", name=op.f("ck_driver_goals_driver_goal_reward_positive")),
        sa.CheckConstraint("budget_cap >= reward_amount", name=op.f("ck_driver_goals_driver_goal_budget_covers_one")),
        sa.CheckConstraint("ends_at > starts_at", name=op.f("ck_driver_goals_driver_goal_window")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_driver_goals_created_by_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_driver_goals")),
    )
    op.create_index(op.f("ix_driver_goals_country_code"), "driver_goals", ["country_code"])
    op.create_table(
        "driver_goal_awards",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(12, 3), nullable=False),
        sa.Column("reference", sa.String(64), nullable=False),
        *_stamps(),
        sa.ForeignKeyConstraint(["goal_id"], ["driver_goals.id"], name=op.f("fk_driver_goal_awards_goal_id_driver_goals"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"], name=op.f("fk_driver_goal_awards_driver_id_drivers"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_driver_goal_awards")),
        sa.UniqueConstraint("goal_id", "driver_id", name="uq_driver_goal_award"),
    )
    op.create_index(op.f("ix_driver_goal_awards_goal_id"), "driver_goal_awards", ["goal_id"])
    op.create_index(op.f("ix_driver_goal_awards_driver_id"), "driver_goal_awards", ["driver_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_driver_goal_awards_driver_id"), table_name="driver_goal_awards")
    op.drop_index(op.f("ix_driver_goal_awards_goal_id"), table_name="driver_goal_awards")
    op.drop_table("driver_goal_awards")
    op.drop_index(op.f("ix_driver_goals_country_code"), table_name="driver_goals")
    op.drop_table("driver_goals")
    # **قيدٌ بـ`goal_reward` يُسقط النزولَ عمداً** — والقيمةُ تبقى في النوع كما تركت `0113` قيمتَها
    _rebuild(_CREDITS_BEFORE)
