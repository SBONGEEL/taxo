"""رحلةٌ لشخصٍ آخر (SPEC §٦٣-ج/١) — راكبٌ فعليٌّ ودافعٌ على الرحلة، ورابطُ تتبّعٍ عامّ.

**أعمدةٌ تُضاف بافتراضٍ يصف كلَّ رحلةٍ قائمةٍ حرفاً**: `for_other = false` و`payer = 'requester'` — فلا تعبئةَ ولا تخمين،
**والمفتاحُ مطفأٌ افتراضاً** فلا رحلةَ جديدةً تحملها حتى يُشعله المالكُ لسوق. **وليس جدولَ مالٍ يُمسّ**: `rides` تكتسب
من يدفع، ولا يتغيّر مبلغٌ ولا قيدٌ قائم.

**و`downgrade` مقيسٌ لا مقروء**: يحذف الجدولَ والأعمدةَ والقيد — وثمنُه أن رحلةً جاريةً لغير صاحبها تصير رحلةً له، **ودفعةُ
نقدها إن لم تُفتح بعدُ لا تُفتح تلقائياً**؛ لا شيءَ غيرُه.

Revision ID: 0090
Revises: 0089
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0090"
down_revision = "0089"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rides",
        sa.Column("for_other", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("rides", sa.Column("passenger_name", sa.String(length=80), nullable=True))
    op.add_column("rides", sa.Column("passenger_phone", sa.String(length=20), nullable=True))
    op.add_column(
        "rides", sa.Column("passenger_erased_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "rides",
        sa.Column("payer", sa.String(length=16), server_default=sa.text("'requester'"), nullable=False),
    )
    op.create_check_constraint(
        "ride_for_other_fields",
        "rides",
        "payer IN ('requester', 'passenger_cash') AND (for_other OR ("
        "passenger_name IS NULL AND passenger_phone IS NULL AND payer = 'requester'))",
    )
    # **الكنسُ اليوميُّ يسأل هذا وحدَه**: رحلاتٌ لغير أصحابها لم يُمحَ راكبُها — فهرسٌ جزئيٌّ صغيرٌ لا يمرّ على كلِّ الرحلات
    op.create_index(
        "ix_rides_passenger_pending_erase",
        "rides",
        ["created_at"],
        postgresql_where=sa.text("for_other AND passenger_erased_at IS NULL"),
    )

    op.create_table(
        "ride_track_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ride_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["ride_id"], ["rides.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ride_track_tokens")),
        sa.UniqueConstraint("ride_id", name=op.f("uq_ride_track_tokens_ride_id")),
        sa.UniqueConstraint("token", name=op.f("uq_ride_track_tokens_token")),
    )


def downgrade() -> None:
    op.drop_table("ride_track_tokens")
    op.drop_index("ix_rides_passenger_pending_erase", table_name="rides")
    op.drop_constraint(op.f("ck_rides_ride_for_other_fields"), "rides", type_="check")
    op.drop_column("rides", "payer")
    op.drop_column("rides", "passenger_erased_at")
    op.drop_column("rides", "passenger_phone")
    op.drop_column("rides", "passenger_name")
    op.drop_column("rides", "for_other")
