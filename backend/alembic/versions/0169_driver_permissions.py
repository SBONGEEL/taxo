"""driver permissions: الأذوناتُ الأساسيّةُ المطفأةُ على هاتف الكبتن (أمرُ المالك ٢٠٢٦-١١-١٦، SPEC §١٠٣ المرحلة A/28)

Revision ID: 0169
Revises: 0168
Create Date: 2026-11-17

**عمودان فارغان في `drivers`** — لا جدولَ مالٍ ولا قيمة: يملؤهما مركزُ الأذونات في غلافٍ جديدٍ حين يشتعل `permissions_center`،
ويقرؤهما المشرفُ في درج الكبتن. **والنزولُ ينزعهما** (لا مالَ فيهما).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0169"
down_revision = "0168"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("drivers", sa.Column("permissions_off", postgresql.JSONB(), nullable=True))
    op.add_column("drivers", sa.Column("permissions_reported_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("drivers", "permissions_reported_at")
    op.drop_column("drivers", "permissions_off")
