"""**الفقاعتان** (أمرُ المالك ٢٠٢٦-١١-٢٠ الرابع، SPEC §١١٠): عمودُ الاستراحة وجدولُ الردود السريعة.

* `drivers.break_until` — متّصلٌ ولا عروضَ حتى هذه اللحظة (البند ٤٤). فارغٌ للجميع بعد الترحيلة، فلا يتغيّر توزيعُ أحد.
* `quick_reply_settings` — نصوصُ الردود السريعة لكلِّ دولة من اللوحة (البند ٥٠)؛ غيابُ الصفِّ افتراضُ الخدمة.

**لا يمسّ جدولَ مال**. **والرجوعُ** يحذف الاثنين؛ ومن كان في استراحةٍ يعود إلى التوزيع فوراً، والردودُ تعود إلى افتراضها — سلوكُ ما قبل
هذه الترحيلة حرفاً (والمفاتيحُ مطفأةٌ فلا شيءَ يقرؤهما قبل الإشعال).

Revision ID: 0181
Revises: 0180
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0181"
down_revision = "0180"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("drivers", sa.Column("break_until", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "quick_reply_settings",
        sa.Column("country_code", postgresql.ENUM(name="country_code", create_type=False), primary_key=True),
        sa.Column("driver_texts", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("rider_texts", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("quick_reply_settings")
    op.drop_column("drivers", "break_until")
