"""النصُّ الفرنسيُّ للوثيقة (SPEC §٧٤-ل/١) — **عمودٌ واحدٌ على `privacy_policies`**: الجزائرُ تتبع لغةَ الهاتف بالفرنسيّة، فوثيقتُها
تُقرأ بالعربيّة والفرنسيّة. **وفارغٌ لما سواها** — والأردنُ كما كان.

Revision ID: 0124
Revises: 0123
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0124"
down_revision = "0123"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("privacy_policies", sa.Column("body_fr", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("privacy_policies", "body_fr")
