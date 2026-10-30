"""رمزُ البنك ورسالتُه على طلب الدفع (SPEC §٨٥/٩، أمرُ المالك ٢٠٢٦-١٠-٣٠) — **عمودان يُضافان، ولا صفَّ يتغيّر**.

طلبٌ حقيقيٌّ رُفض بـ`respCode AB` (CVV خاطئ) ولم يرَ صاحبُه إلا «رفض الوسيطُ الدفع». السببُ العربيُّ يُكتب في `rejection_reason` كما كان،
**والرمزُ والرسالةُ الخامّةُ هنا للّوحة والدعم وحدَهما**. الجدولُ `payment_requests` يحمل مبالغَ لكنّ العمودين وصفيّان ولا يمسّان قيداً ولا
رصيداً؛ **والرجوعُ** حذفُهما (فارغان لكلِّ طلبٍ قائم).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0135"
down_revision = "0134"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payment_requests", sa.Column("gateway_code", sa.String(length=32), nullable=True))
    op.add_column("payment_requests", sa.Column("gateway_message", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("payment_requests", "gateway_message")
    op.drop_column("payment_requests", "gateway_code")
