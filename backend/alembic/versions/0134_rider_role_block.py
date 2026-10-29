"""حظرُ دور الراكب وحدَه (أمرُ المالك ٢٠٢٦-١٠-٢٩، SPEC §21.6) — **عمودان يُضافان، ولا صفَّ يتغيّر**.

الرقمُ نفسُه راكباً وكبتناً، و«حظرُ دورٍ لا يحظر الآخر إلا إن اختار المالكُ حظرَ الشخص»: حظرُ الكبتن قائمٌ (`drivers.status`
موقوف)، وحظرُ الشخص قائمٌ (`users.is_blocked`)، **والناقصُ حظرُ الراكب وحدَه** — فهذان العمودان، فارغين لكلِّ حسابٍ قائم.
**ولا جدولَ مال**، **والرجوعُ** حذفُ العمودين (لا قيمةَ فيهما قبل أن يُستعملا).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0134"
down_revision = "0133"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("rider_blocked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("rider_block_reason", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "rider_block_reason")
    op.drop_column("users", "rider_blocked_at")
