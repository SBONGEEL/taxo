"""بطاقاتُ الهدية بالكشط (SPEC §١٠٠-أ/٣، أمرُ المالك ٢٠٢٦-١١-١٣ البند ٣)

Revision ID: 0162
Revises: 0161
Create Date: 2026-11-14

**ما تفعله** (تغييراتُ جداول البطاقات التي أقرّها المالك ٢٠٢٦-١١-١٣):
- `card_batches.kind` — `batch` (الدفعةُ كما كانت) أو `gift`؛ **كلُّ صفٍّ قائمٍ يأخذ `batch`** فلا يتغيّر معنى دفعةٍ صدرت.
- `taxo_cards.code_envelope` — **رمزُ بطاقة الهدية وحدَها معمًّى** (Fernet) حتى يُكشط، ثمّ يُمحى (`NULL`)؛ **فارغٌ لكلِّ بطاقةٍ قائمة**.
- `card_gift_links` — رابطُ الهدية الخاصّ: **بصمةُ الرابط لا الرابط**، والتصميم، والحالُ بأوقاتها (أُرسل · فُتح · كُشط · أُلغي).

**ولا جدولَ مالٍ هنا**: لا دفترَ ولا دفعات. والبطاقةُ تشحن بالمسار القائم نفسِه (§٧٣-هـ). **والنزولُ يحذف الجدولَ والعمودين** — ولا مالَ
يضيع: رمزٌ معمًّى لم يُكشط يضيع مع العمود، فتبقى بطاقتُه قائمةً بلا من يعرف رمزَها (تُلغى من اللوحة).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0162"
down_revision = "0161"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "card_batches",
        sa.Column("kind", sa.String(16), nullable=False, server_default=sa.text("'batch'")),
    )
    op.create_check_constraint("card_batches_kind_known", "card_batches", "kind IN ('batch', 'gift')")
    op.add_column("taxo_cards", sa.Column("code_envelope", JSONB(), nullable=True))

    op.create_table(
        "card_gift_links",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("card_id", UUID(as_uuid=True), sa.ForeignKey("taxo_cards.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("country_code", postgresql.ENUM("LY", "JO", "DZ", name="country_code", create_type=False), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("design", sa.String(16), nullable=False),
        sa.Column("recipient_name", sa.String(80), nullable=True),
        sa.Column("message", sa.String(200), nullable=True),
        sa.Column("sent_channel", sa.String(16), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("open_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("scratched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.String(500), nullable=True),
        sa.Column("cancelled_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("card_id", name="uq_card_gift_links_card"),
        sa.UniqueConstraint("token_hash", name="uq_card_gift_links_token_hash"),
        sa.CheckConstraint("design IN ('night', 'sunrise', 'city')", name="card_gift_links_design_known"),
        sa.CheckConstraint(
            "sent_channel IS NULL OR sent_channel IN ('whatsapp', 'sms', 'email', 'copy')", name="card_gift_links_channel_known"
        ),
    )
    op.create_index("ix_card_gift_links_country_created", "card_gift_links", ["country_code", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_card_gift_links_country_created", table_name="card_gift_links")
    op.drop_table("card_gift_links")
    op.drop_column("taxo_cards", "code_envelope")
    op.drop_constraint("card_batches_kind_known", "card_batches", type_="check")
    op.drop_column("card_batches", "kind")
