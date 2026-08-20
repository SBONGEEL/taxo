"""نسبةُ العمولة تتبع الاشتراك — لا الدولةَ وحدَها

**والصفرُ في التعبئة صحيحٌ لا افتراضٌ آمن** (§25.11): العمولةُ لم تُشغَّل قط في
أيِّ سوق، فكلُّ اشتراكٍ قائمٍ اليومَ اشتُري على صفر — والتعبئةُ تُثبّت واقعاً لا
تخترع قيمة.

**و`drivers.commission_percent_from_subscription` تبقى `NULL`** في التعبئة: هي
عمودٌ محضَّرٌ يكتبه الشراء، و`NULL` تعني «اقرأ نسبةَ الدولة». وملؤها بصفرٍ يقول
«اشتراكٌ ساري بصفر» عمّن قد لا يكون له اشتراكٌ أصلاً — وهما حالان لا يحملهما
رقمٌ واحد.

Revision ID: 0051
Revises: 0050
Create Date: 2026-08-20 06:07:49.050121
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0051'
down_revision: str | None = '0050'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('driver_subscriptions', sa.Column('commission_percent_at_purchase', sa.Numeric(precision=5, scale=2), server_default=sa.text('0'), nullable=False))
    op.add_column('drivers', sa.Column('commission_percent_from_subscription', sa.Numeric(precision=5, scale=2), nullable=True))

    # **ومن له اشتراكٌ ساري الآن يأخذ نسبتَه المجمَّدة** — وهي صفرٌ للجميع،
    # فالعمودُ يُملأ لمن يعمل اليومَ بدل أن ينتظر تجديدَه
    op.execute(
        """
        UPDATE drivers d SET commission_percent_from_subscription = 0
        WHERE EXISTS (
            SELECT 1 FROM driver_subscriptions s
            WHERE s.driver_id = d.id AND s.status = 'active'
              AND s.starts_at <= now() AND s.expires_at > now()
        )
        """
    )


def downgrade() -> None:
    op.drop_column('drivers', 'commission_percent_from_subscription')
    op.drop_column('driver_subscriptions', 'commission_percent_at_purchase')
