"""وسمُ الارتداد — محسومةٌ عادت تقع.

**ولمَ عمودٌ لا حسابٌ عند القراءة**: «أحُسمت يوماً ثمّ عادت؟» لا يُستنتج من
الحال الراهنة — فالحالُ تعود `open` فيبدو العطبُ كأنه لم يُحسم قطّ، **ويضيع
أنّ أحداً أقرّ بإصلاحه وأخطأ**. وهو الخبرُ الذي يستحقّ أن يُرى أوّلاً.

Revision ID: 0080
Revises: 0079
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0080"
down_revision = "0079"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "error_groups",
        sa.Column("regressed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_error_groups_regressed_at", "error_groups", ["regressed_at"]
    )
    # **المتَّهَم**: أعلى إطارٍ في الأثر — يُقرأ في القائمة بلا فتح كلِّ صفّ
    op.add_column(
        "error_groups", sa.Column("culprit", sa.String(length=200), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("error_groups", "culprit")
    op.drop_index("ix_error_groups_regressed_at", table_name="error_groups")
    op.drop_column("error_groups", "regressed_at")
