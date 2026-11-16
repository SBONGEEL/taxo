"""open map min build: أدنى غلافٍ تُرسم فيه الخريطةُ المفتوحة (قرارُ المالك ٢٠٢٦-١١-١٦، SPEC §١٠٥/٥)

Revision ID: 0168
Revises: 0167
Create Date: 2026-11-16

**عمودٌ فارغٌ في `app_releases`** — لا جدولَ مالٍ ولا قيمة: فارغاً لا يُرسم MapLibre في أيِّ غلافٍ ولو اشتعل
`open_map_display`، فالرفعُ لا يغيّر ما يراه أحد. **والنزولُ ينزع العمودَ وقيدَه** (لا مالَ فيه).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0168"
down_revision = "0167"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_releases", sa.Column("open_map_min_build", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_app_releases_open_map_positive",
        "app_releases",
        "open_map_min_build IS NULL OR open_map_min_build > 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_app_releases_open_map_positive", "app_releases", type_="check")
    op.drop_column("app_releases", "open_map_min_build")
