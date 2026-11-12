"""payment_settings.payment_method_order — ترتيبُ طرق الدفع لكلِّ سوق، وWhop أوّلاً في الأردن (أمرُ المالك ٢٠٢٦-١١-١٣)

Revision ID: 0161
Revises: 0160
Create Date: 2026-11-13

**ما تفعله**: عمودُ `payment_method_order` (JSONB، قائمةٌ فارغةٌ افتراضاً = «كما كان») في `payment_settings` — **جدولُ سياسات الدفع
لا جدولُ مال**: لا رصيدَ فيه ولا قيد. **وتكتب ترتيبَ الأردن** `["card", "wallet", "cliq", "cash"]` — البطاقةُ (Whop) أوّلاً ومقترحةً
مسبقاً، وكليكُ والنقدُ تحتها كما هما. **والجزائرُ وليبيا فارغتان: لا يتغيّر فيهما حرف.** ويُعدَّل من اللوحة («سياسات الدفع»).

**والنزولُ يحذف العمود** — ولا مالَ فيه يضيع: ترتيبُ عرضٍ وحدَه.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0161"
down_revision = "0160"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payment_settings",
        sa.Column("payment_method_order", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.create_check_constraint(
        "payment_method_order_is_array", "payment_settings", "jsonb_typeof(payment_method_order) = 'array'"
    )
    op.get_bind().execute(
        sa.text(
            "UPDATE payment_settings SET payment_method_order = '[\"card\", \"wallet\", \"cliq\", \"cash\"]'::jsonb"
            " WHERE country_code = 'JO'"
        )
    )


def downgrade() -> None:
    op.drop_constraint("payment_method_order_is_array", "payment_settings", type_="check")
    op.drop_column("payment_settings", "payment_method_order")
