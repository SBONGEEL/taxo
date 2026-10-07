"""بالساعة (SPEC §٦٣-ج/٥) — نوعٌ ثالثٌ على الرحلة، وسعرُها ساعاتٌ مجمَّدةٌ لا طريق، ومحجوزٌ يُدفع عند البدء.

**أعمدةٌ بافتراضٍ يصف كلَّ رحلةٍ قائمةٍ حرفاً** (فارغةٌ لغير الساعة)، **وأرقامُ المالك افتراضاتٌ للأردن** (٨٫٠٠٠ للساعة · ١٥ كم ·
نصفُ ساعةٍ للإلغاء · ٨ ساعاتٍ أقصى) **ولليبيا سعرٌ صفرٌ يُخفيها**. **وقيدُ النوع يعرف `hourly`.**

**ولا جدولَ مالٍ يُمسّ قائمُه.** **و`downgrade` مقيسٌ لا مقروء**: رحلةٌ بالساعة قائمةٌ تُسقط التراجعَ عمداً (القيدُ القديمُ لا يعرفها).

Revision ID: 0094
Revises: 0093
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0094"
down_revision = "0093"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("service_settings", sa.Column("hourly_rate", sa.Numeric(12, 3), server_default=sa.text("0"), nullable=False))
    op.add_column("service_settings", sa.Column("hourly_km_per_hour", sa.SmallInteger(), server_default=sa.text("15"), nullable=False))
    op.add_column("service_settings", sa.Column("hourly_cancel_minutes", sa.SmallInteger(), server_default=sa.text("30"), nullable=False))
    op.add_column("service_settings", sa.Column("hourly_max_hours", sa.SmallInteger(), server_default=sa.text("8"), nullable=False))
    op.create_check_constraint(
        "service_settings_hourly_valid",
        "service_settings",
        "hourly_rate >= 0 AND hourly_km_per_hour >= 0 AND hourly_cancel_minutes >= 0 AND hourly_max_hours BETWEEN 1 AND 24",
    )
    op.execute("UPDATE service_settings SET hourly_rate = 8.000 WHERE country_code = 'JO'")

    op.add_column("rides", sa.Column("hourly_hours", sa.SmallInteger(), nullable=True))
    op.add_column("rides", sa.Column("hourly_rate_at_ride", sa.Numeric(12, 3), nullable=True))
    op.add_column("rides", sa.Column("hourly_km_per_hour_at_ride", sa.SmallInteger(), nullable=True))
    op.add_column("rides", sa.Column("hourly_cancel_minutes_at_ride", sa.SmallInteger(), nullable=True))
    op.add_column("rides", sa.Column("hourly_prepay_method", sa.String(length=8), nullable=True))
    op.drop_constraint(op.f("ck_rides_ride_type_valid"), "rides", type_="check")
    op.create_check_constraint("ride_type_valid", "rides", "ride_type IN ('standard', 'parcel', 'hourly')")
    op.create_check_constraint(
        "ride_hourly_fields",
        "rides",
        "(ride_type = 'hourly') = (hourly_hours IS NOT NULL) AND (hourly_prepay_method IS NULL OR hourly_prepay_method IN ('wallet', 'cash'))",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_rides_ride_hourly_fields"), "rides", type_="check")
    op.drop_constraint(op.f("ck_rides_ride_type_valid"), "rides", type_="check")
    op.create_check_constraint("ride_type_valid", "rides", "ride_type IN ('standard', 'parcel')")
    for column in ("hourly_prepay_method", "hourly_cancel_minutes_at_ride", "hourly_km_per_hour_at_ride", "hourly_rate_at_ride", "hourly_hours"):
        op.drop_column("rides", column)
    op.drop_constraint(op.f("ck_service_settings_service_settings_hourly_valid"), "service_settings", type_="check")
    for column in ("hourly_max_hours", "hourly_cancel_minutes", "hourly_km_per_hour", "hourly_rate"):
        op.drop_column("service_settings", column)
