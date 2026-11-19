"""**عرضُ المبلغ الصحيح بلا كسور** (أمرُ المالك ٢٠٢٦-١١-١٩، ورقةُ «نبحث لك عن كبتن»): «8 د.ل» لا «8.000 د.ل»، و«8.50 د.ل» حين يكون كسر.

عمودٌ واحدٌ على `country_markets` — **إعدادُ عرضٍ لا مال**: لا مبلغَ محفوظاً يتغيّر ولا تقريبَ ولا أجرة؛ الخلفيّةُ تحسب وتخزّن كما كانت،
والتطبيقان واللوحةُ يرسمون. **وليبيا تبدأ به** بخانتين للكسر كما أمر المالك؛ والأردنُّ والجزائرُ لا يتغيّر فيهما شيء.

**والرجوعُ** يحذف العمود؛ وخاناتُ ليبيا تبقى خانتين (عرضٌ لا يُخفي خانةً غيرَ صفريّة أبداً)، ويُعيدها المشرفُ من صفحة التقريب إن شاء.

Revision ID: 0177
Revises: 0176
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0177"
down_revision = "0176"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "country_markets",
        sa.Column("display_trim_whole", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    # **تحديثٌ لا إدراج** — صفُّ ليبيا قائمٌ منذ `0173`؛ وإدراجُه هنا كان سيكتب `signup_display` افتراضيّاً في دولةٍ ظهورُها قرارُ المالك
    op.execute(
        "UPDATE country_markets SET display_decimals = 2, display_trim_whole = true, updated_at = now() WHERE country_code = 'LY'"
    )


def downgrade() -> None:
    op.drop_column("country_markets", "display_trim_whole")
