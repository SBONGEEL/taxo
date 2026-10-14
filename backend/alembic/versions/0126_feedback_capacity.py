"""ملاحظاتُ المستخدمين وإنذارُ السعة (SPEC §٧٦/٢ و٤) — جدولُ `app_feedback`، وعتبتا الإنذار على `broadcast_settings`.

**العتبتان تُبذران بقيمتي المالك**: ٢٥٠ كبتناً و٥٠٠ راكب — ٧٠٪ من السعة الآمنة المقيسة. **ولا مالَ هنا** — فبوّابةُ المال لا تعنيها.

**و`downgrade` يحذف الجدولَ والعمودين** — الملاحظاتُ سجلُّ تشغيلٍ لا قرارَ مالٍ فيه.

Revision ID: 0126
Revises: 0125
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0126"
down_revision = "0125"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("app", sa.String(8), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("app_version", sa.String(40), nullable=True),
        sa.Column("web_build", sa.String(80), nullable=True),
        sa.Column("platform", sa.String(16), nullable=True),
        sa.Column("route", sa.String(120), nullable=True),
        sa.Column("screenshot_path", sa.String(512), nullable=True),
        sa.Column("screenshot_type", sa.String(32), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "handled_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("app IN ('rider', 'driver')", name="app_feedback_app"),
        sa.CheckConstraint("char_length(message) BETWEEN 1 AND 2000", name="app_feedback_message_length"),
    )
    op.create_index("ix_app_feedback_user_id", "app_feedback", ["user_id"])

    op.add_column(
        "broadcast_settings",
        sa.Column("alert_captains", sa.Integer(), nullable=False, server_default="250"),
    )
    op.add_column(
        "broadcast_settings",
        sa.Column("alert_riders", sa.Integer(), nullable=False, server_default="500"),
    )
    op.create_check_constraint(
        "broadcast_alert_positive", "broadcast_settings", "alert_captains >= 1 AND alert_riders >= 1"
    )


def downgrade() -> None:
    # **قيدُ العمودين يسقط بسقوط أوّلهما** (Postgres يحذف كلَّ قيدٍ يمسّ عموداً محذوفاً) — فلا يُسمّى هنا، واسمُه بعد قاعدة التسمية
    # غيرُ الاسم المكتوب فوق
    op.drop_column("broadcast_settings", "alert_riders")
    op.drop_column("broadcast_settings", "alert_captains")
    op.drop_index("ix_app_feedback_user_id", table_name="app_feedback")
    op.drop_table("app_feedback")
