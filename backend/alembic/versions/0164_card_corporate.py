"""بطاقاتُ الشركات بفاتورة (SPEC §١٠٠-ب/٧، أمرُ المالك ٢٠٢٦-١١-١٢ البند ٧)

Revision ID: 0164
Revises: 0163
Create Date: 2026-11-14

**ما تفعله** (تغييراتُ جداول البطاقات التي أقرّها المالك ٢٠٢٦-١١-١٣):
- `card_batches.buyer_company` و`buyer_tax_number` و`invoice_number` — **دفعةٌ تُباع لشركةٍ تُعلَّم بها**، ورقمُ فاتورتها متتابعٌ في سوقها.
  **وكلُّ دفعةٍ قائمةٍ تبقى بلا مشترٍ** (أعمدةٌ فارغة)، فلا يتغيّر معنى ما صدر.
- `taxo_card_settings.invoice_seller_name` و`invoice_seller_tax_number` — **بياناتُ البائع على الفاتورة يكتبها المالك**، فارغةٌ افتراضاً
  (لا تُخترع بياناتُ شركة).

**ولا جدولَ مالٍ هنا**: الفاتورةُ تُقرأ من الدفعة (الفئةُ × العدد) ولا تُكتب في دفتر. **والنزولُ يحذف الأعمدة**.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0164"
down_revision = "0163"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("card_batches", sa.Column("buyer_company", sa.String(160), nullable=True))
    op.add_column("card_batches", sa.Column("buyer_tax_number", sa.String(40), nullable=True))
    op.add_column("card_batches", sa.Column("invoice_number", sa.Integer(), nullable=True))
    op.create_unique_constraint("uq_card_batches_country_invoice", "card_batches", ["country_code", "invoice_number"])
    op.create_check_constraint(
        "card_batches_invoice_has_buyer", "card_batches", "(buyer_company IS NULL) = (invoice_number IS NULL)"
    )
    op.add_column("taxo_card_settings", sa.Column("invoice_seller_name", sa.String(160), nullable=True))
    op.add_column("taxo_card_settings", sa.Column("invoice_seller_tax_number", sa.String(40), nullable=True))


def downgrade() -> None:
    op.drop_column("taxo_card_settings", "invoice_seller_tax_number")
    op.drop_column("taxo_card_settings", "invoice_seller_name")
    op.drop_constraint("card_batches_invoice_has_buyer", "card_batches", type_="check")
    op.drop_constraint("uq_card_batches_country_invoice", "card_batches", type_="unique")
    op.drop_column("card_batches", "invoice_number")
    op.drop_column("card_batches", "buyer_tax_number")
    op.drop_column("card_batches", "buyer_company")
