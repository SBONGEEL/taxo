"""«الإحصاءات» (أمرُ المالك ٢٠٢٦-١١-٠٤، `design/SITE-STATS.md`): أربعةُ جداولِ مجاميع وصلاحيّةُ `stats.view` وعقدُ `google_play_reports`.

**مجاميعُ يوميّةٌ وحدَها — لا عمودَ لمستخدمٍ ولا جهازٍ ولا عنوان، ولا جدولَ مالٍ يُمسّ.** والرجوعُ يحذف الجداولَ الأربعة؛ وقيمةُ التعداد
تبقى (Postgres لا ينزع قيمةً من تعداد)، وهي بلا أثرٍ حين لا يحملها أحد.

Revision ID: 0144
Revises: 0143
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0144"
down_revision = "0143"
branch_labels = None
depends_on = None


def _count(name: str) -> sa.Column:
    return sa.Column(name, sa.Integer(), nullable=False, server_default=sa.text("0"))


def upgrade() -> None:
    op.execute("ALTER TYPE admin_permission ADD VALUE IF NOT EXISTS 'stats.view'")
    op.execute("ALTER TYPE provider_key ADD VALUE IF NOT EXISTS 'google_play_reports'")
    op.create_table(
        "site_daily",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("path", sa.String(64), nullable=False),
        sa.Column("source", sa.String(12), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        _count("views"), _count("uniques_day"), _count("uniques_week"), _count("uniques_month"),
        sa.PrimaryKeyConstraint("day", "path", "source", "country", name=op.f("pk_site_daily")),
        sa.CheckConstraint("source IN ('facebook', 'google', 'direct', 'other')", name="ck_site_daily_source"),
    )
    op.create_table(
        "site_downloads_daily",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("app", sa.String(8), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        _count("downloads"), _count("clicks"),
        sa.PrimaryKeyConstraint("day", "app", "country", name=op.f("pk_site_downloads_daily")),
        sa.CheckConstraint("app IN ('rider', 'driver')", name="ck_site_downloads_daily_app"),
    )
    op.create_table(
        "play_stats_daily",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("package", sa.String(64), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        _count("installs"), _count("uninstalls"), _count("active_devices"),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("day", "package", "country", name=op.f("pk_play_stats_daily")),
    )
    op.create_table(
        "stats_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("ran_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        _count("rows"),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('ok', 'failed')", name="ck_stats_imports_status"),
    )
    op.create_index("ix_stats_imports_ran_at", "stats_imports", ["ran_at"])


def downgrade() -> None:
    op.drop_index("ix_stats_imports_ran_at", table_name="stats_imports")
    op.drop_table("stats_imports")
    op.drop_table("play_stats_daily")
    op.drop_table("site_downloads_daily")
    op.drop_table("site_daily")
