"""وضعُ الضيف (SPEC §٧٦-ن/أ، أمرُ المالك ٢٠٢٦-١٠-١٥).

جدولان جديدان — `guest_sessions` (جلسةُ عرضٍ موسومةٌ لا حساب) و`guest_mode_settings` (مفتاحٌ لكلِّ تطبيق، **مطفأٌ افتراضاً**) —
و`app_feedback` يقبل ملاحظةَ ضيفٍ: `user_id` يصير اختياريّاً **وقيدٌ يشترط واحداً من الاثنين بالضبط**. **ولا مالَ هنا**: الضيفُ لا
رحلةَ له ولا قيدَ ولا محفظة.

**و`downgrade` يقف ما دامت ملاحظةُ ضيفٍ قائمة** — إعادةُ `user_id` إلزاميّاً فوق صفٍّ بلا حسابٍ تسقط في منتصفها.

Revision ID: 0129
Revises: 0128
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0129"
down_revision = "0128"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guest_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("app", sa.String(8), nullable=False),
        sa.Column("device_hash", sa.String(64), nullable=False),
        sa.Column("ip_hash", sa.String(64), nullable=False),
        sa.Column("language", sa.String(8), nullable=True),
        sa.Column("network_region", sa.String(2), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("app IN ('rider', 'driver')", name="guest_sessions_app"),
    )
    op.create_index("ix_guest_sessions_device_hash", "guest_sessions", ["device_hash"])
    op.create_table(
        "guest_mode_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("singleton", sa.Boolean(), nullable=False, server_default=sa.text("true"), unique=True),
        sa.Column("rider_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("driver_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("singleton IS TRUE", name="guest_mode_settings_singleton"),
    )
    op.alter_column("app_feedback", "user_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.add_column(
        "app_feedback",
        sa.Column(
            "guest_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("guest_sessions.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_app_feedback_guest_session_id", "app_feedback", ["guest_session_id"])
    op.create_check_constraint("app_feedback_sender", "app_feedback", "num_nonnulls(user_id, guest_session_id) = 1")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM app_feedback WHERE guest_session_id IS NOT NULL) THEN
                RAISE EXCEPTION 'guest feedback exists — downgrade of 0129 refuses to drop it';
            END IF;
        END
        $$
        """
    )
    op.drop_constraint("app_feedback_sender", "app_feedback", type_="check")
    op.drop_index("ix_app_feedback_guest_session_id", table_name="app_feedback")
    op.drop_column("app_feedback", "guest_session_id")
    op.alter_column("app_feedback", "user_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.drop_table("guest_mode_settings")
    op.drop_index("ix_guest_sessions_device_hash", table_name="guest_sessions")
    op.drop_table("guest_sessions")
