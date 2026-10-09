"""مدّةُ الاحتفاظ بتسجيل المكالمات **تسعون يوماً افتراضاً** لا ثلاثون (أمرُ المالك ٢٠٢٦-١٠-٠٩، SPEC §٧١-ب/٥).

**ما تغيّره**: افتراضُ العمود `service_settings.call_recording_retention_days` وحدَه — لسوقٍ يُنشأ صفُّه بعد اليوم.
**ولا `UPDATE` على صفٍّ قائم**: الأردنُ ضُبط ٩٠ بسكربتٍ مدقَّقٍ بأمر المالك، **وليبيا لا تُمسّ**، والمدّةُ تُعدَّل من اللوحة.

Revision ID: 0105
Revises: 0104
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0105"
down_revision = "0104"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("service_settings", "call_recording_retention_days", server_default=sa.text("90"))


def downgrade() -> None:
    op.alter_column("service_settings", "call_recording_retention_days", server_default=sa.text("30"))
