"""حافزُ إحالة السائقات (SPEC القسم 9.1، المرحلة 12-ح)

جدولان، وعمودٌ على `drivers` **بتوليدٍ للقائمين**، وقيمةٌ على تعدادِ الدفتر.

**وفيها فخُّ `0022` نفسُه**: postgres يسمح بإضافة قيمةٍ إلى ENUM داخل معاملة
ويمنع **استعمالها** فيها — وقيدُ إشارةِ المبلغ يستعمل القيمةَ الجديدة نصّاً.
فـ COMMIT صريحٌ بعد `ALTER TYPE`، وكلُّ ما بعده مكتوبٌ ليُعاد تشغيلُه بلا ضرر.

**وتوليدُ رموزِ القائمين في الترحيلة لا في الكود**: العمودُ فريد، وتوليدٌ متأخرٌ
عند أول قراءةٍ يحتاج قفلاً على صفٍّ لا يُكتب فيه شيءٌ آخر — وبغيره تُنتج ضغطتان
رمزين. و`md5` هنا كافٍ: الرمزُ مُعرِّفٌ عامٌّ يُقال في مكالمة، لا سرٌّ — وسرّيّتُه
لا تحمي شيئاً (من يعرف رمزَ أحدهم لا يستفيد منه، فالمكافأةُ لصاحب الرمز).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# نفسُ ما يولّده `models/wallet.py::_amount_sign_constraint` **بعد** إضافة
# `referral_bonus` إلى الدائنة. وأيُّ اختلافٍ بين النصّين يظهر فوراً في
# `test_migrations_match_models`
CREDIT = "'topup', 'ride_earning', 'transfer_in', 'refund', 'tip', 'referral_bonus'"
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

# ثمانيةُ محارفٍ من أبجديةٍ بلا `0/O/1/I/L`: الرمزُ يُقرأ من شاشةٍ ويُكتب في
# أخرى، والحرفان المتشابهان يجعلان رمزاً صحيحاً يُرفض. والطولُ يكفي لملايين
# الحسابات بلا تصادمٍ عمليّ، ومع ذلك الفريدُ في القاعدة هو الحارس
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def upgrade() -> None:
    # (1) قيمةُ الدفتر — ثم **commit صريح** قبل استعمالها في القيد أدناه
    op.execute(
        "ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS 'referral_bonus'"
    )
    op.execute("COMMIT")

    # (2) قيدُ الإشارة يُعاد بناؤه ليعرف النوعَ الجديد. وبغير إعادته يمرّ قيدُ
    # مكافأةٍ بأي إشارة — أي أن مكافأةً بإشارةٍ مقلوبة **تنقص** رصيد الكبتن
    op.execute(
        f"ALTER TABLE wallet_transactions DROP CONSTRAINT IF EXISTS {SIGN_CHECK_NAME}"
    )
    op.execute(
        f"ALTER TABLE wallet_transactions ADD CONSTRAINT {SIGN_CHECK_NAME} "
        f"CHECK ({SIGN_CHECK})"
    )

    # (3) إعداداتُ الحافز per-country — **صفرٌ يعني «لم يُحدَّد»** (قرارُ المالك)
    op.create_table(
        "referral_settings",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "country_code",
            # **`postgresql.ENUM` لا `sa.Enum`**: الثاني يتجاهل `create_type`
            # ويصدر `CREATE TYPE` لنوعٍ أنشأته ترحيلةٌ سابقة، فيفشل الترقية
            postgresql.ENUM("JO", "LY", name="country_code", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "reward_amount",
            sa.Numeric(12, 3),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "required_rides", sa.Integer(), nullable=False, server_default=sa.text("3")
        ),
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
            "reward_amount >= 0 AND required_rides >= 0",
            name="referral_amounts_not_negative",
        ),
        # **ولا `UniqueConstraint` معه**: `unique=True, index=True` على العمود
        # في النموذج يولّد **فهرساً فريداً** لا قيداً، فإضافةُ القيد هنا تجعل
        # `test_migrations_match_models` يرى فرقاً دائماً (وهو ما وقع)
        if_not_exists=True,
    )
    op.create_index(
        "ix_referral_settings_country_code",
        "referral_settings",
        ["country_code"],
        unique=True,
        if_not_exists=True,
    )

    # (4) الرمزُ على `drivers`، ثم توليدُه للقائمين — **قبل** الفهرس الفريد،
    # فصفّان بـ NULL لا يتعارضان لكن التوليدَ أولاً يجعل الفهرسَ يُبنى مرةً
    op.add_column(
        "drivers", sa.Column("referral_code", sa.String(16), nullable=True),
        if_not_exists=True,
    )
    op.execute(
        f"""
        UPDATE drivers SET referral_code = (
            SELECT string_agg(
                substr('{ALPHABET}', 1 + (get_byte(digest, i) % {len(ALPHABET)}), 1),
                ''
            )
            FROM (SELECT decode(md5(drivers.id::text || 'taxo-referral'), 'hex') AS digest) d,
                 generate_series(0, 7) AS i
        )
        WHERE referral_code IS NULL
        """
    )
    op.create_index(
        "ix_drivers_referral_code",
        "drivers",
        ["referral_code"],
        unique=True,
        if_not_exists=True,
    )

    # (5) الإحالاتُ نفسها
    op.create_table(
        "driver_referrals",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("referrer_driver_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("referred_driver_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("code_used", sa.String(16), nullable=False),
        sa.Column("rewarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reward_amount", sa.Numeric(12, 3), nullable=True),
        sa.Column("reward_currency", sa.String(3), nullable=True),
        sa.Column("transaction_id", sa.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["referrer_driver_id"], ["drivers.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["referred_driver_id"], ["drivers.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["wallet_transactions.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("referred_driver_id"),
        sa.CheckConstraint(
            "referrer_driver_id <> referred_driver_id", name="referral_not_self"
        ),
        sa.CheckConstraint(
            "(rewarded_at IS NULL AND reward_amount IS NULL "
            "AND reward_currency IS NULL AND transaction_id IS NULL) OR "
            "(rewarded_at IS NOT NULL AND reward_amount IS NOT NULL "
            "AND reward_currency IS NOT NULL AND transaction_id IS NOT NULL)",
            name="referral_reward_all_or_nothing",
        ),
        sa.CheckConstraint(
            "reward_amount IS NULL OR reward_amount > 0",
            name="referral_reward_positive",
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ix_driver_referrals_referrer_driver_id",
        "driver_referrals",
        ["referrer_driver_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_driver_referrals_rewarded_at",
        "driver_referrals",
        ["rewarded_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_driver_referrals_rewarded_at", table_name="driver_referrals", if_exists=True
    )
    op.drop_index(
        "ix_driver_referrals_referrer_driver_id",
        table_name="driver_referrals",
        if_exists=True,
    )
    op.drop_table("driver_referrals", if_exists=True)

    op.drop_index("ix_drivers_referral_code", table_name="drivers", if_exists=True)
    op.drop_column("drivers", "referral_code", if_exists=True)

    op.drop_index(
        "ix_referral_settings_country_code",
        table_name="referral_settings",
        if_exists=True,
    )
    op.drop_table("referral_settings", if_exists=True)

    # قيمةٌ أُضيفت إلى ENUM لا تُحذف في postgres، لكن **القيدَ يُعاد إلى شكله
    # الأقدم** — وقيودُ المكافأة تُحذف قبله: صفٌّ بنوعٍ لا يعرفه الكود الأقدم
    # أسوأ من غيابه (نفسُ ترتيب `0022`)
    op.execute("DELETE FROM wallet_transactions WHERE type = 'referral_bonus'")
    op.execute(
        f"ALTER TABLE wallet_transactions DROP CONSTRAINT IF EXISTS {SIGN_CHECK_NAME}"
    )
    op.execute(
        f"ALTER TABLE wallet_transactions ADD CONSTRAINT {SIGN_CHECK_NAME} CHECK ("
        "(type IN ('topup', 'ride_earning', 'transfer_in', 'refund', 'tip') "
        "AND amount > 0) OR "
        "(type IN ('ride_payment', 'commission', 'transfer_out', 'withdrawal', "
        "'subscription_payment', 'tip_payment') AND amount < 0) OR "
        "(type IN ('adjustment') AND amount <> 0))"
    )
