"""مُنتقي الدول (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٥): حالُ «متوقفة»، وحالُ الدول غيرِ الأسواق، وعدُّ المحاولات اليوميّ.

**لا جدولَ مالٍ يُمسّ، ولا رقمَ هاتفٍ يُخزَّن، ولا صفَّ بياناتٍ يُكتب** — حالُ ليبيا «قريباً» تُضبط من اللوحة بسطر تدقيق.
**والرجوعُ يحذف الجدولين**؛ وقيمةُ التعداد
تبقى (Postgres لا ينزع قيمةً من تعداد)، **وأيُّ صفٍّ يحملها في `country_markets` يُعاد «قريباً» قبل الحذف**.

Revision ID: 0145
Revises: 0144
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0145"
down_revision = "0144"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE signup_display ADD VALUE IF NOT EXISTS 'stopped'")
    op.create_table(
        "signup_countries",
        sa.Column("code", sa.String(2), primary_key=True),
        sa.Column(
            "display",
            postgresql.ENUM(name="signup_display", create_type=False),
            nullable=False,
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_signup_countries_updated_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_signup_countries")),
    )
    op.create_table(
        "signup_attempts_daily",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("day", "country", name=op.f("pk_signup_attempts_daily")),
    )


def downgrade() -> None:
    op.execute("UPDATE country_markets SET signup_display = 'soon' WHERE signup_display::text = 'stopped'")
    op.drop_table("signup_attempts_daily")
    op.drop_table("signup_countries")
