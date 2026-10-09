"""شارةُ «جديد» على بطاقات الخدمات، ومفتاحُ قسم الأسئلة (SPEC §٧١-ج/٨–٩، أمرُ المالك ٢٠٢٦-١٠-٠٩).

**ما تضيفه** إلى `site_settings`:
- `new_cards` — مفاتيحُ البطاقات التي تُرسم بها «جديد»، **والستُّ كلُّها افتراضاً**: الصفُّ القائمُ يأخذها من الافتراض نفسِه
  (قسمُ «الخدمات الجديدة» كلُّه جديد)، والمشرفُ ينزعها من اللوحة.
- `faq_enabled` — **مطفأٌ**: الأسئلةُ تُكتب وتُراجع ولا تُرسم ولا تُنشر حتى يُشعَل.

**ولا يمسّ جدولَ مال**، ولا يغيّر قيمةً قائمة — عمودان بافتراض.

Revision ID: 0106
Revises: 0105
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0106"
down_revision = "0105"
branch_labels = None
depends_on = None

_CARDS = '\'["airport", "guaranteed_booking", "parcel", "hourly", "intercity", "ride_for_other"]\'::jsonb'


def upgrade() -> None:
    op.add_column(
        "site_settings",
        sa.Column("new_cards", postgresql.JSONB(), nullable=False, server_default=sa.text(_CARDS)),
    )
    op.add_column(
        "site_settings",
        sa.Column("faq_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("site_settings", "faq_enabled")
    op.drop_column("site_settings", "new_cards")
