"""إعداداتُ بثّ موقع الكبتن وسجلُّ تغييراتها (SPEC §٧٥-ج) — `broadcast_settings` (صفٌّ واحدٌ يُبذر بقيم المالك) و`broadcast_changes`.

**يُبذر الصفُّ** بقيم أمر المالك ٢٠٢٦-١٠-١٣: الطورُ آليّ · المتاحُ ١٥ · في الطريق ١٠ · الرحلةُ ١٥ بنقاط ٢ · السكونُ ٣٠ م · النبضةُ ٦٠ ·
والجدول: حتى ١٠٠٠ ⇒ ١٥ · حتى ٢٠٠٠ ⇒ ٢٠ · حتى ٣٠٠٠ ⇒ ٣٠ · فوقها ⇒ ٤٥. **ولا مالَ هنا** — فبوّابةُ المال لا تعنيها.

**و`downgrade` يحذف الجدولين** — لا قرارَ مالٍ فيهما، والسجلُّ سجلُّ تشغيل.

Revision ID: 0125
Revises: 0124
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0125"
down_revision = "0124"
branch_labels = None
depends_on = None

STEPS = (
    '[{"max_online": 1000, "seconds": 15}, {"max_online": 2000, "seconds": 20}, '
    '{"max_online": 3000, "seconds": 30}, {"max_online": null, "seconds": 45}]'
)


def upgrade() -> None:
    op.create_table(
        "broadcast_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("singleton", sa.Boolean(), nullable=False, server_default=sa.text("true"), unique=True),
        sa.Column("mode", sa.String(16), nullable=False, server_default="automatic"),
        sa.Column("available_seconds", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("heading_seconds", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("trip_send_seconds", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("trip_record_seconds", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("move_meters", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("heartbeat_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("auto_steps", postgresql.JSONB(), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("singleton IS TRUE", name="broadcast_settings_singleton"),
        sa.CheckConstraint("mode IN ('manual', 'automatic')", name="broadcast_settings_mode"),
        sa.CheckConstraint("available_seconds BETWEEN 15 AND 45", name="broadcast_available_range"),
        sa.CheckConstraint("heading_seconds BETWEEN 3 AND 60", name="broadcast_heading_range"),
        sa.CheckConstraint("trip_send_seconds BETWEEN 3 AND 60", name="broadcast_trip_send_range"),
        sa.CheckConstraint("trip_record_seconds BETWEEN 1 AND 10", name="broadcast_trip_record_range"),
        sa.CheckConstraint("move_meters BETWEEN 5 AND 500", name="broadcast_move_range"),
        sa.CheckConstraint("heartbeat_seconds BETWEEN 15 AND 120", name="broadcast_heartbeat_range"),
    )
    op.create_table(
        "broadcast_changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("online_count", sa.Integer(), nullable=False),
        sa.Column("old_seconds", sa.Integer(), nullable=True),
        sa.Column("new_seconds", sa.Integer(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint("source IN ('automatic', 'admin')", name="broadcast_changes_source"),
    )
    op.create_index(op.f("ix_broadcast_changes_created_at"), "broadcast_changes", ["created_at"])
    op.execute(
        "INSERT INTO broadcast_settings (id, auto_steps) VALUES (gen_random_uuid(), '" + STEPS + "'::jsonb)"
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_broadcast_changes_created_at"), table_name="broadcast_changes")
    op.drop_table("broadcast_changes")
    op.drop_table("broadcast_settings")
