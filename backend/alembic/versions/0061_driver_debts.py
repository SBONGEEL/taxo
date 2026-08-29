"""دَينُ الكبتن — **بيتٌ ثالثٌ للدَّين، ومخرجٌ من طريقٍ مسدودٍ حيّ**.

## ولمَ لزم اليوم: بابٌ أُغلق فبقيت جملةٌ تحيل إليه

**قِيس 2026-08-30**: رحلةُ كاشٍ لا تكتب `ride_earning` (المالُ في يد الكبتن)،
**والعمولةُ تُخصم من محفظته قيداً سالباً** — و`wallet.record` يرفض
`balance_after < 0`، فتُرمى «رصيد محفظتك لا يغطي عمولة هذه الرحلة — **اشحن
المحفظة** ثم أكّد».

**وشحنُ محفظة الكبتن أُلغي** (قرارُ المالك 2026-08-29): لا مسارَ له في
`driver-app/src/api/endpoints.ts` البتّة. **فكبتنٌ رصيدُه دون العمولة لا يُنهي
رحلةَ كاشٍ أصلاً**، والجملةُ تدلّه على بابٍ ليس هناك. **وهذا عطبٌ حيٌّ لا
ميزةٌ مؤجّلة** — ولذلك يبدأ به البناء.

## والدَّينُ ليس رصيداً سالباً (قاعدةُ `advances` نفسُها)

**الحارسُ عند المصدر يبقى كما هو**: لا رصيدَ سالبَ إطلاقاً. والمستحقُّ يخرج من
الدفتر إلى **جدولٍ مستقلٍّ** يُقرأ ويُسدَّد ويُرفع منعُه — كما فعلت السلفةُ
(`driver_advances`) ورسمُ الإلغاء المحمول (`ride_cancellation_charges`).
**فهذا بيتُ دَينٍ ثالثٌ لا آلةٌ ثالثة**: العَلَمُ في صفِّ الكبتن يقرؤه التوزيعُ
مع أخويه، والتحصيلُ عند دخول المال، ورفعُ المنع في المسار نفسِه.

## ١) `driver_debts` — صفٌّ لكلِّ دفعةٍ استحقّت

**و`collected` عمودٌ لا صفوفُ سداد** (قرارُ المالك 2026-08-30: «السدادُ
الجزئيّ يُقبل ويُنقص الدَّين»): الجزئيُّ **حالةٌ في الصفّ** لا جدولٌ رابع،
والمنعُ يُرفع عند **الصفر** لا قبله — `amount - collected = 0`.

**والفريدُ `(payment_id, source)`**: تسويةٌ تُعاد لا تكتب دَيناً ثانياً —
والحمايةُ في القاعدة لا في الكود، كما `uq_provider_orders_cart_id`.

**و`source` معلَنٌ من أوّل يوم وفيه عضوٌ واحد**: «كلُّ ما يستحقّ من الرحلة»
(قرارُ المالك) — واليومَ عمولةُ ما يُقبض مباشرةً وحدَها هي ما يستحقّ. **وعمودٌ
مصرَّحٌ بعضوٍ واحدٍ أرخصُ من ترحيلةٍ يومَ يصير عضوان.**

## ٢) `drivers.debt_blocked` — **العَلَمُ الثالث، ويُقرأ حيث يُقرأ أخواه**

`dispatch.py` يقرأ `advance_blocked` و`cancellation_carry_blocked` في شرط
الأهلية نفسِه — **فالثالثُ يجلس بينهما ولا يُخترع له مسار**.

## ٣) `payment_settings.driver_debt_ceiling` — **سقفٌ فارغٌ عمداً**

**`NULL` تعني «لا سقفَ»** لا «صفراً» (قرارُ المالك 2026-08-30: «ولا تضعه حتى
أقرّه»). **والفرقُ ماليٌّ لا شكليّ**: صفرٌ يحجب كلَّ كبتنٍ عليه فلسٌ واحد.
فيُبنى المسارُ كاملاً ويبقى **معطَّلاً حتى يُكتب الرقم**، ولا يُحجب أحدٌ اليوم.

Revision ID: 0061
Revises: 0060
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None

COUNTRY = postgresql.ENUM(name="country_code", create_type=False)
CURRENCY = postgresql.ENUM(name="currency", create_type=False)

SOURCE = postgresql.ENUM(
    "ride_commission", name="driver_debt_source", create_type=False
)
STATUS = postgresql.ENUM(
    "outstanding", "settled", "written_off", name="driver_debt_status",
    create_type=False,
)


def upgrade() -> None:
    SOURCE.create(op.get_bind(), checkfirst=True)
    STATUS.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "driver_debts",
        # **بلا `server_default`**: `UUIDMixin` يولّد المفتاحَ في بايثون
        # (`default=uuid.uuid4`) — وافتراضٌ في القاعدة لا يقابله افتراضٌ في
        # النموذج **يُقرأ انحرافاً** ويُسقط `test_migrations_match_models`.
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "driver_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("drivers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("country_code", COUNTRY, nullable=False),
        sa.Column("source", SOURCE, nullable=False),
        sa.Column("amount", sa.Numeric(12, 3), nullable=False),
        # **المحصَّلُ منه** — والجزئيُّ حالةٌ في الصفّ لا جدولٌ رابع
        sa.Column(
            "collected", sa.Numeric(12, 3), nullable=False, server_default="0"
        ),
        sa.Column("currency", CURRENCY, nullable=False),
        sa.Column(
            "ride_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rides.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "payment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status", STATUS, nullable=False, server_default="outstanding"
        ),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("written_off_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "written_off_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("writeoff_reason", sa.String(length=300), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("amount > 0", name="driver_debt_amount_positive"),
        # **لا محصَّلَ سالبٌ ولا فوق الأصل** — والقيدُ في القاعدة لا في الكود
        sa.CheckConstraint(
            "collected >= 0 AND collected <= amount",
            name="driver_debt_collected_within",
        ),
        # **دفعةٌ واحدةٌ تُنشئ دَيناً واحداً** — تسويةٌ تُعاد لا تضاعفه
        sa.UniqueConstraint(
            "payment_id", "source", name="driver_debt_once_per_payment"
        ),
    )
    # **ما يُقرأ في كلِّ تسوية**: القائمُ على كبتنٍ بعينه
    op.create_index(
        "driver_debt_outstanding",
        "driver_debts",
        ["driver_id"],
        postgresql_where=sa.text("status = 'outstanding'"),
    )

    op.add_column(
        "drivers",
        sa.Column(
            "debt_blocked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # **`NULL` = لا سقف** — ولا يُحجب أحدٌ حتى يُكتب الرقم
    op.add_column(
        "payment_settings",
        sa.Column("driver_debt_ceiling", sa.Numeric(12, 3), nullable=True),
    )
    op.create_check_constraint(
        "payment_debt_ceiling_positive",
        "payment_settings",
        "driver_debt_ceiling IS NULL OR driver_debt_ceiling > 0",
    )

    # ## **وتقاربٌ لقاعدةٍ سبقت التصحيح** (2026-08-30)
    #
    # **الترحيلةُ `0060` شُحنت بافتراضِ `gen_random_uuid()` على مفاتيحها
    # الثلاثة ولم تُشغَّل عليها `tests/test_migrations.py`** — فبقي الانحرافُ
    # مستوراً يوماً كاملاً. وقد صُحِّح نصُّها، **لكن قاعدةً رُقّيت قبل التصحيح
    # تحمل الافتراضَ ولا يزيله تصحيحُ نصٍّ ماضٍ**.
    #
    # **فالإزالةُ هنا لتتقارب القاعدتان**: من رقّى أمسِ ومن يرقّي اليوم ينتهيان
    # إلى الشكل نفسِه. **و`DROP DEFAULT` بلا افتراضٍ لا شيءَ**، فالتكرارُ آمن.
    for table in ("privacy_policies", "user_policy_consents", "org_profile"):
        op.execute(f"ALTER TABLE {table} ALTER COLUMN id DROP DEFAULT")

    # **غرضٌ رابعٌ للطلب**: سدادُ دَينٍ بكليك — قضيبُ `cliq_subscriptions` نفسُه
    op.execute("ALTER TYPE provider_order_purpose ADD VALUE IF NOT EXISTS 'debt'")


def downgrade() -> None:
    # **قيمةُ التعداد لا تُنزع** (قاعدةُ المشروع) — والنوعُ يسقط مع من أنشأه
    op.drop_constraint(
        "payment_debt_ceiling_positive", "payment_settings", type_="check"
    )
    op.drop_column("payment_settings", "driver_debt_ceiling")
    op.drop_column("drivers", "debt_blocked")
    op.drop_index("driver_debt_outstanding", table_name="driver_debts")
    op.drop_table("driver_debts")
    STATUS.drop(op.get_bind(), checkfirst=True)
    SOURCE.drop(op.get_bind(), checkfirst=True)
