"""**تقريبُ الأجرة منفصلاً عن التقريب العامّ** (أمرُ المالك ٢٠٢٦-١١-١٩، `design/OWNER-2026-11-19-FARE-ROUNDING.md`).

ستّةُ أعمدةٍ على `payment_settings` — **إعداداتٌ لا مالٌ**: لا صفَّ في جدول مالٍ يتغيّر، ولا رحلةَ قديمةٌ ولا مبلغُ دفتر.
**وتُبذر من الحال القائمة صفّاً صفّاً** — الخطوةُ هي `rounding_unit` إن كان التقريبُ مشتعلاً (وإلّا NULL = دقيق)، والاتجاهُ هو هو،
والمفاتيحُ الأربعةُ هي `rounding_enabled` — **فلا تتغيّر أجرةٌ واحدةٌ في أيِّ دولةٍ بهذه الترحيلة**؛ وقيمُ الأردن الجديدة كتابةُ إعدادٍ
مدقَّقةٌ بعد الرفع لا هنا.

**والرجوعُ** يحذف الأعمدةَ الستّة — والسياسةُ العامّةُ لم تُمسّ فتعود الأجرةُ تُقرَّب بها كما كانت.

Revision ID: 0176
Revises: 0175
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0176"
down_revision = "0175"
branch_labels = None
depends_on = None

_SURFACES = ("fare_on_estimate", "fare_on_final", "fare_on_negotiation", "fare_on_cancellation")


def upgrade() -> None:
    op.add_column("payment_settings", sa.Column("fare_step", sa.Numeric(12, 3), nullable=True))
    op.add_column(
        "payment_settings",
        sa.Column("fare_mode", sa.String(8), nullable=False, server_default=sa.text("'nearest'")),
    )
    for name in _SURFACES:
        op.add_column(
            "payment_settings", sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.text("false"))
        )
    op.execute(
        "UPDATE payment_settings SET "
        "fare_step = CASE WHEN rounding_enabled THEN rounding_unit ELSE NULL END, "
        "fare_mode = rounding_mode, "
        + ", ".join(f"{name} = rounding_enabled" for name in _SURFACES)
    )
    op.create_check_constraint(
        "payment_fare_rounding_valid",
        "payment_settings",
        "(fare_step IS NULL OR fare_step > 0) AND fare_mode IN ('nearest', 'up', 'down')",
    )


def downgrade() -> None:
    op.drop_constraint("payment_fare_rounding_valid", "payment_settings", type_="check")
    for name in reversed(_SURFACES):
        op.drop_column("payment_settings", name)
    op.drop_column("payment_settings", "fare_mode")
    op.drop_column("payment_settings", "fare_step")
