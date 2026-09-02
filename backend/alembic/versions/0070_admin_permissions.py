"""مصفوفةُ صلاحيات المشرفين — **جدولٌ فارغٌ يومَ يُنشأ** (البند ٥، §39٫٥).

**ولا صفَّ يُبذر بقصد** (شرطُ المالك): «الافتراضُ أن `support` يقرأ ويحسم
النزاعات لا أكثر — **لأنه ما يقع اليوم حرفاً**، فالمصفوفةُ لا تبدّل سلوكاً
قائماً في يومها الأول».

**والغيابُ يُقرأ «افتراضُ الدور»** لا «ممنوع» — فجدولٌ فارغٌ يعني أن كلَّ
مشرفٍ يبقى على ما هو عليه اليوم بالضبط. **وبذرُ صفوفٍ للجميع كان سيجعل أوّلَ
نزعٍ خاطئٍ يُقفل باباً لم يكن مقفلاً.**

Revision ID: 0070
Revises: 0069
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None

PERMISSION = postgresql.ENUM(
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
    name="admin_permission",
    create_type=False,
)


def upgrade() -> None:
    PERMISSION.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "admin_permissions",
        # **بلا `server_default`**: `default=uuid.uuid4` في بايثون، وافتراضٌ
        # في القاعدة بلا مقابلٍ في النموذج يُقرأ انحرافاً
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("permission", PERMISSION, nullable=False),
        sa.Column(
            "granted_by",
            postgresql.UUID(as_uuid=True),
            # **`SET NULL` لا `CASCADE`**: حسابُ مانحٍ يُحذف لا يمحو المنحة
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "user_id", "permission", name="uq_admin_permissions_user_permission"
        ),
    )
    op.create_index(
        "ix_admin_permissions_user_id", "admin_permissions", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_admin_permissions_user_id", table_name="admin_permissions")
    op.drop_table("admin_permissions")
    PERMISSION.drop(op.get_bind(), checkfirst=True)
