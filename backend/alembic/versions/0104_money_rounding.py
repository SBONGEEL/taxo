"""لا كسورَ في المال: التقريبُ إلى وحدة الدولة (SPEC §٧٠) — **الإعدادُ والسجلُّ ونوعُ قيدٍ واحد، والتقريبُ مطفأٌ في كلِّ سوق**.

**ما تضيفه**:
- `payment_settings`: `rounding_enabled` (**مطفأٌ في السوقين**) · `rounding_unit` (`0.500`) · `rounding_mode` (`nearest`) ·
  `rounding_enabled_at`. **وإشعالُ الأردن ليس هنا**: كتابةٌ على الإنتاج يُقرّها المالك بعد الرفع (§٧٠-ب)، **وليبيا لا يُمسّ صفُّها**.
- `rides`: `rounding_unit_at_ride` · `rounding_mode_at_ride` — **سياسةُ العرض مجمَّدةً لحظةَ الطلب** (العدّادُ يُبنى في بثٍّ بلا
  جلسة)، **ولرحلة الساعة لحظةَ البدء** (بها قُرِّب المقدَّم وبها يُقرَّب الباقي). `NULL` لكلِّ رحلةٍ قائمة = لا تقريب، كما كانت.
- `provider_orders`: `rounding_precise` · `rounding_unit_at_open` · `rounding_mode_at_open` — **ثمنُ الاشتراك بدقّته وسياستُه
  مجمَّدان عند فتح الطلب** (البطاقة وكليك اليدويّ)، فيُكتب صفُّ السجلّ عند التفعيل منهما لا من إعداد لحظته. `NULL` لكلِّ طلبٍ قائم.
- `money_roundings`: **سجلٌّ يُضاف إليه ولا يُعدَّل ولا يُحذف** (مشغّلٌ كمشغّل الدفتر في `0006`) — صفٌّ لكلِّ فرق تقريب،
  **ومفتاحٌ فريدٌ على المصدر**.
- `wallet_transaction_type`: **`rounding` بالإشارتين** كالتصحيح (§٧٠-ج/٦)، ومعه إعادةُ بناء قيد الإشارة كما في `0097`.

**ولا رصيدَ ولا قيدَ قائمٌ يُمسّ**: أعمدةٌ بافتراضٍ وجدولٌ فارغٌ وقيمةُ تعداد — **لا `UPDATE` على صفٍّ قائم**.

**و`downgrade` مقيسٌ لا مقروء** (`tests/test_migrations.py`): قيمةُ التعداد لا تُنزع (PostgreSQL)، **وقيدٌ بها يُسقط النزولَ
عمداً** — نزولٌ يمحو قيداً بنوعٍ لم يعد يعرفه أسوأُ من نزولٍ يقف.

Revision ID: 0104
Revises: 0103
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0104"
down_revision = "0103"
branch_labels = None
depends_on = None

#: **قائمتا `0097` حرفاً** — والجديدُ يُضاف إلى ذات الإشارتين لا إليهما
CREDITS = (
    "topup", "ride_earning", "transfer_in", "refund", "tip", "referral_bonus", "advance",
    "cancellation_compensation", "guarantee_fee", "guarantee_refund", "guarantee_compensation",
    "commute_credit", "commute_incentive", "intercity_refund", "intercity_earning", "cashback",
)
DEBITS = (
    "ride_payment", "commission", "transfer_out", "withdrawal", "subscription_payment", "tip_payment",
    "advance_repayment", "cancellation_fee", "skin_purchase", "guarantee_hold", "guarantee_penalty", "commute_prepay",
    "intercity_hold",
)
SIGNED_BEFORE = ("adjustment",)
SIGNED_AFTER = ("adjustment", "rounding")

ROUNDING_MODES = "('nearest', 'up', 'down')"


def _sign_constraint(signed: tuple[str, ...]) -> str:
    def listed(values: tuple[str, ...]) -> str:
        return ", ".join(f"'{value}'" for value in values)

    return (
        f"(type IN ({listed(CREDITS)}) AND amount > 0) OR "
        f"(type IN ({listed(DEBITS)}) AND amount < 0) OR "
        f"(type IN ({listed(signed)}) AND amount <> 0)"
    )


def _rebuild(signed: tuple[str, ...]) -> None:
    op.drop_constraint(
        op.f("ck_wallet_transactions_wallet_amount_sign_by_type"), "wallet_transactions", type_="check"
    )
    op.create_check_constraint("wallet_amount_sign_by_type", "wallet_transactions", _sign_constraint(signed))


def upgrade() -> None:
    # ── نوعُ القيد أوّلاً — `ADD VALUE` لا يُستعمل في معاملته، فيُختم قبل ما يقرؤه (نمطُ `0097`)
    op.execute("ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS 'rounding'")
    op.execute("COMMIT")
    _rebuild(SIGNED_AFTER)

    # ── الإعدادُ لكلِّ سوق — **مطفأٌ في الصفوف القائمة كلِّها** بافتراض العمود، ولا `UPDATE` يُشعل شيئاً
    op.add_column(
        "payment_settings",
        sa.Column("rounding_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "payment_settings",
        sa.Column("rounding_unit", sa.Numeric(12, 3), server_default=sa.text("0.500"), nullable=False),
    )
    op.add_column(
        "payment_settings",
        sa.Column("rounding_mode", sa.String(length=8), server_default=sa.text("'nearest'"), nullable=False),
    )
    op.add_column(
        "payment_settings",
        sa.Column("rounding_enabled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "payment_rounding_valid",
        "payment_settings",
        f"rounding_unit > 0 AND rounding_mode IN {ROUNDING_MODES}",
    )

    # ── سياسةُ العرض على الرحلة — `NULL` لكلِّ قائمة (لا إعادةَ كتابةٍ للجدول: عمودان بلا افتراض)
    op.add_column("rides", sa.Column("rounding_unit_at_ride", sa.Numeric(12, 3), nullable=True))
    op.add_column("rides", sa.Column("rounding_mode_at_ride", sa.String(length=8), nullable=True))
    op.create_check_constraint(
        "ride_rounding_policy",
        "rides",
        "(rounding_unit_at_ride IS NULL) = (rounding_mode_at_ride IS NULL) "
        "AND (rounding_unit_at_ride IS NULL OR rounding_unit_at_ride > 0) "
        f"AND (rounding_mode_at_ride IS NULL OR rounding_mode_at_ride IN {ROUNDING_MODES})",
    )

    # ── ثمنُ الاشتراك وسياستُه مجمَّدان على طلبه عند الفتح (البطاقة وكليك اليدويّ) — `NULL` لكلِّ طلبٍ قائم، فلا إعادةَ كتابة
    op.add_column("provider_orders", sa.Column("rounding_precise", sa.Numeric(12, 3), nullable=True))
    op.add_column("provider_orders", sa.Column("rounding_unit_at_open", sa.Numeric(12, 3), nullable=True))
    op.add_column("provider_orders", sa.Column("rounding_mode_at_open", sa.String(length=8), nullable=True))
    op.create_check_constraint(
        "provider_order_rounding_frozen",
        "provider_orders",
        "(rounding_precise IS NULL) = (rounding_unit_at_open IS NULL) "
        "AND (rounding_unit_at_open IS NULL) = (rounding_mode_at_open IS NULL) "
        "AND (rounding_unit_at_open IS NULL OR rounding_unit_at_open > 0) "
        f"AND (rounding_mode_at_open IS NULL OR rounding_mode_at_open IN {ROUNDING_MODES})",
    )

    # ── السجلّ
    op.create_table(
        "money_roundings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", postgresql.ENUM("LY", "JO", name="country_code", create_type=False), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("precise", sa.Numeric(12, 3), nullable=False),
        sa.Column("rounded", sa.Numeric(12, 3), nullable=False),
        sa.Column("difference", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.Numeric(12, 3), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "difference = rounded - precise AND difference <> 0",
            name=op.f("ck_money_roundings_money_rounding_difference"),
        ),
        sa.CheckConstraint(
            f"unit > 0 AND mode IN {ROUNDING_MODES}",
            name=op.f("ck_money_roundings_money_rounding_policy"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_money_roundings_user_id_users"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_money_roundings")),
        sa.UniqueConstraint("source_kind", "source_id", name=op.f("uq_money_roundings_source_kind_source_id")),
    )
    op.create_index(op.f("ix_money_roundings_user_id"), "money_roundings", ["user_id"])
    op.create_index("ix_money_roundings_country_created", "money_roundings", ["country_code", "created_at"])
    # **يُضاف إليه ولا يُعدَّل ولا يُحذف** — مشغّلُ الدفتر (`0006`) بعينه. و`TRUNCATE` لا يمرّ بمشغّلات الصفوف، فكنسُ
    # الاختبارات يبقى عاملاً
    op.execute(
        """
        CREATE FUNCTION money_roundings_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'money_roundings is append-only (%)', TG_OP;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER money_roundings_append_only
        BEFORE UPDATE OR DELETE ON money_roundings
        FOR EACH ROW EXECUTE FUNCTION money_roundings_append_only()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS money_roundings_append_only ON money_roundings")
    op.execute("DROP FUNCTION IF EXISTS money_roundings_append_only()")
    op.drop_index("ix_money_roundings_country_created", table_name="money_roundings")
    op.drop_index(op.f("ix_money_roundings_user_id"), table_name="money_roundings")
    op.drop_table("money_roundings")

    op.drop_constraint(op.f("ck_provider_orders_provider_order_rounding_frozen"), "provider_orders", type_="check")
    op.drop_column("provider_orders", "rounding_mode_at_open")
    op.drop_column("provider_orders", "rounding_unit_at_open")
    op.drop_column("provider_orders", "rounding_precise")

    op.drop_constraint(op.f("ck_rides_ride_rounding_policy"), "rides", type_="check")
    op.drop_column("rides", "rounding_mode_at_ride")
    op.drop_column("rides", "rounding_unit_at_ride")

    op.drop_constraint(op.f("ck_payment_settings_payment_rounding_valid"), "payment_settings", type_="check")
    op.drop_column("payment_settings", "rounding_enabled_at")
    op.drop_column("payment_settings", "rounding_mode")
    op.drop_column("payment_settings", "rounding_unit")
    op.drop_column("payment_settings", "rounding_enabled")

    # **قيدٌ بنوع `rounding` يُسقط هذا السطرَ عمداً** — والقيمةُ نفسُها تبقى في التعداد (لا تُنزع في PostgreSQL)
    _rebuild(SIGNED_BEFORE)
