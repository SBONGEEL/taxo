"""**التحويلُ بين الدول** (أمرُ المالك ٢٠٢٦-١١-٢٢، `design/OWNER-2026-11-22-CROSS-TRANSFER.md`).

**تمسّ جدولَ مال** — فتُعرض على المالك قبل الرفع:
- **`wallet_transaction_type` + `cross_transfer_out` (مدين) و`cross_transfer_in` (دائن) و`cross_transfer_fee` (مدين)**، **وإعادةُ بناء قيد
  الإشارة** بها (نمطُ `0157`). **لا صفَّ قائمٌ يتغيّر**، ولا قيدَ يُكتب بالترحيلة.
- ثلاثةُ جداولَ جديدة: `fx_rates` (**فارغٌ — لا سعرَ يُبذر**)، و`cross_transfer_limits` (**فارغٌ — لا حدَّ يُبذر**)، و`cross_transfers`.
- **والمفتاحُ `cross_country_transfer_enabled` مطفأ** (غيابُ صفّه = مطفأ) — لا تحويلَ بين دولتين قبل أن يُشعله المالك.

**والنزولُ** يحذف الجداولَ الثلاثة ويعيد القيدَ دون الأنواع الثلاثة — **ويسقط عمداً إن وُجد قيدٌ بها** (قيدُ الإشارة يرفضه).
وقيمُ `ENUM` تبقى في النوع (postgres لا يحذف قيمة) — غيرُ مستعملةٍ ولا ضارّة، ونمطُ `0157` نفسُه.

Revision ID: 0187
Revises: 0186
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0187"
down_revision = "0186"
branch_labels = None
depends_on = None

#: **منسوخةٌ لا مستوردة** — قوائمُ `0157` (آخرُ من أعاد بناء القيد)، وهي قوائمُ `models/wallet.py` يومَ كُتبت هذه
_CREDITS_BEFORE = (
    "topup", "ride_earning", "transfer_in", "refund", "tip", "referral_bonus", "advance", "cancellation_compensation",
    "guarantee_fee", "guarantee_refund", "guarantee_compensation", "commute_credit", "commute_incentive", "intercity_refund",
    "intercity_earning", "cashback", "taxo_card", "goal_reward", "loyalty_reward",
)
_DEBITS_BEFORE = (
    "ride_payment", "commission", "transfer_out", "withdrawal", "subscription_payment", "tip_payment", "advance_repayment",
    "cancellation_fee", "skin_purchase", "guarantee_hold", "guarantee_penalty", "commute_prepay", "intercity_hold",
    "rider_plan_payment",
)
_CREDITS_AFTER = (*_CREDITS_BEFORE, "cross_transfer_in")
_DEBITS_AFTER = (*_DEBITS_BEFORE, "cross_transfer_out", "cross_transfer_fee")
_SIGNED = ("adjustment", "rounding")


def _listed(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _rebuild(credits: tuple[str, ...], debits: tuple[str, ...]) -> None:
    op.drop_constraint(op.f("ck_wallet_transactions_wallet_amount_sign_by_type"), "wallet_transactions", type_="check")
    op.create_check_constraint(
        "wallet_amount_sign_by_type",
        "wallet_transactions",
        f"(type IN ({_listed(credits)}) AND amount > 0) OR "
        f"(type IN ({_listed(debits)}) AND amount < 0) OR "
        f"(type IN ({_listed(_SIGNED)}) AND amount <> 0)",
    )


def _stamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def _currency() -> postgresql.ENUM:
    return postgresql.ENUM(name="currency", create_type=False)


def upgrade() -> None:
    for value in ("cross_transfer_out", "cross_transfer_in", "cross_transfer_fee"):
        op.execute(f"ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS '{value}'")
    op.execute("COMMIT")
    _rebuild(_CREDITS_AFTER, _DEBITS_AFTER)

    op.create_table(
        "fx_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_currency", _currency(), nullable=False),
        sa.Column("to_currency", _currency(), nullable=False),
        sa.Column("rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("fee_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("set_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("set_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_stamps(),
        sa.CheckConstraint("from_currency <> to_currency", name=op.f("ck_fx_rates_fx_rate_distinct_pair")),
        sa.CheckConstraint("rate > 0", name=op.f("ck_fx_rates_fx_rate_positive")),
        sa.CheckConstraint("fee_percent >= 0 AND fee_percent <= 20", name=op.f("ck_fx_rates_fx_fee_percent_range")),
        sa.ForeignKeyConstraint(["set_by"], ["users.id"], name=op.f("fk_fx_rates_set_by_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fx_rates")),
        sa.UniqueConstraint("from_currency", "to_currency", name="uq_fx_rates_pair"),
    )
    op.create_table(
        "cross_transfer_limits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", postgresql.ENUM(name="country_code", create_type=False), nullable=False),
        sa.Column("daily_limit", sa.Numeric(12, 3), nullable=False),
        sa.Column("monthly_limit", sa.Numeric(12, 3), nullable=False),
        *_stamps(),
        sa.CheckConstraint(
            "daily_limit >= 0 AND monthly_limit >= 0", name=op.f("ck_cross_transfer_limits_cross_limits_non_negative")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cross_transfer_limits")),
        sa.UniqueConstraint("country_code", name="uq_cross_transfer_limits_country"),
    )
    op.create_table(
        "cross_transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_currency", _currency(), nullable=False),
        sa.Column("to_currency", _currency(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 3), nullable=False),
        sa.Column("fee", sa.Numeric(12, 3), nullable=False),
        sa.Column("received", sa.Numeric(12, 3), nullable=False),
        sa.Column("rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("fee_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("rate_set_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("out_transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("in_transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fee_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        *_stamps(),
        sa.CheckConstraint(
            "amount > 0 AND fee >= 0 AND received > 0", name=op.f("ck_cross_transfers_cross_transfer_amounts")
        ),
        sa.CheckConstraint("from_currency <> to_currency", name=op.f("ck_cross_transfers_cross_transfer_distinct")),
        sa.ForeignKeyConstraint(
            ["sender_id"], ["users.id"], name=op.f("fk_cross_transfers_sender_id_users"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"], ["users.id"], name=op.f("fk_cross_transfers_recipient_id_users"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["out_transaction_id"], ["wallet_transactions.id"],
            name=op.f("fk_cross_transfers_out_transaction_id_wallet_transactions"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["in_transaction_id"], ["wallet_transactions.id"],
            name=op.f("fk_cross_transfers_in_transaction_id_wallet_transactions"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["fee_transaction_id"], ["wallet_transactions.id"],
            name=op.f("fk_cross_transfers_fee_transaction_id_wallet_transactions"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cross_transfers")),
        sa.UniqueConstraint("out_transaction_id", name=op.f("uq_cross_transfers_out_transaction_id")),
        sa.UniqueConstraint("in_transaction_id", name=op.f("uq_cross_transfers_in_transaction_id")),
        sa.UniqueConstraint("fee_transaction_id", name=op.f("uq_cross_transfers_fee_transaction_id")),
    )
    op.create_index(op.f("ix_cross_transfers_sender_id"), "cross_transfers", ["sender_id"])
    op.create_index(op.f("ix_cross_transfers_recipient_id"), "cross_transfers", ["recipient_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_cross_transfers_recipient_id"), table_name="cross_transfers")
    op.drop_index(op.f("ix_cross_transfers_sender_id"), table_name="cross_transfers")
    op.drop_table("cross_transfers")
    op.drop_table("cross_transfer_limits")
    op.drop_table("fx_rates")
    _rebuild(_CREDITS_BEFORE, _DEBITS_BEFORE)
