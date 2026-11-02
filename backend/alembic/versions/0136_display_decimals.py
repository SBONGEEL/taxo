"""خاناتُ عرض المبالغ لكلِّ دولة (SPEC §٧٣-ج/٧، أمرُ المالك ٢٠٢٦-١١-٠٢) — **عمودٌ يُضاف على جدولٍ بلا مال، ولا صفَّ يتغيّر**.

`country_markets.display_decimals`: كم خانةً تُرسم بعد الفاصلة في التطبيقات واللوحة. **للعرض وحدَه** — لا يمسّ مبلغاً محفوظاً
ولا رصيداً ولا قيداً ولا تقريباً، والمالُ يُحسب بخانات عملته (`core/currency.CURRENCY_DECIMALS`) كما كان حرفاً.

**و`NULL` = خاناتُ العملة نفسُها** (الأردنيّ ٣ · الجزائريّ ٠ · الليبيّ ٣) — **فالإنتاجُ بعدها كما قبلها حرفاً**، ولا صفَّ يُبذر.

**والرجوعُ** حذفُ العمود: ما يضيع به اختيارُ عرضٍ لا مال، **ويُكتب في سجلّ التدقيق** قبل أن يضيع.

Revision ID: 0136
Revises: 0135
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0136"
down_revision = "0135"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("country_markets", sa.Column("display_decimals", sa.SmallInteger(), nullable=True))
    op.create_check_constraint(
        "country_markets_display_decimals_range",
        "country_markets",
        "display_decimals IS NULL OR display_decimals BETWEEN 0 AND 3",
    )


def downgrade() -> None:
    op.drop_constraint("country_markets_display_decimals_range", "country_markets", type_="check")
    op.drop_column("country_markets", "display_decimals")
