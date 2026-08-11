"""قيمةُ `read` في `audit_action` — لقراءةٍ تُسجَّل

الخريطةُ الحيّة تخرج بهوية كل كبتنٍ مع موقعه، ومن يفتحها يُسأل عنها. ولا
فعلَ في التعداد يصفها: `update` كذبٌ، و`create` أكذب.

**ولا `DROP TYPE` في التراجع**: النوع أنشأته 0003 وهي من تُسقطه، وPostgres لا
يحذف قيمةً من تعداد. و`IF NOT EXISTS` هو ما يجعل ترقيةً بعد تراجعٍ جزئي تمرّ.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'read'")


def downgrade() -> None:
    # لا تُحذف قيمةٌ من تعدادٍ في Postgres؛ والنوع يسقط مع 0003
    pass
