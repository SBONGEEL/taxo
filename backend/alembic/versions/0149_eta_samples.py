"""عيّناتُ دقّة وقت الوصول (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٢).

جدولٌ جديدٌ `eta_samples`: المتوقَّعُ (خامّاً ومعروضاً) والفعليُّ لكلِّ اقتراب، **وبه يُصحَّح الوقتُ بالساعة واليوم وتُقاس دقّتُه في
اللوحة**. **لا جدولَ مالٍ يُمسّ.** والرجوعُ يحذف الجدول.

Revision ID: 0149
Revises: 0148
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0149"
down_revision = "0148"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eta_samples",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ride_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", postgresql.ENUM(name="country_code", create_type=False), nullable=False),
        sa.Column("raw_seconds", sa.Integer(), nullable=False),
        sa.Column("shown_seconds", sa.Integer(), nullable=False),
        sa.Column("actual_seconds", sa.Integer(), nullable=False),
        sa.Column("local_hour", sa.SmallInteger(), nullable=False),
        sa.Column("local_dow", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ride_id"], ["rides.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ride_id", name="eta_samples_ride"),
    )


def downgrade() -> None:
    op.drop_table("eta_samples")
