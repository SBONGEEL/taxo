"""قنواتُ أندرويد التي يحملها الجهاز — بها يختار الخادمُ القناة (SPEC §٦١-ل/٣–٥، ٢٠٢٦-١٠-٠٥).

**عمودٌ فارغٌ على `device_tokens`** (`push_channels`): يكتبه التطبيقُ مع رمزه حين يجد قنواتِ المجموعة
الثانية على الجهاز فعلاً، **و`NULL` حزمةٌ أقدمُ يُرسَل إليها كما اليومَ حرفاً** — فلا يتغيّر شيءٌ لجهازٍ لم يبلّغ.
**ولا جدولَ مالٍ هنا، ولا يقرؤه غيرُ الإرسال.**

**و`downgrade` يحذف العمود** — وثمنُه: يعود كلُّ جهازٍ إلى قنوات اليوم حتى يبلّغ ثانية. لا مال ولا صفّ.

Revision ID: 0085
Revises: 0084
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0085"
down_revision = "0084"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("device_tokens", sa.Column("push_channels", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("device_tokens", "push_channels")
