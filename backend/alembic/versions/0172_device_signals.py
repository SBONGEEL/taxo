"""device signals: إشاراتُ جهاز الكبتن للمشرف — موقعٌ مزيَّف، جهازٌ معدَّل (أمرُ المالك ٢٠٢٦-١١-١٨، SPEC §١٠٣ B/17 و25)

Revision ID: 0172
Revises: 0171
Create Date: 2026-11-18

**عمودان فارغان في `drivers`** — لا جدولَ مالٍ ولا قيمة، على نمط `0169` حرفاً: يملؤهما غلافٌ جديدٌ حين يشتعل مفتاحا
`mock_location_report` و`root_report`، ويقرؤهما المشرفُ في درج الكبتن. **بلاغٌ لا حجب. والنزولُ ينزعهما** (لا مالَ فيهما).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0172"
down_revision = "0171"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("drivers", sa.Column("device_signals", postgresql.JSONB(), nullable=True))
    op.add_column("drivers", sa.Column("device_signals_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("drivers", "device_signals_at")
    op.drop_column("drivers", "device_signals")
