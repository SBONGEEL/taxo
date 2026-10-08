"""صلاحيةُ الملخّصات المالية (SPEC §٦٥-د/٧) — **قيمةٌ واحدةٌ في `admin_permission`، ولا جدولَ ولا عمود**.

**ما تضيفه**: `finance.summary` — **ولا تُعطى لأحدٍ افتراضاً، ولا للمشرف الكامل** (`services/permissions.SENSITIVE`)، فلا صفَّ
يُكتب هنا: الصلاحيةُ تُمنح بالاسم من مصفوفة اللوحة، ومنحُها مدقَّقٌ كأيِّ منح.

**ولا مالَ ولا صفَّ قائماً يُمسّ**: الصفحةُ قراءةٌ وحدَها، وما تقرؤه جداولُ قائمةٌ كما هي.

**و`downgrade` مقيسٌ لا مقروء** (`tests/test_migrations.py::test_0103_downgrade_does_not_widen_an_admin`): يعيد بناءَ النوع بلا
القيمة كما فعلت `0102` و`0079` — PostgreSQL لا تحذف عضواً من نوع — **ولا يوسّع أحداً**: من كانت صلاحيتُه هذه وحدَها يُكتب له
`read.only` قبل الحذف، فلا يصير بالنزول «بلا صفوف» فيُقرأ افتراضَ دوره — **وافتراضُ `admin` قبلها كلُّ ما ليس حسّاساً**.

**ورقمُها `0103` فوق `0102`** (المحادثةُ والمكالمة، مدموجةٌ قبلها).

Revision ID: 0103
Revises: 0102
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0103"
down_revision = "0102"
branch_labels = None
depends_on = None

#: **العضوُ الجديدُ وحدَه باسمه** — وأعضاءُ النوع قبله تُقرأ من القاعدة في النزول لا تُنسخ هنا
_NEW_PERMISSION = "finance.summary"


def upgrade() -> None:
    # `IF NOT EXISTS` كي تُعاد على قاعدةٍ نصفِ مهاجَرةٍ بلا سقوط
    op.execute(f"ALTER TYPE admin_permission ADD VALUE IF NOT EXISTS '{_NEW_PERMISSION}'")


def downgrade() -> None:
    bind = op.get_bind()
    # **والنزولُ لا يوسّع أحداً** — قاعدةُ `0102` حرفاً: مشرفٌ كلُّ صفوفه هذه الصلاحيةُ يُكتب له `read.only` (أضيقُ ما في
    # التعداد القديم، **وصفٌّ يحكم** فلا يُقرأ افتراضُه). ومن له صفٌّ آخرُ معها لا يُمسّ: صفوفُه الباقيةُ تحكم كما كانت
    op.execute(
        "INSERT INTO admin_permissions (id, user_id, permission, granted_at) "
        "SELECT gen_random_uuid(), user_id, 'read.only'::admin_permission, now() FROM admin_permissions "
        f"GROUP BY user_id HAVING bool_and(permission::text = '{_NEW_PERMISSION}')"
    )
    op.execute(f"DELETE FROM admin_permissions WHERE permission::text = '{_NEW_PERMISSION}'")
    members = bind.execute(sa.text("SELECT unnest(enum_range(NULL::admin_permission))::text")).scalars().all()
    values = ", ".join(f"'{value}'" for value in members if value != _NEW_PERMISSION)
    op.execute(sa.text(f"CREATE TYPE admin_permission_old AS ENUM ({values})"))
    op.execute(
        "ALTER TABLE admin_permissions "
        "ALTER COLUMN permission TYPE admin_permission_old "
        "USING permission::text::admin_permission_old"
    )
    op.execute("DROP TYPE admin_permission")
    op.execute("ALTER TYPE admin_permission_old RENAME TO admin_permission")
