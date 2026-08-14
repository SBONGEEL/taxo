"""طلبُ إلغاء التفعيل والرصيدُ المحتجَز (البند ١٣)

Revision ID: 0032
Revises: 0031
Create Date: 2026-08-14 20:28:04.348653
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0032'
down_revision: str | None = '0031'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # **قيمةُ التعداد لا يراها التوليدُ التلقائي** — و`ALTER TYPE` تجوز في
    # المعاملة ما دامت القيمةُ لا تُستعمل فيها (قاعدةُ `0028`/`0031`)
    op.execute("ALTER TYPE driver_status ADD VALUE IF NOT EXISTS 'deactivated'")

    op.create_table('deactivation_requests',
    sa.Column('driver_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'cancelled', name='deactivation_status'), nullable=False),
    sa.Column('reason', sa.String(length=300), nullable=True),
    sa.Column('review_note', sa.String(length=300), nullable=True),
    sa.Column('resolved_by', sa.UUID(), nullable=True),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['driver_id'], ['drivers.id'], name=op.f('fk_deactivation_requests_driver_id_drivers'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], name=op.f('fk_deactivation_requests_resolved_by_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_deactivation_requests'))
    )
    op.create_index(op.f('ix_deactivation_requests_driver_id'), 'deactivation_requests', ['driver_id'], unique=False)
    op.create_index('uq_deactivation_pending', 'deactivation_requests', ['driver_id'], unique=True, postgresql_where="status = 'pending'")
    op.add_column('wallet_settings', sa.Column('withdrawal_reserve_amount', sa.Numeric(precision=12, scale=3), server_default=sa.text('0'), nullable=False))

    # **والقيدُ يُعاد بناؤه ليشمل العمودَ الجديد**: التوليدُ التلقائي لا يقارن
    # قيودَ CHECK، فمبلغٌ سالبٌ كان يمرّ من طبقةٍ عليا يجد الجدولَ مفتوحاً
    op.drop_constraint(
        op.f("ck_wallet_settings_wallet_limits_non_negative"),
        "wallet_settings",
        type_="check",
    )
    op.create_check_constraint(
        "wallet_limits_non_negative",
        "wallet_settings",
        "transfer_daily_limit >= 0 AND transfer_monthly_limit >= 0 "
        "AND min_withdrawal_amount >= 0 AND withdrawal_reserve_amount >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_wallet_settings_wallet_limits_non_negative"),
        "wallet_settings",
        type_="check",
    )
    op.create_check_constraint(
        "wallet_limits_non_negative",
        "wallet_settings",
        "transfer_daily_limit >= 0 AND transfer_monthly_limit >= 0 "
        "AND min_withdrawal_amount >= 0",
    )
    op.drop_column('wallet_settings', 'withdrawal_reserve_amount')
    op.drop_index('uq_deactivation_pending', table_name='deactivation_requests', postgresql_where="status = 'pending'")
    op.drop_index(op.f('ix_deactivation_requests_driver_id'), table_name='deactivation_requests')
    op.drop_table('deactivation_requests')
    # **النوعُ لا يسقط مع جدوله في postgres** — فيُسقط صراحةً وإلا فشل الرفعُ
    # الثاني بـ«type already exists» (قاعدةُ `0002`). و`deactivated` في
    # `driver_status` تبقى: قيمُ التعداد لا تُنزع، والنوعُ يُسقطه من أنشأه
    op.execute("DROP TYPE IF EXISTS deactivation_status")
