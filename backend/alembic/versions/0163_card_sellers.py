"""بائعو البطاقات في المحلّات والبيعُ لحظةَ الطلب (SPEC §١٠٠-ب/٤–٥، أمرُ المالك ٢٠٢٦-١١-١٢ البندان ٤ و٥)

Revision ID: 0163
Revises: 0162
Create Date: 2026-11-14

**ما تفعله** (تغييراتُ جداول البطاقات التي أقرّها المالك ٢٠٢٦-١١-١٣):
- `user_role` ← `card_seller` — **بائعُ بطاقاتٍ في محلٍّ موزّع**: صفحةُ البيع وحدَها، والعاملُ الثاني إلزاميّ.
- `card_shop_staff` — ربطُ حساب البائع بمحلّه (واحدٌ لكلِّ حساب)، ويُوقف ولا يُحذف.
- `card_batches.kind` يقبل `pos` — بطاقةٌ واحدةٌ وُلّدت لحظةَ البيع؛ **وكلُّ صفٍّ قائمٍ كما هو**.
- `taxo_card_settings` — `pos_enabled` (**مطفأٌ**)، و`pos_daily_cap` (عددُ بطاقاتٍ لا مال)، و`pos_validity_days`.

**ولا جدولَ مالٍ هنا**: لا رصيدَ للمحلّ ولا حدَّ ائتمانٍ ولا عمولةَ ولا تسوية — **تلك قيمُ المالك وتنتظره** (§١٠٠-ب/٥-٦).
والخصمُ ونمطُ الدفع يُجمَّدان على الدفعة كما يُجمَّدان اليوم. **والنزولُ** يحذف الجدولَ والأعمدةَ ويعيد قيدَ النوع — **ويرفض إن
وُجدت دفعةُ بيعٍ أو حسابُ بائع**، فلا يُترك صفٌّ بنوعٍ لا يعرفه القيد. وقيمةُ التعداد تبقى (Postgres لا ينزعها) بلا أثر.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0163"
down_revision = "0162"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'card_seller'")
    op.drop_constraint("card_batches_kind_known", "card_batches", type_="check")
    op.create_check_constraint("card_batches_kind_known", "card_batches", "kind IN ('batch', 'gift', 'pos')")
    op.add_column("taxo_card_settings", sa.Column("pos_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("taxo_card_settings", sa.Column("pos_daily_cap", sa.Integer(), nullable=False, server_default=sa.text("20")))
    op.add_column(
        "taxo_card_settings", sa.Column("pos_validity_days", sa.Integer(), nullable=False, server_default=sa.text("365"))
    )
    op.create_table(
        "card_shop_staff",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("shop_id", UUID(as_uuid=True), sa.ForeignKey("card_shops.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("user_id", name="uq_card_shop_staff_user"),
    )
    op.create_index("ix_card_shop_staff_shop_id", "card_shop_staff", ["shop_id"])


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM card_batches WHERE kind = 'pos') OR EXISTS (SELECT 1 FROM card_shop_staff) THEN
                RAISE EXCEPTION 'دفعاتُ بيعٍ أو حساباتُ بائعين قائمة — لا نزولَ يتركها بلا معنى';
            END IF;
        END $$;
        """
    )
    op.drop_index("ix_card_shop_staff_shop_id", table_name="card_shop_staff")
    op.drop_table("card_shop_staff")
    op.drop_column("taxo_card_settings", "pos_validity_days")
    op.drop_column("taxo_card_settings", "pos_daily_cap")
    op.drop_column("taxo_card_settings", "pos_enabled")
    op.drop_constraint("card_batches_kind_known", "card_batches", type_="check")
    op.create_check_constraint("card_batches_kind_known", "card_batches", "kind IN ('batch', 'gift')")
