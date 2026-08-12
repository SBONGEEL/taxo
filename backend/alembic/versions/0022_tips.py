"""البقشيش (SPEC القسم 6.5، المرحلة 12-و)

جدولٌ واحد، وقيمتان على تعدادِ الدفتر، وثلاثةُ حقولٍ على `payment_settings`.

**وفيها فخُّ `0018` نفسُه بوجهٍ جديد**: postgres يسمح بإضافة قيمةٍ إلى ENUM
داخل معاملة ويمنع **استعمالها** فيها — وقيدُ إشارةِ المبلغ في الدفتر يستعمل
القيمَ الجديدة نصّاً (`type IN ('tip', …)`). و`0009` تفادى ذلك بمقارنة
`purpose::text`، لكن ذاك يجعل شكلَ القيد مختلفاً عمّا يولّده النموذج فيراه
`test_migrations_match_models` فرقاً دائماً. فالمخرجُ هنا **COMMIT صريح** بعد
`ALTER TYPE` كما في `0018` — وكلُّ ما بعده مكتوبٌ ليُعاد تشغيلُه بلا ضرر، لأن
ذلك الـcommit يعني أن فشلاً لاحقاً لم يعد يتراجع عمّا قبله.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# نفسُ ما يولّده `models/wallet.py::_amount_sign_constraint` — والقائمتان هنا
# **بعد** إضافة `tip`/`tip_payment`. أيُّ اختلافٍ بين النصّين يظهر فوراً في
# `test_migrations_match_models`، وهو الحارس الذي يمنع انحرافهما
CREDIT = "'topup', 'ride_earning', 'transfer_in', 'refund', 'tip'"
DEBIT = (
    "'ride_payment', 'commission', 'transfer_out', 'withdrawal', "
    "'subscription_payment', 'tip_payment'"
)
SIGNED = "'adjustment'"
SIGN_CHECK = (
    f"(type IN ({CREDIT}) AND amount > 0) OR "
    f"(type IN ({DEBIT}) AND amount < 0) OR "
    f"(type IN ({SIGNED}) AND amount <> 0)"
)
SIGN_CHECK_NAME = "ck_wallet_transactions_wallet_amount_sign_by_type"


def upgrade() -> None:
    # (1) قيمتا الدفتر — ثم **commit صريح** قبل استعمالهما في القيد أدناه
    op.execute("ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS 'tip'")
    op.execute(
        "ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS 'tip_payment'"
    )
    op.execute("COMMIT")

    # (2) قيدُ الإشارة يُعاد بناؤه ليعرف النوعين الجديدين. وبغير إعادته يمرّ
    # قيدُ بقشيشٍ بأي إشارة — أي أن خصماً بإشارةٍ مقلوبة **يزيد** رصيد الراكب
    op.execute(
        f"ALTER TABLE wallet_transactions DROP CONSTRAINT IF EXISTS {SIGN_CHECK_NAME}"
    )
    op.execute(
        f"ALTER TABLE wallet_transactions ADD CONSTRAINT {SIGN_CHECK_NAME} "
        f"CHECK ({SIGN_CHECK})"
    )

    # (3) الجدول. **بلا `status` وبلا `method`**: القناةُ المحفظةُ وحدها وتستقر
    # في نفس المعاملة، فوجودُ الصفِّ هو أن المال تحرّك — ولا قيمةَ `failed`
    # يمكن أن تُكتب أصلاً (انظر `models/tip.py`)
    op.create_table(
        "tips",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("ride_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("rider_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("driver_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(12, 3), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
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
        sa.ForeignKeyConstraint(["ride_id"], ["rides.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rider_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["driver_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("ride_id", name="uq_tips_ride_id"),
        sa.CheckConstraint("amount > 0", name="tips_amount_positive"),
        if_not_exists=True,
    )
    op.create_index("ix_tips_rider_id", "tips", ["rider_id"], if_not_exists=True)
    op.create_index("ix_tips_driver_id", "tips", ["driver_id"], if_not_exists=True)

    # (4) مبالغُ الأزرار وسقفُها per-country — **أصفارٌ تعني «لم يُضبط»** فتُخفى
    # الميزة (نفس قاعدة `wallet_settings.transfer_*_limit`)
    for column in ("tip_preset_small", "tip_preset_medium", "tip_max"):
        op.add_column(
            "payment_settings",
            sa.Column(
                column,
                sa.Numeric(12, 3),
                nullable=False,
                server_default=sa.text("0"),
            ),
            if_not_exists=True,
        )
    op.execute(
        "ALTER TABLE payment_settings DROP CONSTRAINT IF EXISTS "
        "ck_payment_settings_payment_tip_amounts_not_negative"
    )
    op.execute(
        "ALTER TABLE payment_settings ADD CONSTRAINT "
        "ck_payment_settings_payment_tip_amounts_not_negative CHECK "
        "(tip_preset_small >= 0 AND tip_preset_medium >= 0 AND tip_max >= 0)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE payment_settings DROP CONSTRAINT IF EXISTS "
        "ck_payment_settings_payment_tip_amounts_not_negative"
    )
    for column in ("tip_max", "tip_preset_medium", "tip_preset_small"):
        op.drop_column("payment_settings", column, if_exists=True)

    op.drop_index("ix_tips_driver_id", table_name="tips", if_exists=True)
    op.drop_index("ix_tips_rider_id", table_name="tips", if_exists=True)
    op.drop_table("tips", if_exists=True)

    # قيمةٌ أُضيفت إلى ENUM لا تُحذف في postgres، لكن **القيدَ يُعاد إلى شكله
    # الأقدم**: بغير ذلك يبقى قيدٌ يسمح بنوعين لا يعرفهما الكود الأقدم. وقيودُ
    # الدفتر تُحذف صفوفُ البقشيش قبلها — صفٌّ بنوعٍ لا يعرفه الكود أسوأ من غيابه
    op.execute(
        "DELETE FROM wallet_transactions WHERE type IN ('tip', 'tip_payment')"
    )
    op.execute(
        f"ALTER TABLE wallet_transactions DROP CONSTRAINT IF EXISTS {SIGN_CHECK_NAME}"
    )
    op.execute(
        f"ALTER TABLE wallet_transactions ADD CONSTRAINT {SIGN_CHECK_NAME} CHECK ("
        "(type IN ('topup', 'ride_earning', 'transfer_in', 'refund') AND amount > 0) OR "
        "(type IN ('ride_payment', 'commission', 'transfer_out', 'withdrawal', "
        "'subscription_payment') AND amount < 0) OR "
        "(type IN ('adjustment') AND amount <> 0))"
    )
