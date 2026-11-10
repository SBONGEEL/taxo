"""درجةُ جودة الكبتن (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٣).

جدولان جديدان: `quality_settings` (الأوزانُ والمفتاحُ لكلِّ دولة، **مطفأٌ افتراضاً**) و`driver_quality_scores` (الدرجةُ اليوميّة
ومكوّناتُها). **لا جدولَ مالٍ يُمسّ.** والرجوعُ يحذف الجدولين.

Revision ID: 0151
Revises: 0150
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0151"
down_revision = "0150"
branch_labels = None
depends_on = None


def _stamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "quality_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", postgresql.ENUM(name="country_code", create_type=False), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("w_acceptance", sa.SmallInteger(), server_default=sa.text("30"), nullable=False),
        sa.Column("w_cancellation", sa.SmallInteger(), server_default=sa.text("25"), nullable=False),
        sa.Column("w_rating", sa.SmallInteger(), server_default=sa.text("25"), nullable=False),
        sa.Column("w_complaints", sa.SmallInteger(), server_default=sa.text("10"), nullable=False),
        sa.Column("w_completed", sa.SmallInteger(), server_default=sa.text("10"), nullable=False),
        sa.Column("dispatch_bonus_m", sa.Integer(), server_default=sa.text("150"), nullable=False),
        sa.Column("warn_below", sa.SmallInteger(), server_default=sa.text("50"), nullable=False),
        *_stamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("country_code", name="quality_settings_country"),
        sa.CheckConstraint(
            "w_acceptance >= 0 AND w_cancellation >= 0 AND w_rating >= 0 AND w_complaints >= 0 AND w_completed >= 0"
            " AND w_acceptance + w_cancellation + w_rating + w_complaints + w_completed > 0",
            name="quality_weights_valid",
        ),
        sa.CheckConstraint("dispatch_bonus_m BETWEEN 0 AND 1000", name="quality_bonus_range"),
        sa.CheckConstraint("warn_below BETWEEN 0 AND 100", name="quality_warn_range"),
    )
    op.create_table(
        "driver_quality_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("components", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_stamps(),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("driver_id", "day", name="driver_quality_scores_day"),
        sa.CheckConstraint("score BETWEEN 0 AND 100", name="driver_quality_score_range"),
    )
    op.create_index("ix_driver_quality_scores_driver_id", "driver_quality_scores", ["driver_id"])


def downgrade() -> None:
    op.drop_index("ix_driver_quality_scores_driver_id", table_name="driver_quality_scores")
    op.drop_table("driver_quality_scores")
    op.drop_table("quality_settings")
