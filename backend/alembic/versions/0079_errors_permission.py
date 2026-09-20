"""errors.read: صلاحيةُ شاشة الأعطال — عضوٌ ثانيَ عشرَ في المصفوفة

Revision ID: 0079
Revises: 0078
Create Date: 2026-09-20

**عضوٌ يُضاف إلى نوعٍ قائم** (`admin_permission`)، لا جدولَ ولا عمود.

## والنزولُ يُعيد بناءَ النوع — ولا سبيلَ غيرُه

**PostgreSQL لا تحذف عضواً من `ENUM`.** فالنزولُ يبني نوعاً جديداً بالأحدَ
عشرَ، ويحوّل العمودَ إليه، ويُسقط القديم، ويعيد الاسم. **وهذا مقيسٌ لا مقروء**:
جُرِّب صعوداً ونزولاً وصعوداً قبل الإيداع.

**والصفوفُ الحاملةُ للعضو المحذوف تُحذف أولاً**: تحويلُ عمودٍ فيه قيمةٌ لا
يعرفها النوعُ الجديد يسقط بنصٍّ غامض. **وحذفُ منحةِ صلاحيةٍ ليس حذفَ مال**
— ولا صفَّ منها اليومَ أصلاً، والمصفوفةُ فارغةٌ بقرارها المعلَن («الغيابُ
يعني: اقرأ افتراضَ دوره»).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0079"
down_revision = "0078"
branch_labels = None
depends_on = None

_ELEVEN = (
    "settings.write",
    "users.manage",
    "finance.manage",
    "growth.manage",
    "fleet.manage",
    "providers.manage",
    "backups.manage",
    "payments.resolve",
    "read.only",
    "security.manage",
    "permissions.manage",
)


def upgrade() -> None:
    # `IF NOT EXISTS` كي تُعاد على قاعدةٍ نصفِ مهاجَرةٍ بلا سقوط
    op.execute("ALTER TYPE admin_permission ADD VALUE IF NOT EXISTS 'errors.read'")


def downgrade() -> None:
    op.execute("DELETE FROM admin_permissions WHERE permission = 'errors.read'")

    values = ", ".join(f"'{value}'" for value in _ELEVEN)
    op.execute(sa.text(f"CREATE TYPE admin_permission_old AS ENUM ({values})"))
    op.execute(
        "ALTER TABLE admin_permissions "
        "ALTER COLUMN permission TYPE admin_permission_old "
        "USING permission::text::admin_permission_old"
    )
    op.execute("DROP TYPE admin_permission")
    op.execute("ALTER TYPE admin_permission_old RENAME TO admin_permission")
