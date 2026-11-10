"""التذاكرُ ورسائلُها — «محادثة مع الدعم» و«نسيت شيئاً» و«شكوى على الرحلة» (أمرُ المالك ٢٠٢٦-١١-١٠، البندان ٨ و٩).

جدولان جديدان. **لا جدولَ مالٍ يُمسّ.** والرجوعُ يحذفهما.

Revision ID: 0152
Revises: 0151
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0152"
down_revision = "0151"
branch_labels = None
depends_on = None


def _stamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "support_tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", postgresql.ENUM(name="country_code", create_type=False), nullable=False),
        sa.Column("app", sa.String(length=8), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("ride_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("against_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("category", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'open'"), nullable=False),
        sa.Column("needs_staff", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("handled_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("photo_path", sa.String(length=255), nullable=True),
        sa.Column("photo_type", sa.String(length=64), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        *_stamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ride_id"], ["rides.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["against_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["handled_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("kind IN ('support', 'lost_item', 'complaint')", name="support_ticket_kind_values"),
        sa.CheckConstraint("status IN ('open', 'in_review', 'resolved', 'rejected')", name="support_ticket_status_values"),
        sa.CheckConstraint("app IN ('rider', 'driver')", name="support_ticket_app_values"),
        sa.CheckConstraint(
            "category IS NULL OR category IN ('behavior', 'vehicle', 'route', 'fare', 'safety', 'other')",
            name="support_ticket_category_values",
        ),
        sa.CheckConstraint("kind = 'support' OR ride_id IS NOT NULL", name="support_ticket_ride_required"),
    )
    op.create_index("ix_support_tickets_user_id", "support_tickets", ["user_id"])
    op.create_index("ix_support_tickets_ride_id", "support_tickets", ["ride_id"])
    op.create_index("ix_support_tickets_against_user_id", "support_tickets", ["against_user_id"])
    op.create_index("ix_support_tickets_status_last", "support_tickets", ["status", "last_message_at"])
    op.create_index(
        "support_tickets_one_active",
        "support_tickets",
        ["user_id", "ride_id", "kind"],
        unique=True,
        postgresql_where=sa.text("status IN ('open', 'in_review') AND ride_id IS NOT NULL"),
    )
    op.create_table(
        "support_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("author_role", sa.String(length=8), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        *_stamps(),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("author_role IN ('user', 'party', 'staff')", name="support_message_role_values"),
    )
    op.create_index("ix_support_messages_ticket_id", "support_messages", ["ticket_id"])


def downgrade() -> None:
    op.drop_index("ix_support_messages_ticket_id", table_name="support_messages")
    op.drop_table("support_messages")
    op.drop_index("support_tickets_one_active", table_name="support_tickets")
    op.drop_index("ix_support_tickets_status_last", table_name="support_tickets")
    op.drop_index("ix_support_tickets_against_user_id", table_name="support_tickets")
    op.drop_index("ix_support_tickets_ride_id", table_name="support_tickets")
    op.drop_index("ix_support_tickets_user_id", table_name="support_tickets")
    op.drop_table("support_tickets")
