"""payment gateways: وسيطا الجزائر (Chargily · SofizPay) في صفحة العقود، ومن يحمل رسومَ الوسيط

Revision ID: 0114
Revises: 0113
Create Date: 2026-10-11

**ما تضيفه** (SPEC §٧٣-هـ المرحلة ٣): قيمتان في نوع العقد (`provider_key`: `chargily` · `sofizpay`) — **تُختمان قبل أيِّ استعمال** (نمطُ
`0018`/`0111`) — وعمودُ `payment_providers.fee_bearer` (`taxo` · `user` · `split`) **افتراضُه `taxo`** فكلُّ طريقةٍ قائمةٍ تبقى كما هي.

**ولا عقدَ يُكتب ولا طريقةَ تُفعَّل** — يُبنى الوسيطان مطفأين بلا مفاتيح (أمرُ المالك). والنزولُ يحذف العمودَ وقيدَه، وقيمتا التعداد تبقيان
(لا تُحذف قيمةُ تعدادٍ في PostgreSQL) — و`IF NOT EXISTS` يجعل الصعودَ بعده نظيفاً.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0114"
down_revision = "0113"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE provider_key ADD VALUE IF NOT EXISTS 'chargily'")
    op.execute("ALTER TYPE provider_key ADD VALUE IF NOT EXISTS 'sofizpay'")
    op.execute("COMMIT")
    op.add_column(
        "payment_providers",
        sa.Column("fee_bearer", sa.String(length=8), server_default=sa.text("'taxo'"), nullable=False),
    )
    op.create_check_constraint(
        "payment_provider_fee_bearer_valid", "payment_providers", "fee_bearer IN ('taxo', 'user', 'split')"
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_payment_providers_payment_provider_fee_bearer_valid"), "payment_providers", type_="check"
    )
    op.drop_column("payment_providers", "fee_bearer")
