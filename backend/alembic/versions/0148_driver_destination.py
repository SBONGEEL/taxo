"""«وجهتي» — حدّاها لكلِّ سوق (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٥).

عمودان في `dispatch_settings`: **كم مرّةً في اليوم** يضع الكبتنُ وجهةً (`0` ⇒ الميزةُ مطفأةٌ في سوقه)، **وكم في المئة انحرافاً** يُقبل
عن طريقه المباشر إليها. **والوجهةُ نفسُها في Redis بمهلة** لا في القاعدة: حالٌ عابرةٌ لساعات، وضياعُها يعيده إلى كلِّ الطلبات.

**لا جدولَ مالٍ يُمسّ.** والرجوعُ يحذف العمودين وقيدَيهما.

Revision ID: 0148
Revises: 0147
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0148"
down_revision = "0147"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dispatch_settings",
        sa.Column("destination_daily_uses", sa.Integer(), nullable=False, server_default=sa.text("2")),
    )
    op.add_column(
        "dispatch_settings",
        sa.Column("destination_detour_percent", sa.Integer(), nullable=False, server_default=sa.text("30")),
    )
    op.create_check_constraint(
        "dispatch_destination_uses_range", "dispatch_settings", "destination_daily_uses BETWEEN 0 AND 10"
    )
    op.create_check_constraint(
        "dispatch_destination_detour_range", "dispatch_settings", "destination_detour_percent BETWEEN 5 AND 100"
    )


def downgrade() -> None:
    op.drop_constraint("dispatch_destination_detour_range", "dispatch_settings", type_="check")
    op.drop_constraint("dispatch_destination_uses_range", "dispatch_settings", type_="check")
    op.drop_column("dispatch_settings", "destination_detour_percent")
    op.drop_column("dispatch_settings", "destination_daily_uses")
