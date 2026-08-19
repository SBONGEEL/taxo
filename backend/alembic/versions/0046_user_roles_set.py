"""أدوارُ الحساب مجموعةً — ونقلُ كلِّ حسابٍ بدوره الحالي حرفياً.

**لا حسابَ يكسب دوراً بالترحيلة ولا يفقده** (شرطُ المالك): صفٌّ واحدٌ لكل حساب،
مأخوذٌ من `users.role` كما هو. والعمودُ **يبقى** — لا يُحذف في هذه المرحلة:
حذفُه يجعل الرجوعَ فقداً، ويجعل كلَّ قراءةٍ لم تُنقل بعدُ عمياء.

Revision ID: 0046
Revises: 0045
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # **النوعُ قائمٌ سلفاً** — `create_type=False` وإلا فشل الترقّي بـ
        # «type already exists»، وهو الفخُّ الذي عالجه `0003`
        sa.Column(
            "role",
            postgresql.ENUM(
                "rider", "driver", "admin", "support",
                name="user_role",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "role", name="uq_user_roles_user_role"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])

    # **النقلُ حرفيٌّ**: صفٌّ لكل حساب بدوره الحالي، لا أكثر ولا أقلّ.
    # و`gen_random_uuid()` من pgcrypto المفعَّلة في هذه القاعدة (تُستعمل في 0045).
    op.execute(
        """
        INSERT INTO user_roles (id, user_id, role, granted_at)
        SELECT gen_random_uuid(), id, role, now() FROM users
        """
    )


def downgrade() -> None:
    # **الرجوعُ بلا فقد**: `users.role` لم يُمسّ، فالحالةُ السابقةُ قائمةٌ كما هي
    # ولا شيءَ يُعاد بناؤه. وإسقاطُ الجدول يُسقط ما زاد عن الدور الأساسي — وهو
    # ما لا وجودَ له عند هذه الترحيلة بحكم النقل الحرفيّ.
    op.drop_index("ix_user_roles_user_id", table_name="user_roles")
    op.drop_table("user_roles")
