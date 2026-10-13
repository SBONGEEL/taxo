"""رسومُ الوسيط على كلِّ طلبٍ عنده (SPEC §٧٤-ك/١) — **عمودان على `payment_requests`**: من حملها (`fee_payer`: «taxo» أو «user») وكم
(`fee_amount`) كما قالها الوسيطُ عند فتح الصفحة ثمّ عند تأكيد الدفع. **لا قيدَ يُكتب ولا يُمسّ** — يُقرأ في صفحتَي المالية.

Revision ID: 0123
Revises: 0122
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0123"
down_revision = "0122"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payment_requests", sa.Column("fee_payer", sa.String(length=16), nullable=True))
    op.add_column("payment_requests", sa.Column("fee_amount", sa.Numeric(12, 3), nullable=True))


def downgrade() -> None:
    op.drop_column("payment_requests", "fee_amount")
    op.drop_column("payment_requests", "fee_payer")
