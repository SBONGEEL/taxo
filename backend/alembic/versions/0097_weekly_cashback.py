"""الاسترداد الأسبوعي (SPEC §٦٣-ج/٨) — سلاسلُ الأيام، والمبلغُ من اللوحة، وقيدٌ دائنٌ من TAXO.

**نوعٌ واحدٌ في الدفتر** (`cashback`، دائنٌ بلا مدين — من TAXO لا من كبتن) **ومعه إعادةُ بناء قيد الإشارة**. **والمبلغُ صفرٌ في السوقين**
— لم يقل المالكُ رقماً، والصفرُ يُخفي الخدمة؛ **وعددُ الأيام ٦** («أسبوعٌ بلا جمعته»، §٦٣-د/٩).

**ولا جدولَ مالٍ قائمٌ يُمسّ.** **و`downgrade` مقيسٌ لا مقروء**: قيمةُ التعداد لا تُنزع، **وقيدٌ بها يُسقط التراجع** عمداً.

Revision ID: 0097
Revises: 0096
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0097"
down_revision = "0096"
branch_labels = None
depends_on = None

CREDITS = (
    "topup", "ride_earning", "transfer_in", "refund", "tip", "referral_bonus", "advance",
    "cancellation_compensation", "guarantee_fee", "guarantee_refund", "guarantee_compensation",
    "commute_credit", "commute_incentive", "intercity_refund", "intercity_earning",
)
DEBITS = (
    "ride_payment", "commission", "transfer_out", "withdrawal", "subscription_payment", "tip_payment",
    "advance_repayment", "cancellation_fee", "skin_purchase", "guarantee_hold", "guarantee_penalty", "commute_prepay",
    "intercity_hold",
)


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
    op.execute("ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS 'cashback'")
    op.execute("COMMIT")
    _rebuild(CREDITS + ("cashback",), DEBITS)

    op.add_column("service_settings", sa.Column("cashback_amount", sa.Numeric(12, 3), server_default=sa.text("0"), nullable=False))
    op.add_column("service_settings", sa.Column("cashback_days", sa.SmallInteger(), server_default=sa.text("6"), nullable=False))
    op.create_check_constraint(
        "service_settings_cashback_valid", "service_settings", "cashback_amount >= 0 AND cashback_days BETWEEN 2 AND 14"
    )

    op.create_table(
        "cashback_streaks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", postgresql.ENUM("LY", "JO", name="country_code", create_type=False), nullable=False),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("last_day", sa.Date(), nullable=False),
        sa.Column("days_done", sa.SmallInteger(), nullable=False),
        sa.Column("days_required", sa.SmallInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 3), nullable=False),
        sa.Column("status", sa.String(length=8), server_default=sa.text("'active'"), nullable=False),
        sa.Column("won_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'won', 'lost') AND days_done >= 1 AND days_required >= 1 AND amount > 0 "
            "AND last_day >= started_on",
            name=op.f("ck_cashback_streaks_cashback_streak_valid"),
        ),
        sa.ForeignKeyConstraint(["rider_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cashback_streaks")),
    )
    op.create_index(op.f("ix_cashback_streaks_rider_id"), "cashback_streaks", ["rider_id"])
    op.create_index(
        "uq_cashback_streaks_active_rider", "cashback_streaks", ["rider_id"], unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_cashback_streaks_active_rider", table_name="cashback_streaks")
    op.drop_index(op.f("ix_cashback_streaks_rider_id"), table_name="cashback_streaks")
    op.drop_table("cashback_streaks")
    op.drop_constraint(op.f("ck_service_settings_service_settings_cashback_valid"), "service_settings", type_="check")
    op.drop_column("service_settings", "cashback_days")
    op.drop_column("service_settings", "cashback_amount")
    _rebuild(CREDITS, DEBITS)
