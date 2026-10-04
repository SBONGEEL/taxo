"""فحصُ المركبة — موعدٌ يضعه المشرفُ ويراه الكبتن (SPEC §61-ط/٥، ٢٠٢٦-١٠-٠٤).

**ثلاثةُ أعمدةٍ فارغةٍ على `drivers`**: موعدُ الفحص · مكانُه · وقتُ اجتيازه. **ولا جدولَ مالٍ بينها، ولا صفَّ يُكتب** —
كلُّ كبتنٍ يبدأ بلا موعد. **ولا يشترطها الاعتماد**: `drivers.approve` لا يقرؤها، فمسارُ الاعتماد كما هو.

**و`downgrade` يحذف الأعمدةَ الثلاثة، وثمنُه مكتوب**: ما وضعه المشرفون من مواعيدَ يضيع — ولا مالَ فيه.

Revision ID: 0083
Revises: 0082
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0083"
down_revision = "0082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("drivers", sa.Column("inspection_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("drivers", sa.Column("inspection_place", sa.String(length=160), nullable=True))
    op.add_column("drivers", sa.Column("inspection_passed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("drivers", "inspection_passed_at")
    op.drop_column("drivers", "inspection_place")
    op.drop_column("drivers", "inspection_at")
