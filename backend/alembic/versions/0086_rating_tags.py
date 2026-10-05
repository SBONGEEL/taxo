"""وسومُ التقييم (`ratings.tags`) — R10 «قيادة آمنة · سيارة نظيفة · ودود · وصل بسرعة · يعرف الطريق» (SPEC §٦٢-ج/٢٥).

**مصفوفةٌ فارغةٌ افتراضاً** فكلُّ تقييمٍ قائمٍ بلا وسوم كما كان. لا مالَ هنا.
**و`downgrade` يحذف العمود** — وثمنُه: تضيع الوسومُ المكتوبة بعده، والنجومُ والتعليقُ كما هي.

Revision ID: 0086
Revises: 0085
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0086"
down_revision = "0085"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ratings",
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String(length=24)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
    )


def downgrade() -> None:
    op.drop_column("ratings", "tags")
