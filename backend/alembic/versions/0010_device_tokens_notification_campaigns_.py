"""device tokens notification campaigns cliq acquirer

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-10 05:32:27.710503
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '0010'
down_revision: str | None = '0009'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # قيمة جديدة على نوعٍ قائم (المرحلة 8): حساب التاجر الذي يشهد على شحن
    # المحفظة بكليك. `IF NOT EXISTS` يجعلها قابلة للإعادة بعد downgrade جزئي —
    # النوع لا يُسقط هنا لأن جداول `0007`/`0008` ما زالت تستعمله.
    # ولا تُستعمل القيمة في أي قيدٍ في هذه الترحيلة: postgres يسمح بإضافتها
    # داخل معاملة ويمنع **استعمالها** فيها (نفس درس `0009`).
    op.execute("ALTER TYPE payment_provider ADD VALUE IF NOT EXISTS 'cliq_acquirer'")

    # `country_code` أنشأته `0002` وما زالت جداوله قائمة، فهو هنا
    # بـ `create_type=False` — وبغيره يفشل upgrade بـ "type already exists".
    # الأنواع الأربعة الجديدة (device_platform، campaign_audience،
    # campaign_status، delivery_status) تُنشأ هنا وتُسقط في downgrade.
    country_code = postgresql.ENUM('LY', 'JO', name='country_code', create_type=False)

    op.create_table('notification_settings',
    sa.Column('country_code', country_code, nullable=False),
    sa.Column('quiet_hours_start', sa.Time(), nullable=False),
    sa.Column('quiet_hours_end', sa.Time(), nullable=False),
    sa.Column('timezone', sa.String(length=64), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notification_settings')),
    sa.UniqueConstraint('country_code', name='uq_notification_settings_country_code')
    )
    op.create_table('device_tokens',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('device_id', sa.String(length=64), nullable=False),
    sa.Column('token', sa.String(length=512), nullable=False),
    sa.Column('platform', sa.Enum('android', 'ios', 'web', name='device_platform'), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_device_tokens_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_device_tokens')),
    sa.UniqueConstraint('token', name='uq_device_tokens_token'),
    sa.UniqueConstraint('user_id', 'device_id', name='uq_device_tokens_user_device')
    )
    op.create_index(op.f('ix_device_tokens_user_id'), 'device_tokens', ['user_id'], unique=False)
    op.create_table('notification_campaigns',
    sa.Column('title', sa.String(length=120), nullable=False),
    sa.Column('body', sa.String(length=500), nullable=False),
    sa.Column('audience', sa.Enum('all_riders', 'all_drivers', 'by_country', 'segment', name='campaign_audience'), nullable=False),
    sa.Column('country_code', country_code, nullable=True),
    sa.Column('status', sa.Enum('draft', 'scheduled', 'sent', 'cancelled', name='campaign_status'), nullable=False),
    sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('sent_count', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(audience::text = 'by_country') <= (country_code IS NOT NULL)", name=op.f('ck_notification_campaigns_campaign_country_required')),
    sa.CheckConstraint("(status::text = 'scheduled') <= (scheduled_at IS NOT NULL)", name=op.f('ck_notification_campaigns_campaign_scheduled_requires_time')),
    sa.CheckConstraint('sent_count >= 0', name=op.f('ck_notification_campaigns_campaign_sent_count_non_negative')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_notification_campaigns_created_by_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notification_campaigns'))
    )
    op.create_index(op.f('ix_notification_campaigns_status'), 'notification_campaigns', ['status'], unique=False)
    op.create_index('ix_notification_campaigns_status_scheduled', 'notification_campaigns', ['status', 'scheduled_at'], unique=False)
    op.create_table('notification_deliveries',
    sa.Column('campaign_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.Enum('sent', 'failed', 'skipped', name='delivery_status'), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['notification_campaigns.id'], name=op.f('fk_notification_deliveries_campaign_id_notification_campaigns'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notification_deliveries_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notification_deliveries')),
    sa.UniqueConstraint('campaign_id', 'user_id', name='uq_notification_deliveries_campaign_user')
    )
    op.create_index(op.f('ix_notification_deliveries_campaign_id'), 'notification_deliveries', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_notification_deliveries_user_id'), 'notification_deliveries', ['user_id'], unique=False)
    op.add_column('provider_orders', sa.Column('qr_payload', sa.String(length=512), nullable=True))
    op.add_column('users', sa.Column('marketing_push_enabled', sa.Boolean(), server_default='true', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'marketing_push_enabled')
    op.drop_column('provider_orders', 'qr_payload')
    op.drop_index(op.f('ix_notification_deliveries_user_id'), table_name='notification_deliveries')
    op.drop_index(op.f('ix_notification_deliveries_campaign_id'), table_name='notification_deliveries')
    op.drop_table('notification_deliveries')
    op.drop_index('ix_notification_campaigns_status_scheduled', table_name='notification_campaigns')
    op.drop_index(op.f('ix_notification_campaigns_status'), table_name='notification_campaigns')
    op.drop_table('notification_campaigns')
    op.drop_index(op.f('ix_device_tokens_user_id'), table_name='device_tokens')
    op.drop_table('device_tokens')
    op.drop_table('notification_settings')

    # postgres لا يُسقط أنواع ENUM مع جداولها، فبغير هذا يفشل upgrade التالي
    # بـ "type already exists". و`payment_provider` ليس منها: أنشأته ترحيلةٌ
    # سابقة وما زالت جداولها قائمة — وقيمةٌ أُضيفت إلى ENUM لا تُحذف منه أصلاً.
    for enum_name in (
        'delivery_status',
        'campaign_status',
        'campaign_audience',
        'device_platform',
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
