"""الرقمُ الكبيرُ في اللافتة (`promo_banners.headline`) — «30%» في لافتة الرئيسية R05 (SPEC §٦٢-ج/٢٦).

**عمودٌ فارغٌ يُضاف ولا يُملأ لما سبق**: اللافتاتُ القائمةُ بلا رقمٍ كبير (`NULL`) فتُرسم كما كانت حرفاً — **ولا رقمَ يُستخرج من
عنوانها**. **وليس جدولَ مال**: اللافتةُ محتوى، و«30%» نصٌّ يكتبه المشرفُ لا خصمٌ يُحسب (الخصمُ في عقد الكوبون وحدَه).
**و`downgrade` يحذف العمود** — وثمنُه: يختفي الرقمُ الكبيرُ من اللافتة؛ لا شيءَ غيرُه.

Revision ID: 0088
Revises: 0087
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0088"
down_revision = "0087"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("promo_banners", sa.Column("headline", sa.String(8), nullable=True))


def downgrade() -> None:
    op.drop_column("promo_banners", "headline")
