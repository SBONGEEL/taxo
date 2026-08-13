"""قناةُ `share` لخصم المشاركة (المرحلة 12-ي)

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-13 09:20:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # قيمةٌ جديدةٌ على نوعٍ قائم — لا نوعَ جديد، و`IF NOT EXISTS` يجعلها قابلةً
    # للإعادة بعد تراجعٍ جزئي (التراجعُ لا يُسقط النوع لأن جدولَه باقٍ).
    #
    # **ولا تُستعمل القيمةُ في هذه الترحيلة**: postgres يسمح بإضافتها داخل
    # معاملة ويمنع استعمالَها فيها — ولا قيدَ هنا يحتاجها، فلا حاجة إلى حيلة
    # `::text` التي لجأت إليها `0009`.
    op.execute("ALTER TYPE payment_method ADD VALUE IF NOT EXISTS 'share'")

    # النسبةُ المجمَّدةُ على الرحلة — إضافةُ عمودٍ لا تستعمل القيمةَ الجديدة،
    # فتجوز في المعاملة نفسِها
    op.add_column(
        "rides",
        sa.Column(
            "share_discount_percent_at_ride",
            sa.Numeric(precision=5, scale=2),
            server_default="0",
            nullable=False,
        ),
    )
    # الاسمُ **بلا بادئة**: اصطلاحُ التسمية في `models/base.py` يضيف `ck_rides_`
    # بنفسه، وتمريرُ الاسم كاملاً ينتج `ck_rides_ck_rides_…` — وهو ما أسقط
    # `test_migrations_match_models`
    op.create_check_constraint(
        "ride_share_discount_percent_range",
        "rides",
        "share_discount_percent_at_ride >= 0 "
        "AND share_discount_percent_at_ride <= 100",
    )


def downgrade() -> None:
    # بلا بادئةٍ كذلك: الاصطلاحُ يضيفها في الإسقاط كما يضيفها في الإنشاء
    op.drop_constraint(
        "ride_share_discount_percent_range", "rides", type_="check"
    )
    op.drop_column("rides", "share_discount_percent_at_ride")
    # postgres لا يحذف قيمةً من ENUM. والنوعُ نفسُه تُسقطه الترحيلةُ التي
    # أنشأته (`0007`)، فيبقى التراجعُ هنا بلا عمل — وهو ما يجعل `IF NOT EXISTS`
    # أعلاه شرطَ إعادةِ الترقية بعد تراجعٍ جزئي.
    pass
