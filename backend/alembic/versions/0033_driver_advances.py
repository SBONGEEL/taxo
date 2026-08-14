"""driver advances

سلفُ الكباتن (البند ١٥): جدولُ السلف وإعداداتُها، وعمودان على الكبتن، وربطُ
الدفتر بالسلفة، **ونوعان جديدان في نوع القيد**.

وثلاثةُ مطبّاتٍ في Postgres تلتقي هنا، كلُّها معروفةٌ في هذا المشروع:

- `ALTER TYPE … ADD VALUE` لا يجوز في المعاملة نفسِها التي **تستعمل** القيمة،
  و`env.py` يلفّ السلسلةَ كلَّها في معاملةٍ واحدة — فـ`COMMIT` صريحٌ بعد
  الإضافة، تماماً كترحيلة `0018`. وما بعده يُكتب `IF EXISTS` لأن ذلك الـcommit
  يعني أن فشلاً لاحقاً لا يتراجع عمّا سبقه.
- والأنواعُ التي أنشأتها ترحيلاتٌ سابقة (`country_code`، `currency`) تُشار
  إليها بـ`create_type=False`، وإلا فشل `upgrade` بـ«type already exists».
- والنوعُ الجديدُ (`advance_status`) يُسقَط في `downgrade` صراحةً: Postgres لا
  يُسقط الأنواع مع جداولها.

**وقيدُ إشارة المبلغ يُعاد بناؤه**: `advance` دائنٌ و`advance_repayment` مدين،
والقيدُ القديم لا يعرفهما — فيرفض كلَّ قيدٍ منهما.

Revision ID: 0033
Revises: 0032
Create Date: 2026-08-14 21:29:41.163969
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


COUNTRY = postgresql.ENUM("LY", "JO", name="country_code", create_type=False)
CURRENCY = postgresql.ENUM("LYD", "JOD", name="currency", create_type=False)

# القيدُ كما تبنيه `models/wallet.py` من الثلاثيات نفسِها — والقائمتان هنا
# نسخةُ لحظتِها، لأن الترحيلةَ تصف قاعدةً في زمنٍ لا نموذجاً يتغيّر
CREDITS = (
    "topup",
    "ride_earning",
    "transfer_in",
    "refund",
    "tip",
    "referral_bonus",
    "advance",
)
DEBITS = (
    "ride_payment",
    "commission",
    "transfer_out",
    "withdrawal",
    "subscription_payment",
    "tip_payment",
    "advance_repayment",
)


def _sign_constraint(credits: tuple[str, ...], debits: tuple[str, ...]) -> str:
    def listed(values: tuple[str, ...]) -> str:
        return ", ".join(f"'{value}'" for value in values)

    return (
        f"(type IN ({listed(credits)}) AND amount > 0) OR "
        f"(type IN ({listed(debits)}) AND amount < 0) OR "
        "(type IN ('adjustment') AND amount <> 0)"
    )


def upgrade() -> None:
    # **القيمتان الجديدتان أولاً ثم commit**: ما بعده يستعملهما في قيدِ فحص،
    # والاستعمالُ في معاملة الإضافة نفسِها مرفوضٌ في Postgres
    op.execute(
        "ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS 'advance'"
    )
    op.execute(
        "ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS "
        "'advance_repayment'"
    )
    op.execute("COMMIT")

    advance_status = postgresql.ENUM(
        "outstanding", "repaid", "written_off", name="advance_status"
    )
    advance_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "advance_settings",
        sa.Column("country_code", COUNTRY, nullable=False),
        sa.Column(
            "deduction_percent",
            sa.Integer(),
            server_default=sa.text("20"),
            nullable=False,
        ),
        sa.Column(
            "min_kept_amount",
            sa.Numeric(precision=12, scale=3),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "term_days", sa.Integer(), server_default=sa.text("14"), nullable=False
        ),
        sa.Column(
            "min_completed_rides",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "min_rating",
            sa.Numeric(precision=3, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "growth_percent_per_repaid",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "max_multiplier_percent",
            sa.Integer(),
            server_default=sa.text("100"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.CheckConstraint(
            "deduction_percent > 0 AND deduction_percent <= 100 AND term_days > 0 "
            "AND min_kept_amount >= 0 AND min_completed_rides >= 0 "
            "AND min_rating >= 0 AND growth_percent_per_repaid >= 0 "
            "AND max_multiplier_percent >= 100",
            name=op.f("ck_advance_settings_advance_settings_sane"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_advance_settings")),
    )
    op.create_index(
        op.f("ix_advance_settings_country_code"),
        "advance_settings",
        ["country_code"],
        unique=True,
        if_not_exists=True,
    )

    op.create_table(
        "driver_advances",
        sa.Column("driver_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("currency", CURRENCY, nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "outstanding",
                "repaid",
                "written_off",
                name="advance_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("written_off_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("written_off_by", sa.UUID(), nullable=True),
        sa.Column("writeoff_reason", sa.String(length=300), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.CheckConstraint(
            "(written_off_at IS NULL AND written_off_by IS NULL "
            "AND writeoff_reason IS NULL) OR "
            "(written_off_at IS NOT NULL AND writeoff_reason IS NOT NULL)",
            name=op.f("ck_driver_advances_advance_writeoff_all_or_nothing"),
        ),
        sa.CheckConstraint(
            "amount > 0", name=op.f("ck_driver_advances_advance_amount_positive")
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"],
            ["users.id"],
            name=op.f("fk_driver_advances_approved_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["driver_id"],
            ["drivers.id"],
            name=op.f("fk_driver_advances_driver_id_drivers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["written_off_by"],
            ["users.id"],
            name=op.f("fk_driver_advances_written_off_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_driver_advances")),
    )
    op.create_index(
        op.f("ix_driver_advances_driver_id"),
        "driver_advances",
        ["driver_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        op.f("ix_driver_advances_status"),
        "driver_advances",
        ["status"],
        unique=False,
        if_not_exists=True,
    )
    # **سلفةٌ قائمةٌ واحدةٌ لكل كبتن** — الحارسُ الأخير تحت أي سباق
    op.create_index(
        "uq_advance_outstanding",
        "driver_advances",
        ["driver_id"],
        unique=True,
        postgresql_where="status = 'outstanding'",
        if_not_exists=True,
    )

    op.add_column(
        "drivers",
        sa.Column("advance_cap_override", sa.Numeric(precision=12, scale=3), nullable=True),
    )
    op.add_column(
        "drivers",
        sa.Column(
            "advance_blocked",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    op.add_column("wallet_transactions", sa.Column("advance_id", sa.UUID(), nullable=True))
    op.create_index(
        op.f("ix_wallet_transactions_advance_id"),
        "wallet_transactions",
        ["advance_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_foreign_key(
        op.f("fk_wallet_transactions_advance_id_driver_advances"),
        "wallet_transactions",
        "driver_advances",
        ["advance_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # **وقيدُ الإشارة يُعاد بناؤه ليعرف النوعين الجديدين** — وبغيره يرفض
    # الدفترُ كلَّ صرفٍ وكلَّ اقتطاع
    op.drop_constraint(
        op.f("ck_wallet_transactions_wallet_amount_sign_by_type"),
        "wallet_transactions",
        type_="check",
    )
    op.create_check_constraint(
        "wallet_amount_sign_by_type",
        "wallet_transactions",
        _sign_constraint(CREDITS, DEBITS),
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_wallet_transactions_wallet_amount_sign_by_type"),
        "wallet_transactions",
        type_="check",
    )
    op.create_check_constraint(
        "wallet_amount_sign_by_type",
        "wallet_transactions",
        _sign_constraint(CREDITS[:-1], DEBITS[:-1]),
    )
    op.drop_constraint(
        op.f("fk_wallet_transactions_advance_id_driver_advances"),
        "wallet_transactions",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_wallet_transactions_advance_id"), table_name="wallet_transactions"
    )
    op.drop_column("wallet_transactions", "advance_id")
    op.drop_column("drivers", "advance_blocked")
    op.drop_column("drivers", "advance_cap_override")
    op.drop_index(
        "uq_advance_outstanding",
        table_name="driver_advances",
        postgresql_where="status = 'outstanding'",
    )
    op.drop_index(op.f("ix_driver_advances_status"), table_name="driver_advances")
    op.drop_index(op.f("ix_driver_advances_driver_id"), table_name="driver_advances")
    op.drop_table("driver_advances")
    op.drop_index(
        op.f("ix_advance_settings_country_code"), table_name="advance_settings"
    )
    op.drop_table("advance_settings")
    # النوعُ لا يسقط مع جدوله — و`IF EXISTS` هو ما يجعل تراجعاً جزئياً قابلاً
    # للترقية من جديد. وقيمتا الدفتر لا تُحذفان: Postgres لا يزيل قيمةً من نوع
    op.execute("DROP TYPE IF EXISTS advance_status")
