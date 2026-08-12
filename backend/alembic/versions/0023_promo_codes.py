"""الكوبونات والخصومات (SPEC القسم 6.6، المرحلة 12-ز)

جدولٌ واحد، وأربعةُ حقولٍ مجمَّدةٍ على الرحلة، **وقيمةُ قناةٍ جديدة في
`payment_method`** — وهي القرارُ المحوريّ: الخصمُ صفُّ دفعةٍ لا نقصٌ في الأجرة.

**وفخُّ `0018` هنا أيضاً**: `ALTER TYPE ... ADD VALUE` لا تُستعمل قيمتُها في نفس
المعاملة، ولا شيءَ في هذه الترحيلة يستعملها — لا قيدَ CHECK ولا فهرسٌ جزئي — فلا
حاجةَ إلى COMMIT صريح. والنوعُ الجديد `promo_discount_type` يُنشأ بالجدول
ويُسقَط في `downgrade` (وإلا فشل الترقيةُ الثانية).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DISCOUNT_TYPE = postgresql.ENUM(
    "percent", "fixed", name="promo_discount_type", create_type=False
)


def upgrade() -> None:
    # (1) قناةُ الخصم. لا شيءَ بعدها في هذه الترحيلة يستعملها، فلا COMMIT
    op.execute("ALTER TYPE payment_method ADD VALUE IF NOT EXISTS 'promo'")

    DISCOUNT_TYPE.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "promo_codes",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column(
            "country_code",
            postgresql.ENUM(name="country_code", create_type=False),
            nullable=False,
        ),
        sa.Column("discount_type", DISCOUNT_TYPE, nullable=False),
        sa.Column("discount_value", sa.Numeric(12, 3), nullable=False),
        # سقفُ خصمِ النسبة — `null` يعني «الأجرة كلها» وهو ما يجعل «مجاناً» ممكناً
        sa.Column("max_discount", sa.Numeric(12, 3), nullable=True),
        sa.Column("budget_total", sa.Numeric(12, 3), nullable=False),
        sa.Column("per_user_limit", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("total_usage_limit", sa.Integer(), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("created_by", sa.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        # **الرمزُ فريدٌ لكل دولة**: حملةٌ في سوقٍ لا تمنع اسمَها في الآخر،
        # والمطابقةُ تكون بالرمز والدولة معاً فلا يُستعمل رمزُ الأردن في ليبيا
        sa.UniqueConstraint("country_code", "code", name="uq_promo_codes_country_code"),
        sa.CheckConstraint("discount_value > 0", name="promo_value_positive"),
        sa.CheckConstraint("budget_total >= 0", name="promo_budget_not_negative"),
        sa.CheckConstraint("per_user_limit > 0", name="promo_per_user_positive"),
        sa.CheckConstraint(
            "max_discount IS NULL OR max_discount > 0", name="promo_cap_positive"
        ),
        # نسبةٌ فوق المئة ليست خصماً بل هديةٌ تتجاوز الأجرة
        sa.CheckConstraint(
            "discount_type <> 'percent' OR discount_value <= 100",
            name="promo_percent_within_hundred",
        ),
    )

    # (2) الحقولُ المجمَّدة على الرحلة — **القاعدةُ لا المبلغ** (القسم 6.6)
    op.add_column(
        "rides", sa.Column("promo_code_id", sa.UUID(as_uuid=True), nullable=True)
    )
    op.add_column("rides", sa.Column("promo_type_at_ride", DISCOUNT_TYPE, nullable=True))
    op.add_column(
        "rides", sa.Column("promo_value_at_ride", sa.Numeric(12, 3), nullable=True)
    )
    op.add_column(
        "rides", sa.Column("promo_cap_at_ride", sa.Numeric(12, 3), nullable=True)
    )
    op.create_foreign_key(
        "fk_rides_promo_code_id_promo_codes",
        "rides",
        "promo_codes",
        ["promo_code_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # يُستعلَم به عند كل تطبيقٍ (عدُّ الاستعمال) وكل قراءةِ مصروف
    op.create_index("ix_rides_promo_code_id", "rides", ["promo_code_id"])


def downgrade() -> None:
    op.drop_index("ix_rides_promo_code_id", table_name="rides")
    op.drop_constraint("fk_rides_promo_code_id_promo_codes", "rides", type_="foreignkey")
    for column in (
        "promo_cap_at_ride",
        "promo_value_at_ride",
        "promo_type_at_ride",
        "promo_code_id",
    ):
        op.drop_column("rides", column)

    op.drop_table("promo_codes")
    # النوعُ يُسقطه من أنشأه، وإلا فشلت الترقيةُ الثانية بـ«type already exists»
    DISCOUNT_TYPE.drop(op.get_bind(), checkfirst=True)

    # قيمةُ ENUM لا تُحذف في postgres؛ وأثرُها الوحيد صفوفُ دفعاتٍ بقناة `promo`
    # تُحذف قبل النزول — صفٌّ بقناةٍ لا يعرفها الكود الأقدم أسوأ من غيابه
    op.execute("DELETE FROM payments WHERE method = 'promo'")
