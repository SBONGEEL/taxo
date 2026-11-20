"""**صورةُ الكبتن الجديدةُ تنتظر المراجعة والقديمةُ باقيةٌ للركّاب** (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-هـ/٢).

عمودٌ واحدٌ على `driver_documents`: `live_file_path` — **مسارُ الصورة المعتمَدة السابقة** ما دامت الجديدةُ تنتظر مشرفاً. يُملأ حين
يستبدل الكبتنُ صورةً شخصيّةً معتمَدة، ويُفرَّغ (ويُحذف ملفُّه) حين تُعتمد الجديدة؛ والرفضُ يُبقيه. **لا يمسّ جدولَ مال**.

**والرجوعُ** يحذف العمود؛ ومن كان ينتظر صورتَه الجديدةَ يرى الركّابُ حرفَ اسمه حتى تُراجَع — سلوكُ ما قبل هذه الترحيلة حرفاً.

Revision ID: 0179
Revises: 0178
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0179"
down_revision = "0178"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("driver_documents", sa.Column("live_file_path", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("driver_documents", "live_file_path")
