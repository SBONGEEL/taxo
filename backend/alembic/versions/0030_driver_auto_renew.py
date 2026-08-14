"""مفتاحُ التجديد التلقائي على الكبتن (البند ١٤)

Revision ID: 0030
Revises: 0029
Create Date: 2026-08-14 15:51:21.927208
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0030'
down_revision: str | None = '0029'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # **مطفأٌ افتراضاً وبـ`server_default`**: الصفوفُ القائمة لا تُفتح على مالٍ
    # يخرج بلا ضغطةٍ من صاحبه — الإذنُ صريحٌ أو لا يكون
    op.add_column('drivers', sa.Column('auto_renew', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade() -> None:
    # **مطفأٌ افتراضاً وبـ`server_default`**: الصفوفُ القائمة لا تُفتح على مالٍ
    # يخرج بلا ضغطةٍ من صاحبه — الإذنُ صريحٌ أو لا يكون
    op.drop_column('drivers', 'auto_renew')
