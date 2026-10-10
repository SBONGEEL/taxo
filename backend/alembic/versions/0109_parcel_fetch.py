"""«أحضر غرضي» (SPEC §٧٢-ج/١) — الطردُ معكوساً: علمٌ على الرحلة ووصفُ الغرض، ورسمٌ مستقلٌّ في إعدادات الخدمات.

**أعمدةٌ بافتراضٍ يصف كلَّ رحلةٍ قائمةٍ حرفاً**: `parcel_fetch = false` والوصفُ فارغ — فلا تعبئةَ على الرحلات. **والرسمُ يُنسخ من رسم الطرد**
بنصِّ المالك («كالطرد افتراضاً، ويُضبط من اللوحة») — فما ضبطه المالكُ للطرد هو أوّلُ رسمٍ لهذا، **ومفتاحُه المطفأُ يُبقيه خامداً** حتى يُشعَل.

**ولا جدولَ مالٍ يُمسّ**: `rides` تكتسب عمودين، و`service_settings` عموداً.

**و`downgrade` مقيسٌ لا مقروء**: يُسقط القيدَ والأعمدةَ الثلاثة — **ووصفُ غرضٍ لم يُمحَ بعد يذهب معها**، وهو بيانٌ يُمحى بعد ٣٠ يوماً أصلاً.

Revision ID: 0109
Revises: 0108
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0109"
down_revision = "0108"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "service_settings",
        sa.Column("parcel_fetch_fee", sa.Numeric(12, 3), server_default=sa.text("0"), nullable=False),
    )
    op.create_check_constraint("service_settings_parcel_fetch_fee_valid", "service_settings", "parcel_fetch_fee >= 0")
    op.execute("UPDATE service_settings SET parcel_fetch_fee = parcel_fee")

    op.add_column("rides", sa.Column("parcel_fetch", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("rides", sa.Column("parcel_item", sa.String(length=120), nullable=True))
    op.create_check_constraint(
        "ride_parcel_fetch",
        "rides",
        "(NOT parcel_fetch OR (ride_type = 'parcel' AND payer = 'requester')) "
        "AND (parcel_item IS NULL OR ride_type = 'parcel')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_rides_ride_parcel_fetch"), "rides", type_="check")
    op.drop_column("rides", "parcel_item")
    op.drop_column("rides", "parcel_fetch")
    op.drop_constraint(
        op.f("ck_service_settings_service_settings_parcel_fetch_fee_valid"), "service_settings", type_="check"
    )
    op.drop_column("service_settings", "parcel_fetch_fee")
