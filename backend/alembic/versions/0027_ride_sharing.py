"""مشاركةُ الرحلة بين ركاب: المجموعةُ والمقعدُ وحارسُهما، وإعداداتُها (12-ي)

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-13 06:44:44.017819
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


_ACTIVE = "status IN ('accepted', 'arrived', 'in_progress', 'at_stop')"

revision: str = '0027'
down_revision: str | None = '0026'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('ride_sharing_settings',
    sa.Column(
            "country_code",
            postgresql.ENUM("LY", "JO", name="country_code", create_type=False),
            nullable=False,
        ),
    sa.Column('discount_percent', sa.Numeric(precision=5, scale=2), server_default=sa.text('0'), nullable=False),
    sa.Column('corridor_km', sa.Numeric(precision=6, scale=3), server_default=sa.text('2'), nullable=False),
    sa.Column('max_detour_minutes', sa.SmallInteger(), server_default=sa.text('7'), nullable=False),
    sa.Column('partner_wait_seconds', sa.SmallInteger(), server_default=sa.text('90'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('discount_percent >= 0 AND discount_percent <= 100 AND corridor_km >= 0 AND max_detour_minutes >= 0 AND partner_wait_seconds >= 0', name=op.f('ck_ride_sharing_settings_ride_sharing_values_in_range')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ride_sharing_settings'))
    )
    op.create_index(op.f('ix_ride_sharing_settings_country_code'), 'ride_sharing_settings', ['country_code'], unique=True)
    op.add_column('rides', sa.Column('share_group_id', sa.UUID(), nullable=True))
    op.add_column('rides', sa.Column('share_seat', sa.SmallInteger(), server_default='1', nullable=False))
    op.drop_index(op.f('uq_rides_active_driver'), table_name='rides', postgresql_where=sa.text(_ACTIVE))
    op.create_index('uq_rides_active_driver', 'rides', ['driver_id', 'share_seat'], unique=True, postgresql_where=sa.text(_ACTIVE))
    op.create_index(op.f('ix_rides_share_group_id'), 'rides', ['share_group_id'], unique=False)
    op.create_index('uq_rides_active_share_group', 'rides', ['share_group_id', 'share_seat'], unique=True, postgresql_where=sa.text(_ACTIVE + " AND share_group_id IS NOT NULL"))
    op.create_check_constraint(op.f('ck_rides_ride_share_seat_valid'), 'rides', 'share_seat IN (1, 2) AND (share_seat = 1 OR share_group_id IS NOT NULL)')


def downgrade() -> None:
    op.drop_constraint(op.f('ck_rides_ride_share_seat_valid'), 'rides', type_='check')
    op.drop_index('uq_rides_active_share_group', table_name='rides', postgresql_where=sa.text(_ACTIVE + " AND share_group_id IS NOT NULL"))
    op.drop_index(op.f('ix_rides_share_group_id'), table_name='rides')
    op.drop_index('uq_rides_active_driver', table_name='rides', postgresql_where=sa.text(_ACTIVE))
    op.create_index(op.f('uq_rides_active_driver'), 'rides', ['driver_id'], unique=True, postgresql_where=sa.text(_ACTIVE))
    op.drop_column('rides', 'share_seat')
    op.drop_column('rides', 'share_group_id')
    op.drop_index(op.f('ix_ride_sharing_settings_country_code'), table_name='ride_sharing_settings')
    op.drop_table('ride_sharing_settings')
