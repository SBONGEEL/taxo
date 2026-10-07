"""رمزُ الرحلة (`rides.start_code`) — أربعُ خاناتٍ تُدخلها الكبتنةُ قبل بدء الرحلة النسائية (SPEC §٦٢-ج/٥).

**عمودٌ فارغٌ يُضاف ولا يُملأ لما سبق**: الرحلاتُ القائمةُ بلا رمز (`NULL`) فتبدأ كما كانت حرفاً — **والمفتاحُ مطفأٌ افتراضاً**،
فلا رمزَ يُولَّد حتى يُشعله المالكُ لسوق. **وليس جدولَ مال**: الرمزُ شرطُ بدءٍ لا مبلغ، ولا يمسّ أجرةً ولا دفعة.
**و`downgrade` يحذف العمود** — وثمنُه: رحلةٌ نسائيةٌ جاريةٌ مقبولةٌ برمزٍ تبدأ بلا رمز؛ لا شيءَ غيرُه.

Revision ID: 0089
Revises: 0088
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0089"
down_revision = "0088"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rides", sa.Column("start_code", sa.String(4), nullable=True))


def downgrade() -> None:
    op.drop_column("rides", "start_code")
