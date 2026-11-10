"""حملاتُ Push — الحدُّ الأسبوعيّ والمدينةُ والحال والإحصاء (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٩).

* `notification_settings.weekly_marketing_cap` — **أقصى ما يصل المستخدمَ من حملاتٍ في سبعة أيام** لكلِّ دولة (افتراضاً ٣).
* `notification_campaigns.zone_id` — **المدينة/الولاية** (منطقةُ تسعير): من كانت آخرُ رحلاته فيها؛ و`activity` — **الحال**:
  `active` (رحلةٌ في ٣٠ يوماً) · `dormant` (رحلاتٌ قديمةٌ وحدها) · `never` (لا رحلة).
* `notification_deliveries.skip_reason` — **لمَ لم يُرسل**: `opted_out` · `no_device` · `weekly_cap` — فيُقرأ الإحصاءُ لا يُخمَّن.

**لا جدولَ مالٍ يُمسّ.** والرجوعُ يحذف الأعمدةَ وقيودَها.

Revision ID: 0150
Revises: 0149
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0150"
down_revision = "0149"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_settings",
        sa.Column("weekly_marketing_cap", sa.SmallInteger(), nullable=False, server_default=sa.text("3")),
    )
    op.create_check_constraint(
        "notification_weekly_cap_range", "notification_settings", "weekly_marketing_cap BETWEEN 1 AND 14"
    )
    op.add_column("notification_campaigns", sa.Column("zone_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "notification_campaigns_zone_id_fkey", "notification_campaigns", "pricing_zones", ["zone_id"], ["id"], ondelete="SET NULL"
    )
    op.add_column("notification_campaigns", sa.Column("activity", sa.String(length=16), nullable=True))
    op.create_check_constraint(
        "campaign_activity_values", "notification_campaigns", "activity IS NULL OR activity IN ('active', 'dormant', 'never')"
    )
    op.add_column("notification_deliveries", sa.Column("skip_reason", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("notification_deliveries", "skip_reason")
    op.drop_constraint("campaign_activity_values", "notification_campaigns", type_="check")
    op.drop_column("notification_campaigns", "activity")
    op.drop_constraint("notification_campaigns_zone_id_fkey", "notification_campaigns", type_="foreignkey")
    op.drop_column("notification_campaigns", "zone_id")
    op.drop_constraint("notification_weekly_cap_range", "notification_settings", type_="check")
    op.drop_column("notification_settings", "weekly_marketing_cap")
