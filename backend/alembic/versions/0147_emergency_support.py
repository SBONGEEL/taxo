"""زرُّ الطوارئ وأرقامُ التواصل لكلِّ دولة (أمرُ المالك ٢٠٢٦-١١-١٠، البندان ٧ و٨).

* `support_settings` — رقمُ طوارئ الدولة وواتسابُ الدعم.
* `emergency_alerts` — كلُّ ضغطةٍ على زرّ الطوارئ، مفتوحةً حتى يعالجها مشرف.

**لا جدولَ مالٍ يُمسّ.** والرجوعُ يحذف الجدولين.

Revision ID: 0147
Revises: 0146
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0147"
down_revision = "0146"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "support_settings",
        sa.Column("country_code", postgresql.ENUM(name="country_code", create_type=False), nullable=False),
        sa.Column("emergency_number", sa.String(length=20), nullable=True),
        sa.Column("whatsapp_number", sa.String(length=20), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_support_settings_updated_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("country_code", name=op.f("pk_support_settings")),
    )
    op.create_table(
        "emergency_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=8), nullable=False),
        sa.Column("ride_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("country_code", postgresql.ENUM(name="country_code", create_type=False), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=8), server_default="open", nullable=False),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handled_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('rider', 'driver')", name=op.f("ck_emergency_alerts_emergency_alerts_role")),
        sa.CheckConstraint("status IN ('open', 'handled')", name=op.f("ck_emergency_alerts_emergency_alerts_status")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_emergency_alerts_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ride_id"], ["rides.id"], name=op.f("fk_emergency_alerts_ride_id_rides"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["handled_by"], ["users.id"], name=op.f("fk_emergency_alerts_handled_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_emergency_alerts")),
    )
    op.create_index(op.f("ix_emergency_alerts_user_id"), "emergency_alerts", ["user_id"])
    op.create_index(op.f("ix_emergency_alerts_ride_id"), "emergency_alerts", ["ride_id"])
    op.create_index(op.f("ix_emergency_alerts_status"), "emergency_alerts", ["status"])


def downgrade() -> None:
    op.drop_table("emergency_alerts")
    op.drop_table("support_settings")
