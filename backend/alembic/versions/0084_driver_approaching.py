"""«الكبتن يقترب» — علامةُ الإشعار على الرحلة، ومسافتُه لكلِّ سوق (SPEC §61-ي/١١، ٢٠٢٦-١٠-٠٤).

**عمودٌ فارغٌ على `rides`** (`approach_notified_at`): يُكتب مرّةً بتحديثٍ مشروطٍ ذرّيّ حين يُرسل الإشعار — فلا يتكرّر ولو تزامن موقعان.
**وعمودٌ على `notification_settings`** (`approach_notice_meters`) بافتراضٍ ٨٠٠ م وحدٍّ ٢٠٠–٣٠٠٠ — يُضبط من اللوحة.
**ولا جدولَ مالٍ بينهما، ولا يقرؤهما التوزيعُ ولا انتقالُ الحالات.**

**و`downgrade` يحذف العمودين** — وثمنُه: تُنسى علامةُ ما أُرسل ومسافةٌ ضبطها المشرف. لا مال.

Revision ID: 0084
Revises: 0083
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0084"
down_revision = "0083"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rides", sa.Column("approach_notified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "notification_settings",
        sa.Column("approach_notice_meters", sa.Integer(), nullable=False, server_default="800"),
    )
    op.create_check_constraint(
        "ck_notification_settings_approach_notice_meters",
        "notification_settings",
        "approach_notice_meters BETWEEN 200 AND 3000",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_notification_settings_approach_notice_meters", "notification_settings", type_="check"
    )
    op.drop_column("notification_settings", "approach_notice_meters")
    op.drop_column("rides", "approach_notified_at")
