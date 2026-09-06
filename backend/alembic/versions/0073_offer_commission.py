"""نسبةُ العمولة على العرض — **البند ٥٥** (٢٠٢٦-٠٩-٠٦).

**و`NULL` ليست صفراً**: عرضٌ يخصم من السعر وحدَه يبقى كما هو، **وعرضٌ يمنح
صفراً يقولها صراحةً** — وحالان لا يحملهما رقمٌ واحد.

**ولا قيمةَ افتراضيةَ على الصفوف القائمة**: كلُّها تبقى `NULL` **فلا يتغيّر
سلوكُ عرضٍ منشورٍ بترحيلة** — والترحيلةُ تضيف بابَ اختيارٍ لا تفتحه.

Revision ID: 0073
Revises: 0072
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscription_offers",
        sa.Column("commission_percent", sa.Numeric(5, 2), nullable=True),
    )
    # **والحدُّ في القاعدة لا في المخطَّط وحدَه**: مخطَّطٌ يحرس بابَه، **وصفٌّ
    # يُكتب من سكربتٍ أو يدٍ يمرّ من تحته** — والنسبةُ مالٌ.
    op.create_check_constraint(
        "commission_percent_range",
        "subscription_offers",
        "commission_percent IS NULL OR (commission_percent >= 0 AND commission_percent <= 100)",
    )


def downgrade() -> None:
    op.drop_constraint(
        # **بلا بادئة هنا أيضاً**: `drop_constraint` يطبّق الاصطلاح نفسَه،
        # فاسمٌ كاملٌ يصير مُضاعَفَ البادئة ثمّ يُبتر — ولا يجده.
        "commission_percent_range",
        "subscription_offers",
        type_="check",
    )
    op.drop_column("subscription_offers", "commission_percent")
