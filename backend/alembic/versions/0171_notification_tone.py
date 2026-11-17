"""notification tone: «نغمة الإشعارات» لكلِّ مستخدم (أمرُ المالك ٢٠٢٦-١١-١٧، `design/OWNER-2026-11-17-THIRD.md` ج/١)

Revision ID: 0171
Revises: 0170
Create Date: 2026-11-17

**عمودٌ فارغٌ في `users`** — لا جدولَ مالٍ ولا قيمة: `NULL` هو **الصوتُ الافتراضيُّ الحاليّ** فلا يتغيّر شيءٌ لأحدٍ حتى يختار
بنفسه، ولا يُقرأ أصلاً ما دام مفتاحُ `notification_tones_enabled` مطفأً في سوقه. **والنزولُ ينزعه** (لا مالَ فيه).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0171"
down_revision = "0170"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("notification_tone", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "notification_tone")
