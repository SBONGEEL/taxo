"""algeria withdrawals: قنواتُ صرف الكابتن الجزائريّ، ووجهةُ الصرف مجمَّدةً على الطلب

Revision ID: 0115
Revises: 0114
Create Date: 2026-10-11

**ما تضيفه** (SPEC §٧٣-هـ المرحلة ٤): ثلاثُ قيمٍ في `withdrawal_method` (`ccp` · `baridimob` · `cash_office`) — **تُختم قبل أيِّ استعمال**
(نمطُ `0114`) — وعمودان على `withdrawal_requests`: `payout_account` (رقمُ CCP أو RIP أو RIB) و`payout_holder` (صاحبُه)، **فارغان لكلِّ صفٍّ
قائم**؛ وقيدٌ يمنع طلبَ CCP أو BaridiMob بلا وجهة.

**ولا صفَّ مالٍ يُكتب ولا يُعدَّل**: عمودان فارغان وقيدٌ لا يمسّ صفّاً قائماً (كلُّها `cliq`/`bank`). والنزولُ يحذف القيدَ والعمودين،
والقيمُ الثلاثُ تبقى (لا تُحذف قيمةُ تعدادٍ في PostgreSQL) — و`IF NOT EXISTS` يجعل الصعودَ بعده نظيفاً.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0115"
down_revision = "0114"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE withdrawal_method ADD VALUE IF NOT EXISTS 'ccp'")
    op.execute("ALTER TYPE withdrawal_method ADD VALUE IF NOT EXISTS 'baridimob'")
    op.execute("ALTER TYPE withdrawal_method ADD VALUE IF NOT EXISTS 'cash_office'")
    op.execute("COMMIT")
    op.add_column("withdrawal_requests", sa.Column("payout_account", sa.String(length=34), nullable=True))
    op.add_column("withdrawal_requests", sa.Column("payout_holder", sa.String(length=120), nullable=True))
    op.create_check_constraint(
        "withdrawal_payout_destination",
        "withdrawal_requests",
        "method::text NOT IN ('ccp', 'baridimob') OR (payout_account IS NOT NULL AND payout_holder IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_withdrawal_requests_withdrawal_payout_destination"), "withdrawal_requests", type_="check"
    )
    op.drop_column("withdrawal_requests", "payout_holder")
    op.drop_column("withdrawal_requests", "payout_account")
