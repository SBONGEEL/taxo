"""الطرد (SPEC §٦٣-ج/٤) — نوعٌ على الرحلة، ومستلمٌ يُمحى بعد ٣٠ يوماً، ودافعٌ ثالث «المستلمُ نقداً»، ورسمٌ للكبتن من إعدادات الخدمات.

**أعمدةٌ بافتراضٍ يصف كلَّ رحلةٍ قائمةٍ حرفاً**: `ride_type = 'standard'` والمستلمُ فارغ — فلا تعبئة. **ورسمُ الطرد الافتراضيُّ للأردن ٠٫٥٠٠
بنصِّ المالك، ولليبيا صفرٌ يُخفيه**. **وقيدُ أطراف الرحلة يُعاد بناؤه** ليعرف الدافعَ الثالث والمستلم: «المستلمُ نقداً» للطرد وحدَه،
والمستلمُ لا يُكتب على رحلةٍ ليست طرداً. **والفهرسُ الجزئيُّ للكنس يشمل الطرد** — بياناتُ المستلم تُمحى بالكنس نفسِه.

**ولا جدولَ مالٍ يُمسّ قائمُه**: `rides` تكتسب نوعاً ومستلماً، و`service_settings` عموداً.

**و`downgrade` مقيسٌ لا مقروء**: يُسقط الأعمدةَ ويعيد القيدَ والفهرسَ القديمين — **وطردٌ قائمٌ يُسقط التراجع** عمداً (القيدُ القديم لا يعرف
`recipient_cash`): بياناتُ مستلمٍ لا تُمحى بتراجعٍ صامت.

Revision ID: 0093
Revises: 0092
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0093"
down_revision = "0092"
branch_labels = None
depends_on = None

OLD_PARTIES = (
    "payer IN ('requester', 'passenger_cash') AND (for_other OR ("
    "passenger_name IS NULL AND passenger_phone IS NULL AND payer = 'requester'))"
)
NEW_PARTIES = (
    "payer IN ('requester', 'passenger_cash', 'recipient_cash') "
    "AND (for_other OR (passenger_name IS NULL AND passenger_phone IS NULL)) "
    "AND (payer <> 'passenger_cash' OR for_other) "
    "AND (payer <> 'recipient_cash' OR ride_type = 'parcel') "
    "AND (ride_type = 'parcel' OR (recipient_name IS NULL AND recipient_phone IS NULL AND recipient_address IS NULL))"
)


def upgrade() -> None:
    op.add_column("service_settings", sa.Column("parcel_fee", sa.Numeric(12, 3), server_default=sa.text("0"), nullable=False))
    op.create_check_constraint("service_settings_parcel_fee_valid", "service_settings", "parcel_fee >= 0")
    op.execute("UPDATE service_settings SET parcel_fee = 0.500 WHERE country_code = 'JO'")

    op.add_column("rides", sa.Column("ride_type", sa.String(length=16), server_default=sa.text("'standard'"), nullable=False))
    op.add_column("rides", sa.Column("recipient_name", sa.String(length=80), nullable=True))
    op.add_column("rides", sa.Column("recipient_phone", sa.String(length=20), nullable=True))
    op.add_column("rides", sa.Column("recipient_address", sa.String(length=255), nullable=True))
    op.create_check_constraint("ride_type_valid", "rides", "ride_type IN ('standard', 'parcel')")
    op.drop_constraint(op.f("ck_rides_ride_for_other_fields"), "rides", type_="check")
    op.create_check_constraint("ride_for_other_fields", "rides", NEW_PARTIES)
    op.drop_index("ix_rides_passenger_pending_erase", table_name="rides")
    op.create_index(
        "ix_rides_passenger_pending_erase",
        "rides",
        ["created_at"],
        postgresql_where=sa.text("(for_other OR ride_type = 'parcel') AND passenger_erased_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_rides_passenger_pending_erase", table_name="rides")
    op.create_index(
        "ix_rides_passenger_pending_erase",
        "rides",
        ["created_at"],
        postgresql_where=sa.text("for_other AND passenger_erased_at IS NULL"),
    )
    op.drop_constraint(op.f("ck_rides_ride_for_other_fields"), "rides", type_="check")
    op.create_check_constraint("ride_for_other_fields", "rides", OLD_PARTIES)
    op.drop_constraint(op.f("ck_rides_ride_type_valid"), "rides", type_="check")
    for column in ("recipient_address", "recipient_phone", "recipient_name", "ride_type"):
        op.drop_column("rides", column)
    op.drop_constraint(op.f("ck_service_settings_service_settings_parcel_fee_valid"), "service_settings", type_="check")
    op.drop_column("service_settings", "parcel_fee")
