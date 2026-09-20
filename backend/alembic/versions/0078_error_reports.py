"""error reports: تقاريرُ الأعطال — مجموعةٌ وحدثٌ وجهاز

Revision ID: 0078
Revises: 0077
Create Date: 2026-09-20

**ثلاثةُ جداولَ لا واحد**، والعلّةُ كاملةً في `app/models/error_report.py`:
المجموعةُ تُجيب «ما هو»، والحدثُ «متى ولمن»، وجدولُ الأجهزة يجعل «كم إنساناً»
عدّاً مضبوطاً يُفرَز عليه بدل `COUNT(DISTINCT)` يمسح كلَّ حدث.

**و`client_app` موجودٌ سلفاً** (أنشأته `0071` لجدول الإصدارات) فلا يُنشأ
ثانيةً — `create_type=False` عليه وحدَه. والثلاثةُ الجديدةُ تُنشأ هنا
بـ`checkfirst=True`: **ترحيلةٌ تُعاد على قاعدةٍ نصفِ مهاجَرةٍ لا تسقط على نوعٍ
موجود**.

**ولا صفَّ تكتبه**: جداولُ جديدةٌ فارغةٌ تماماً، فلا ترحيلَ بيانات ولا قياسَ
صفوفٍ قائمة.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0078"
down_revision = "0077"
branch_labels = None
depends_on = None


_ERROR_KIND = postgresql.ENUM(
    "error", "rejection", "boundary", "user_report",
    name="error_kind",
    create_type=False,
)
_ERROR_STATUS = postgresql.ENUM(
    "open", "resolved", "ignored", name="error_status", create_type=False
)
_ERROR_PLATFORM = postgresql.ENUM(
    "android", "ios", "web", name="error_platform", create_type=False
)
#: **موجودٌ منذ `0071`** — يُشار إليه ولا يُنشأ
_CLIENT_APP = postgresql.ENUM(
    "rider", "driver", "panel", name="client_app", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (_ERROR_KIND, _ERROR_STATUS, _ERROR_PLATFORM):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "error_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("app", _CLIENT_APP, nullable=False),
        sa.Column("kind", _ERROR_KIND, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column(
            "status", _ERROR_STATUS, nullable=False, server_default="open"
        ),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("user_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("first_seen_release", sa.String(length=40), nullable=True),
        sa.Column("last_seen_release", sa.String(length=40), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_error_groups")),
    )
    op.create_index(
        op.f("ix_error_groups_fingerprint"),
        "error_groups",
        ["fingerprint"],
        unique=True,
    )
    op.create_index(op.f("ix_error_groups_app"), "error_groups", ["app"])
    op.create_index(op.f("ix_error_groups_status"), "error_groups", ["status"])
    op.create_index(
        op.f("ix_error_groups_user_count"), "error_groups", ["user_count"]
    )
    op.create_index(
        op.f("ix_error_groups_last_seen_at"), "error_groups", ["last_seen_at"]
    )

    op.create_table(
        "error_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("app", _CLIENT_APP, nullable=False),
        sa.Column("kind", _ERROR_KIND, nullable=False),
        sa.Column("platform", _ERROR_PLATFORM, nullable=False),
        sa.Column("os_version", sa.String(length=60), nullable=True),
        sa.Column("release", sa.String(length=40), nullable=True),
        sa.Column("channel", sa.String(length=20), nullable=True),
        sa.Column("route", sa.String(length=200), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("stack", sa.Text(), nullable=True),
        sa.Column("component_stack", sa.Text(), nullable=True),
        sa.Column("breadcrumbs", postgresql.JSONB(), nullable=True),
        sa.Column("device_hash", sa.String(length=64), nullable=False),
        sa.Column("online", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("repeat", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("request_id", sa.String(length=32), nullable=True),
        sa.Column(
            "user_reported", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["group_id"], ["error_groups.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_error_events")),
    )
    op.create_index(op.f("ix_error_events_group_id"), "error_events", ["group_id"])
    op.create_index(
        op.f("ix_error_events_device_hash"), "error_events", ["device_hash"]
    )
    op.create_index(op.f("ix_error_events_release"), "error_events", ["release"])
    op.create_index(
        op.f("ix_error_events_request_id"), "error_events", ["request_id"]
    )
    op.create_index(
        op.f("ix_error_events_received_at"), "error_events", ["received_at"]
    )
    op.create_index(
        op.f("ix_error_events_user_reported"), "error_events", ["user_reported"]
    )

    op.create_table(
        "error_group_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["group_id"], ["error_groups.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_error_group_devices")),
        sa.UniqueConstraint(
            "group_id", "device_hash", name="uq_error_group_devices_pair"
        ),
    )
    op.create_index(
        op.f("ix_error_group_devices_group_id"),
        "error_group_devices",
        ["group_id"],
    )


def downgrade() -> None:
    op.drop_table("error_group_devices")
    op.drop_table("error_events")
    op.drop_table("error_groups")
    bind = op.get_bind()
    for enum_type in (_ERROR_PLATFORM, _ERROR_STATUS, _ERROR_KIND):
        enum_type.drop(bind, checkfirst=True)
