"""**أسماءٌ عربيّةٌ يكتبها المشرفُ لأماكن الخريطة** (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-ب) — جدولٌ جديدٌ `map_name_fixes`.

**لا يمسّ جدولَ مال**. **والرجوعُ** يحذف الجدول، فتعود الأماكنُ بأسماء مربّعاتها كما كانت حرفاً.

Revision ID: 0180
Revises: 0179
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0180"
down_revision = "0179"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "map_name_fixes",
        sa.Column("okey", sa.String(length=40), primary_key=True),
        sa.Column("country_code", postgresql.ENUM(name="country_code", create_type=False), nullable=False),
        sa.Column("name_ar", sa.String(length=120), nullable=False),
        sa.Column("original_name", sa.String(length=120), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_map_name_fixes_country_code", "map_name_fixes", ["country_code"])


def downgrade() -> None:
    op.drop_index("ix_map_name_fixes_country_code", table_name="map_name_fixes")
    op.drop_table("map_name_fixes")
