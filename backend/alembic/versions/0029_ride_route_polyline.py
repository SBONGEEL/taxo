"""شكلُ مسار الرحلة على الرحلة (البند ٨)

Revision ID: 0029
Revises: 0028
Create Date: 2026-08-14 05:39:14.298442
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0029'
down_revision: str | None = '0028'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # عمودٌ نصّيٌّ يحمل `[[lng, lat], …]` بصيغة JSON — يُكتب مرةً عند القبول.
    # **قابلٌ للعدم عمداً**: عقدُ Mapbox قد يكون مطفأً أو النداءُ سقط، وخريطةٌ
    # بلا خطٍّ أهونُ من رحلةٍ لا تُقبل. ولا فهرسَ عليه: لا يُبحث به أبداً
    op.add_column('rides', sa.Column('route_polyline', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('rides', 'route_polyline')
