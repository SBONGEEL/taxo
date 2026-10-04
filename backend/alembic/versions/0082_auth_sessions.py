"""جلساتُ الدخول — صفٌّ في القاعدة لا مفتاحٌ في Redis (SPEC §60، قرارُ المالك ٢٠٢٦-١٠-٠٤).

**الدخولُ يبقى حتى يخرج صاحبُه**: رمزُ التجديد بلا عمر، وصلاحيتُه صفٌّ حيٌّ هنا
ورمزٌ يطابقه. **وجدولٌ جديدٌ لا يمسّ جدولاً قائماً — ولا جدولَ مالٍ بينها.**

**ولا بياناتَ تُرحَّل**: الجلساتُ القائمةُ يومَ الرفع مفاتيحُ في Redis، **ورمزُها
يصير صفّاً عند أوّل تجديد** (`token_service._adopt_legacy`) — فالتحويلُ لا يُخرج
أحداً، ولا يُكتب في هذه الترحيلة صفٌّ واحد.

**و`downgrade` يحذف الجدول، وثمنُه مكتوبٌ لا مسكوتٌ عنه**: من دخل بعد الرفع يحمل
رمزاً بـ`sid` لا مفتاحَ له في Redis، فيُعاد دخولُه **مرّةً** بعد الرجوع.

Revision ID: 0082
Revises: 0081
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0082"
down_revision = "0081"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_jti", sa.String(length=64), nullable=False),
        sa.Column("current_issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_jti", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=32), nullable=True),
        # **كرموز الأجهزة**: بيانُ دخولٍ لا سجلٌّ محاسبيّ، ولا معنى له بعد صاحبه
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
    )
    # «كلُّ جلسات هذا الحساب» — إنهاءُ الكلّ وتغييرُ كلمة المرور يسألانه
    op.create_index(
        op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_table("auth_sessions")
