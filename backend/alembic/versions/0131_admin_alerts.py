"""إشعاراتُ المالك بنشاط المستخدمين (SPEC §٨١، أمرُ المالك ٢٠٢٦-١٠-٢٠).

ثلاثةُ جداولَ جديدةٍ وحدَها — `admin_alerts` و`admin_alert_reads` و`admin_alert_settings`. **ولا مساسَ بجدولٍ قائم ولا بجدول مال**:
الأحداثُ تُلتقط في الشيفرة بعد الالتزام (`services/alert_capture.py`)، **لا بمُطلقٍ في القاعدة على جداول المال**. و`downgrade` يحذف الثلاثة
ومعها إشعاراتُ اللوحة وحدَها.

Revision ID: 0131
Revises: 0130
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0131"
down_revision = "0130"
branch_labels = None
depends_on = None

_COUNTRY = postgresql.ENUM(name="country_code", create_type=False)
_CURRENCY = postgresql.ENUM(name="currency", create_type=False)
_NEW_PERMISSION = "activity_alerts.receive"


def upgrade() -> None:
    # **صلاحيةُ الاستلام** — لا تُعطى لأحدٍ افتراضاً (`permissions.SENSITIVE`)، والمالكُ يملكها بدوره؛ فلا صفَّ يُكتب هنا
    op.execute(f"ALTER TYPE admin_permission ADD VALUE IF NOT EXISTS '{_NEW_PERMISSION}'")
    op.create_table(
        "admin_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(48), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("tone", sa.String(16), nullable=False),
        sa.Column("country_code", _COUNTRY, nullable=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("amount", sa.Numeric(12, 3), nullable=True),
        sa.Column("currency", _CURRENCY, nullable=True),
        sa.Column("record_type", sa.String(24), nullable=True),
        sa.Column("record_id", sa.String(64), nullable=True),
        sa.Column("data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("group_key", sa.String(80), nullable=False),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_admin_alerts_kind", "admin_alerts", ["kind"])
    op.create_index("ix_admin_alerts_category", "admin_alerts", ["category"])
    op.create_index("ix_admin_alerts_country_code", "admin_alerts", ["country_code"])
    op.create_index("ix_admin_alerts_created_at", "admin_alerts", ["created_at"])
    op.create_index("ix_admin_alerts_group", "admin_alerts", ["group_key", "last_event_at"])

    op.create_table(
        "admin_alert_reads",
        sa.Column(
            "alert_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("admin_alerts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_admin_alert_reads_user_id", "admin_alert_reads", ["user_id"])

    op.create_table(
        "admin_alert_settings",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("kinds", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("sounds", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("admin_alert_settings")
    op.drop_index("ix_admin_alert_reads_user_id", table_name="admin_alert_reads")
    op.drop_table("admin_alert_reads")
    op.drop_index("ix_admin_alerts_group", table_name="admin_alerts")
    op.drop_index("ix_admin_alerts_created_at", table_name="admin_alerts")
    op.drop_index("ix_admin_alerts_country_code", table_name="admin_alerts")
    op.drop_index("ix_admin_alerts_category", table_name="admin_alerts")
    op.drop_index("ix_admin_alerts_kind", table_name="admin_alerts")
    op.drop_table("admin_alerts")

    # **والنزولُ لا يوسّع أحداً** — من كانت صلاحيتُه هذه وحدَها يُكتب له `read.only` قبل الحذف (قاعدةُ `0103` و`0118` حرفاً)
    bind = op.get_bind()
    op.execute(
        "INSERT INTO admin_permissions (id, user_id, permission, granted_at) "
        "SELECT gen_random_uuid(), user_id, 'read.only'::admin_permission, now() FROM admin_permissions "
        f"GROUP BY user_id HAVING bool_and(permission::text = '{_NEW_PERMISSION}')"
    )
    op.execute(f"DELETE FROM admin_permissions WHERE permission::text = '{_NEW_PERMISSION}'")
    members = bind.execute(sa.text("SELECT unnest(enum_range(NULL::admin_permission))::text")).scalars().all()
    values = ", ".join(f"'{value}'" for value in members if value != _NEW_PERMISSION)
    op.execute(sa.text(f"CREATE TYPE admin_permission_old AS ENUM ({values})"))
    op.execute(
        "ALTER TABLE admin_permissions "
        "ALTER COLUMN permission TYPE admin_permission_old "
        "USING permission::text::admin_permission_old"
    )
    op.execute("DROP TYPE admin_permission")
    op.execute("ALTER TYPE admin_permission_old RENAME TO admin_permission")
