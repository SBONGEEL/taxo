"""تفصيلُ الأجرة مجمَّداً على الرحلة (`rides.fare_lines`) — R10 «الأجرة النهائية» وأسطرُها (SPEC §٦٢-ج/٢٥).

**عمودٌ فارغٌ يُضاف ولا يُملأ لما سبق**: الرحلاتُ القديمة لا تفصيلَ لها (`NULL`) فلا يُرسم لها شيء — **ولا يُعاد بناؤه من
التسعيرة الحالية** لأن معدّلاتها قد تغيّرت منذ جُمّد السعر. **ولا يغيّر مبلغاً**: `estimated_fare` و`final_fare` يُحسبان كما كانا
حرفاً، والأسطرُ تُكتب من الحساب نفسِه.

**وجدولُ `rides` جدولُ مال** — فالترحيلةُ تُعرض على المالك قبل أيِّ رفع (قاعدةُ `CLAUDE.md` الثانية)، **ولا رفعَ في هذا الفرع**.
**وأقرّها المالك** ٢٠٢٦-١٠-٠٦ (SPEC §٦٢-د/٦) — والرفعُ إلى الإنتاج بقوله وحده كسائر الفرع.
**و`downgrade` يحذف العمود** — وثمنُه: يختفي التفصيلُ من الشاشة؛ لا مبلغَ يتغيّر.

Revision ID: 0087
Revises: 0086
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0087"
down_revision = "0086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rides", sa.Column("fare_lines", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("rides", "fare_lines")
