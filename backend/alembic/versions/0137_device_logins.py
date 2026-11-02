"""الجلسةُ تبقى حتى «تسجيل الخروج»، والبصمةُ تبقى بعده (أمرُ المالك ٢٠٢٦-١١-٠٢، SPEC §60-ج) — **جدولٌ وعمودٌ بلا مال**.

- `auth_sessions.current_seen_at` — أوصل الزوجُ الحاليُّ صاحبَه؟ وما لم يصل فعودةُ الرمز السابق جوابٌ ضاع لا سرقة
  (تطبيقٌ قُتل والتجديدُ في الطريق). **فارغٌ لكلِّ جلسةٍ قائمة** — أي «لم يُرَ بعد»، وهو الاتجاهُ الذي لا يُخرج أحداً.
- `device_logins` — بيانُ جهازٍ يُصرف ببصمةٍ بعد الخروج (`models/device_login.py`). **فارغٌ**: لا أحدَ أشعله بعد.

**والرجوعُ** حذفُهما: من أشعل البصمةَ يدخل بكلمة مروره مرّةً، **ولا جلسةَ تسقط**.

Revision ID: 0137
Revises: 0136
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0137"
down_revision = "0136"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("auth_sessions", sa.Column("current_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "device_logins",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("app", sa.String(length=8), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=32), nullable=True),
    )
    op.create_index("ix_device_logins_user_id", "device_logins", ["user_id"])
    op.create_index(
        "device_logins_live_unique",
        "device_logins",
        ["user_id", "device_id", "app"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("device_logins_live_unique", table_name="device_logins")
    op.drop_index("ix_device_logins_user_id", table_name="device_logins")
    op.drop_table("device_logins")
    op.drop_column("auth_sessions", "current_seen_at")
