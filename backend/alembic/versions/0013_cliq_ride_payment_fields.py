"""cliq ride payment fields

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-10 12:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0013'
down_revision: str | None = '0012'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # صفحة دفع كليك داخل التطبيق (SPEC القسم 6، المرحلة 9): «كل الخطوات
    # تُسجَّل بطوابع زمنية في `payments`: المبلغ، وalias المعروض، والمرجع
    # الداخلي، ومرجع الحوالة، ومن أكّد ومتى». الثلاثة الأولى كانت مفقودة —
    # المبلغ ومن أكّد ومتى قائمة منذ 6-أ.
    op.add_column('payments', sa.Column('cliq_alias', sa.String(length=64), nullable=True))
    op.add_column('payments', sa.Column('cliq_reference', sa.String(length=32), nullable=True))
    op.add_column(
        'payments', sa.Column('cliq_transfer_reference', sa.String(length=64), nullable=True)
    )
    op.add_column(
        'payments',
        sa.Column('cliq_reference_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_unique_constraint(
        'uq_payments_cliq_reference', 'payments', ['cliq_reference']
    )
    # `method::text` لا `method` مباشرةً: الصياغة النصّية لا تحتاج أن يحلّ
    # postgres القيمة إلى نوع ENUM، وهو نفس ما فعلته `0009` مع
    # `provider_orders.purpose` لنفس السبب
    op.create_check_constraint(
        'payment_cliq_fields_method',
        'payments',
        "cliq_reference IS NULL OR method::text = 'cliq'",
    )
    op.create_check_constraint(
        'payment_cliq_transfer_complete',
        'payments',
        '(cliq_transfer_reference IS NULL) = (cliq_reference_at IS NULL)',
    )


def downgrade() -> None:
    op.drop_constraint('payment_cliq_transfer_complete', 'payments', type_='check')
    op.drop_constraint('payment_cliq_fields_method', 'payments', type_='check')
    op.drop_constraint('uq_payments_cliq_reference', 'payments', type_='unique')
    op.drop_column('payments', 'cliq_reference_at')
    op.drop_column('payments', 'cliq_transfer_reference')
    op.drop_column('payments', 'cliq_reference')
    op.drop_column('payments', 'cliq_alias')
