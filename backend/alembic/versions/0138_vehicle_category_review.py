"""فئةُ المركبة يقرّرها المشرف (أمرُ المالك ٢٠٢٦-١١-٠٢، SPEC §٩١-ب) — **أعمدةٌ بلا مال، ولا صفَّ يتغيّر**.

- `vehicles.category_confirmed_at` · `category_confirmed_by` — **أكّد مشرفٌ فئةَ هذه المركبة؟** فارغٌ لكلِّ مركبةٍ قائمة: فئتُها اليومَ
  **مؤقّتةٌ تعمل كما كانت**، وتظهر في «بحاجة لمراجعة الفئة» حتى يؤكّدها مشرف — **فلا يفقد كبتنٌ عملَه بالترحيلة**.
- `ride_categories.name_fr` · `name_en` — **اسمُ الفئة بالفرنسيّة والإنجليزيّة** (فارغٌ = الاسمُ العربيّ كما اليوم).
- `ride_categories.guidance` · `suggest_models` — **إرشادُ التعيين**: نصٌّ للمشرف، وطُرزٌ تُقترح لها الفئة (مع `min_year` القائم).
- `ride_categories.serves_lower` — **أيأخذ كبتنُ هذه الفئة طلباتِ ما دونها؟** `false` لكلِّ صفّ: التوزيعُ كما هو اليوم حرفاً.

**والرجوعُ** حذفُها: تعود الفئةُ اختياراً بلا تأكيد، **ولا رحلةَ ولا سعرَ ولا رصيدَ يمسّه شيء**.

Revision ID: 0138
Revises: 0137
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0138"
down_revision = "0137"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vehicles", sa.Column("category_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "vehicles",
        sa.Column(
            "category_confirmed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("ride_categories", sa.Column("name_fr", sa.String(length=40), nullable=True))
    op.add_column("ride_categories", sa.Column("name_en", sa.String(length=40), nullable=True))
    op.add_column("ride_categories", sa.Column("guidance", sa.String(length=500), nullable=True))
    op.add_column(
        "ride_categories",
        sa.Column("suggest_models", postgresql.ARRAY(sa.String(length=60)), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "ride_categories",
        sa.Column("serves_lower", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("ride_categories", "serves_lower")
    op.drop_column("ride_categories", "suggest_models")
    op.drop_column("ride_categories", "guidance")
    op.drop_column("ride_categories", "name_en")
    op.drop_column("ride_categories", "name_fr")
    op.drop_column("vehicles", "category_confirmed_by")
    op.drop_column("vehicles", "category_confirmed_at")
