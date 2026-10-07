"""«انتظري، نوسّع البحث» (SPEC §٦٤-ج/٤-٣، §٦٢-ج/٢٨) — علامةٌ على الرحلة: بحثٌ أوسعُ وأطولُ **بين الكبتنات وحدهنّ**.

**عمودٌ بافتراضٍ يصف كلَّ رحلةٍ قائمةٍ حرفاً** (`false`)، **ولا جدولَ مالٍ يُمسّ**. **و`downgrade` مقيسٌ لا مقروء.**

Revision ID: 0098
Revises: 0097
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0098"
down_revision = "0097"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rides", sa.Column("search_widened", sa.Boolean(), server_default=sa.text("false"), nullable=False))


def downgrade() -> None:
    op.drop_column("rides", "search_widened")
