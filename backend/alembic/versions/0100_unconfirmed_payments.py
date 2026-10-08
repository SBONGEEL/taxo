"""المدفوعاتُ غيرُ المؤكَّدة (`design/PAYMENTS-UNCONFIRMED.md`، SPEC §٦٤-ج، `design/APPROVALS-62.md` §٣) — الخطواتُ ١–٥ من §١٠.

**ما تضيفه**: قيمتا تعداد (`payment_status.voided` — طريقةٌ بدّلها الراكب، و`payment_confirmed_by.auto_rule` — قاعدةُ الإتمام
الآليّ للكاش)؛ وعمودٌ واحدٌ على الرحلة (`payment_method_hint`)؛ وأعمدةُ أثرٍ على الدفعة (الإقرار، التذكيراتُ بعددها ووقتها،
معاييرُ القاعدة مجمَّدة، الاعتراض، وقتُ التبديل) بقيودها وفهرسٍ جزئيٍّ لما ينتظر أحداً؛ وعتباتُ §٩ على `payment_settings`
بقيمها الابتدائية.

**تمسّ جدولَي مال — `payments` و`payment_settings` — بأعمدةٍ جديدةٍ فارغةٍ أو بافتراض، ولا تكتب صفّاً قائماً ولا تمسّ
الدفتر** (`wallet_transactions` لا يُلمس). **والصفوفُ القائمةُ تبقى كما هي حرفاً**: كلُّ عمودٍ جديدٍ فارغٌ أو صفر، والقيودُ
الجديدةُ تصحّ على كلِّ صفٍّ قائم (لا `declared_at` ولا `auto_rule` ولا اعتراضَ قبل اليوم).

**و`downgrade` مقيسٌ لا مقروء** (`tests/test_migrations.py`): يحذف الفهرسَ والقيودَ والأعمدةَ كلَّها. **وقيمتا التعداد لا
تُنزعان** — `ALTER TYPE … ADD VALUE` لا عكسَ له في Postgres (كـ`0092` و`0095` و`0097`)، **وصفٌّ بقيمةٍ منهما يُبقيها
مستعملةً** فلا يصحّ نزعُها ولو أمكن: دفعةٌ بُدِّلت أو أُتمّت آلياً سجلٌّ ماليٌّ لا يُمحى أثرُه بتراجع.

Revision ID: 0100
Revises: 0099
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0100"
down_revision = "0099"
branch_labels = None
depends_on = None

PAYMENT_CHECKS: dict[str, str] = {
    "payment_declared_cash_only": "declared_at IS NULL OR method::text = 'cash'",
    "payment_auto_rule_criteria": (
        "(COALESCE(confirmed_by::text, '') = 'auto_rule') = (auto_confirm_criteria IS NOT NULL)"
    ),
    "payment_objection_complete": (
        "(objected_at IS NULL) = (objection_reason IS NULL) "
        "AND (objected_at IS NULL OR confirmed_by::text = 'auto_rule')"
    ),
    "payment_reminders_not_negative": "driver_reminders >= 0 AND rider_reminders >= 0",
}

SETTING_CHECKS: dict[str, str] = {
    "payment_unconfirmed_thresholds_positive": (
        "cash_auto_confirm_hours > 0 AND cash_auto_confirm_max_amount > 0 "
        "AND cliq_reference_minutes > 0 "
        "AND driver_unconfirmed_block_count > 0 AND driver_unconfirmed_block_hours > 0 "
        "AND rider_unconfirmed_block_minutes > 0 "
        "AND rider_unpaid_rulings_cash_off > 0 AND rider_unpaid_rulings_window_days > 0 "
        "AND dispute_window_hours > 0"
    ),
    "payment_reminder_minutes_valid": (
        "jsonb_typeof(payment_reminder_minutes) = 'array' "
        "AND jsonb_array_length(payment_reminder_minutes) = 4 "
        "AND (payment_reminder_minutes->>0)::int > 0 "
        "AND (payment_reminder_minutes->>0)::int < (payment_reminder_minutes->>1)::int "
        "AND (payment_reminder_minutes->>1)::int < (payment_reminder_minutes->>2)::int "
        "AND (payment_reminder_minutes->>2)::int < (payment_reminder_minutes->>3)::int"
    ),
}

#: (الاسم، النوع، الافتراضُ في القاعدة) — **بالترتيب نفسِه في النموذج**
SETTING_COLUMNS: tuple[tuple[str, sa.types.TypeEngine, str], ...] = (
    ("payment_reminder_minutes", postgresql.JSONB(), "'[10, 120, 720, 1380]'::jsonb"),
    ("cash_auto_confirm_hours", sa.Integer(), "24"),
    ("cash_auto_confirm_max_amount", sa.Numeric(12, 3), "20.000"),
    ("cliq_reference_minutes", sa.Integer(), "30"),
    ("driver_unconfirmed_block_count", sa.Integer(), "3"),
    ("driver_unconfirmed_block_hours", sa.Integer(), "24"),
    ("rider_unconfirmed_block_minutes", sa.Integer(), "30"),
    ("rider_unpaid_rulings_cash_off", sa.Integer(), "2"),
    ("rider_unpaid_rulings_window_days", sa.Integer(), "90"),
    ("dispute_window_hours", sa.Integer(), "72"),
)


def upgrade() -> None:
    op.execute("ALTER TYPE payment_status ADD VALUE IF NOT EXISTS 'voided'")
    op.execute("ALTER TYPE payment_confirmed_by ADD VALUE IF NOT EXISTS 'auto_rule'")
    # **القيمتان تُثبَّتان قبل أن يقرأهما قيد** — `ADD VALUE` لا يُستعمل في المعاملة التي أضافته
    op.execute("COMMIT")

    op.add_column(
        "rides",
        sa.Column(
            "payment_method_hint",
            postgresql.ENUM(name="payment_method", create_type=False),
            nullable=True,
        ),
    )

    op.add_column("payments", sa.Column("declared_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "payments",
        sa.Column("driver_reminders", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column("payments", sa.Column("driver_reminded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "payments",
        sa.Column("rider_reminders", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column("payments", sa.Column("rider_reminded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payments", sa.Column("auto_confirm_criteria", postgresql.JSONB(), nullable=True))
    op.add_column("payments", sa.Column("objected_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payments", sa.Column("objection_reason", sa.String(length=255), nullable=True))
    op.add_column("payments", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    for name, condition in PAYMENT_CHECKS.items():
        op.create_check_constraint(name, "payments", condition)
    op.create_index(
        "ix_payments_unconfirmed",
        "payments",
        ["created_at"],
        postgresql_where=sa.text("status = 'pending' AND method IN ('cash', 'cliq')"),
    )

    for name, column_type, default in SETTING_COLUMNS:
        op.add_column(
            "payment_settings",
            sa.Column(name, column_type, server_default=sa.text(default), nullable=False),
        )
    for name, condition in SETTING_CHECKS.items():
        op.create_check_constraint(name, "payment_settings", condition)


#: **ما لا يقرؤه الكودُ القديم** — `pg_enum` بـ`validate_strings` يرمي `LookupError` على قيمةٍ لا يعرفها تعدادُه
_UNREADABLE_BY_0099 = (
    "SELECT count(*) FROM payments "
    "WHERE status::text = 'voided' OR confirmed_by::text = 'auto_rule'"
)


def downgrade() -> None:
    """يحذف ما أضافته الترحيلةُ كلَّه — **إلا قيمتي التعداد** (`voided` و`auto_rule`): لا عكسَ لـ`ADD VALUE` في Postgres.

    **والتراجعُ آمنٌ قبل أوّل إشعالٍ للمفتاح وحدَه** (مراجعةُ ٢٠٢٦-١٠-٠٧): ما إن يحمل صفٌّ `voided` (طريقةٌ بُدِّلت) أو
    `auto_rule` (إتمامٌ آليّ) **لا يقرؤه كودُ ما قبل 0100**: `models/base.pg_enum` يبني `SAEnum` بـ`validate_strings`، فقيمةٌ
    لا يعرفها التعدادُ ترمي `LookupError` — **وكلُّ قراءةٍ لدفعات تلك الرحلة تصير 500** (شاشةُ الدفع، وقائمةُ اللوحة،
    و`list_for_ride`). **فيقف التراجعُ هنا باسمه** بدل أن يُنتج مخطّطاً لا يقرؤه كودُه: الطريقُ حينها نسخةٌ تسبق الترحيلة،
    أو كودٌ يعرف القيمتين — **ولا يُعدَّل صفٌّ ماليٌّ ليمرّ التراجع** (القاعدةُ الثانية في `CLAUDE.md`).

    وتبقى القيمتان في النوعين بلا صفٍّ يحملهما حين يمرّ — **ولا تُنزعان ولو أمكن**: نوعٌ يُعاد بناؤه على جدول مالٍ قائمٍ أخطرُ
    من قيمتين لا يقرؤهما أحد.
    """
    leftovers = op.get_bind().execute(sa.text(_UNREADABLE_BY_0099)).scalar_one()
    if leftovers:
        raise RuntimeError(
            f"تراجعُ 0100 توقّف: {leftovers} صفَّ دفعٍ يحمل `voided` أو `auto_rule` — "
            "وكودُ ما قبل 0100 لا يقرؤهما (`LookupError` في `pg_enum`)، فكلُّ قراءةٍ لدفعات رحلاتها تصير 500. "
            "الطريقُ نسخةٌ تسبق الترحيلة، أو كودٌ يعرف القيمتين — ولا يُعدَّل صفٌّ ماليٌّ ليمرّ التراجع."
        )
    for name in SETTING_CHECKS:
        op.drop_constraint(op.f(f"ck_payment_settings_{name}"), "payment_settings", type_="check")
    for name, _type, _default in reversed(SETTING_COLUMNS):
        op.drop_column("payment_settings", name)

    op.drop_index("ix_payments_unconfirmed", table_name="payments")
    for name in PAYMENT_CHECKS:
        op.drop_constraint(op.f(f"ck_payments_{name}"), "payments", type_="check")
    for column in (
        "voided_at",
        "objection_reason",
        "objected_at",
        "auto_confirm_criteria",
        "rider_reminded_at",
        "rider_reminders",
        "driver_reminded_at",
        "driver_reminders",
        "declared_at",
    ):
        op.drop_column("payments", column)

    op.drop_column("rides", "payment_method_hint")
