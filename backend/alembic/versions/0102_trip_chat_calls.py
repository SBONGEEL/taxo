"""محادثةُ الرحلة ومكالمتُها (SPEC §٦٦، `design/APPROVALS-DATA.md` §١) — ثلاثةُ جداولَ جديدة، وصلاحيتان، وثلاثةُ أعمدةٍ لكلِّ سوق.

**ما تضيفه**:

- `ride_messages` — نصٌّ حتى ٣٠٠ حرف، ومن أرسله وبأيِّ صفة، ومتى، ومتى قُرئ. **ولا صورَ ولا صوتَ ولا مواقع**: لا عمودَ لها أصلاً.
- `ride_message_reports` — البلاغُ: الرسالةُ ومن أبلغ والسببُ وسطرٌ اختياريّ، وحالُه ومن عالجه ومتى. **بلاغٌ واحدٌ لكلِّ مُبلِّغٍ على رسالة**.
- `ride_calls` — سجلُّ المكالمة: من اتصل بمن، ومتى بدأت ورُدَّ عليها وانتهت، ومدّتُها وسببُ انتهائها، **وهل سُجّلت** — **ولا صوت**:
  `recording_path` يبقى فارغاً ما دام التسجيلُ مطفأً في السوق (وهو مطفأٌ افتراضاً). **ومكالمةٌ حيّةٌ واحدةٌ لكلِّ رحلة** بفهرسٍ فريدٍ جزئيّ.
- **قيمتان في `admin_permission`** — `trip_chats.read` و`call_recordings.listen` — **ولا تُعطيان لأحدٍ افتراضاً** (`services/permissions.py`).
- **ثلاثةُ أعمدةٍ على `service_settings`** (بيتُ إعدادات الخدمات الجديدة لكلِّ سوق): مدّةُ الاحتفاظ بالمحادثة وسجلِّ المكالمات (٩٠ يوماً)،
  ومفتاحُ التسجيل (**مطفأ**)، ومدّةُ الاحتفاظ بالتسجيل (٣٠ يوماً).

**ولا جدولَ قائمٌ يُكتب صفُّه**: الجداولُ الثلاثةُ جديدةٌ فارغة، والأعمدةُ الثلاثةُ بافتراضٍ يصف كلَّ سوقٍ قائمٍ كما هو — **ولا مالَ في شيءٍ منها**.

**و`downgrade` مقيسٌ لا مقروء** (`tests/test_migrations.py`): يُسقط الجداولَ وأنواعَها والأعمدةَ، **ويعيد بناءَ `admin_permission`
بأعضائه الاثني عشر** كما فعلت `0079` — PostgreSQL لا تحذف عضواً من نوع، **وحذفُ منحةِ صلاحيةٍ ليس حذفَ مال**.

**ورقمُها `0102` فوق `0101`** (حسابا التجربة، فرعٌ شقيقٌ دُمج قبلها) — وُجّه `down_revision` إليها عند الدمج ٢٠٢٦-١٠-٠٨.

Revision ID: 0102
Revises: 0100
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0102"
down_revision = "0101"
branch_labels = None
depends_on = None

#: **جانبُ الرحلة** — النوعُ القائمُ نفسُه (`rating_rater_type`: راكبٌ أو كبتن)، فلا يُخترع ثانٍ بالقيمتين نفسيهما
SIDE = postgresql.ENUM(name="rating_rater_type", create_type=False)

REPORT_REASON = postgresql.ENUM(
    "abuse", "harassment", "fraud", "other", name="ride_message_report_reason", create_type=False
)
REPORT_STATUS = postgresql.ENUM("open", "handled", name="ride_message_report_status", create_type=False)
CALL_STATUS = postgresql.ENUM("ringing", "active", "ended", name="ride_call_status", create_type=False)
CALL_END_REASON = postgresql.ENUM(
    "completed", "declined", "no_answer", "failed", "ride_ended", "cancelled",
    name="ride_call_end_reason", create_type=False,
)

#: **العضوان الجديدان وحدَهما بأسمائهما** — وأعضاءُ النوع قبلهما تُقرأ من القاعدة في النزول لا تُنسخ هنا: قائمةٌ منسوخةٌ تفترق
#: عن النوع أوّلَ عضوٍ يُضاف بعد هذه الترحيلة
_NEW_PERMISSIONS = ("trip_chats.read", "call_recordings.listen")


def upgrade() -> None:
    for value in _NEW_PERMISSIONS:
        # `IF NOT EXISTS` كي تُعاد على قاعدةٍ نصفِ مهاجَرةٍ بلا سقوط
        op.execute(f"ALTER TYPE admin_permission ADD VALUE IF NOT EXISTS '{value}'")

    bind = op.get_bind()
    for enum in (REPORT_REASON, REPORT_STATUS, CALL_STATUS, CALL_END_REASON):
        enum.create(bind, checkfirst=True)

    # ── الرسائل
    op.create_table(
        "ride_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ride_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rides.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "sender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("sender_role", SIDE, nullable=False),
        sa.Column("body", sa.String(length=300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("char_length(body) BETWEEN 1 AND 300", name="ride_message_body_length"),
    )
    op.create_index("ix_ride_messages_ride_id_created_at", "ride_messages", ["ride_id", "created_at"])
    op.create_index(op.f("ix_ride_messages_sender_id"), "ride_messages", ["sender_id"])

    # ── البلاغات
    op.create_table(
        "ride_message_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ride_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reporter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("reason", REPORT_REASON, nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("status", REPORT_STATUS, server_default="open", nullable=False),
        sa.Column(
            "handled_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handled_note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(status = 'handled') = (handled_at IS NOT NULL)", name="ride_message_report_handled_complete"
        ),
        sa.UniqueConstraint("message_id", "reporter_id", name="uq_ride_message_reports_message_id_reporter_id"),
    )
    op.create_index(op.f("ix_ride_message_reports_status"), "ride_message_reports", ["status"])

    # ── المكالمات
    op.create_table(
        "ride_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ride_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rides.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "caller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "callee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("caller_role", SIDE, nullable=False),
        sa.Column("status", CALL_STATUS, server_default="ringing", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("end_reason", CALL_END_REASON, nullable=True),
        sa.Column("recorded", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("caller_notice_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("callee_notice_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recording_path", sa.String(length=255), nullable=True),
        sa.Column("recording_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(status = 'ended') = (ended_at IS NOT NULL AND end_reason IS NOT NULL)", name="ride_call_ended_complete"
        ),
        sa.CheckConstraint(
            "status = 'ringing' OR answered_at IS NOT NULL OR status = 'ended'", name="ride_call_active_answered"
        ),
        sa.CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0", name="ride_call_duration_valid"),
        sa.CheckConstraint("recording_path IS NULL OR recorded", name="ride_call_recording_only_when_recorded"),
        sa.CheckConstraint(
            "caller_id IS NULL OR callee_id IS NULL OR caller_id <> callee_id", name="ride_call_two_parties"
        ),
    )
    op.create_index("ix_ride_calls_ride_id_started_at", "ride_calls", ["ride_id", "started_at"])
    op.create_index(
        "uq_ride_calls_live_ride",
        "ride_calls",
        ["ride_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('ringing', 'active')"),
    )

    # ── إعداداتُ السوق
    op.add_column(
        "service_settings",
        sa.Column("chat_retention_days", sa.SmallInteger(), server_default=sa.text("90"), nullable=False),
    )
    op.add_column(
        "service_settings",
        sa.Column("call_recording_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "service_settings",
        sa.Column("call_recording_retention_days", sa.SmallInteger(), server_default=sa.text("30"), nullable=False),
    )
    op.create_check_constraint(
        "service_settings_trip_comms_valid",
        "service_settings",
        "chat_retention_days BETWEEN 1 AND 3650 AND call_recording_retention_days BETWEEN 1 AND 3650",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_service_settings_service_settings_trip_comms_valid"), "service_settings", type_="check")
    op.drop_column("service_settings", "call_recording_retention_days")
    op.drop_column("service_settings", "call_recording_enabled")
    op.drop_column("service_settings", "chat_retention_days")

    op.drop_index("uq_ride_calls_live_ride", table_name="ride_calls")
    op.drop_index("ix_ride_calls_ride_id_started_at", table_name="ride_calls")
    op.drop_table("ride_calls")
    op.drop_index(op.f("ix_ride_message_reports_status"), table_name="ride_message_reports")
    op.drop_table("ride_message_reports")
    op.drop_index(op.f("ix_ride_messages_sender_id"), table_name="ride_messages")
    op.drop_index("ix_ride_messages_ride_id_created_at", table_name="ride_messages")
    op.drop_table("ride_messages")

    bind = op.get_bind()
    for enum in (CALL_END_REASON, CALL_STATUS, REPORT_STATUS, REPORT_REASON):
        enum.drop(bind, checkfirst=True)

    # **والصلاحيتان تُنزعان بإعادة بناء النوع** — كـ`0079` حرفاً: منحُهما يُحذف أولاً، ثمّ يُحوَّل العمود. **والباقي يُقرأ بترتيبه
    # من النوع نفسِه** لا من قائمةٍ منسوخة
    listed = ", ".join(f"'{value}'" for value in _NEW_PERMISSIONS)
    # **والنزولُ لا يوسّع أحداً** (قِيس ٢٠٢٦-١٠-٠٨): مشرفٌ كلُّ صفوفه من الصلاحيتين يصير بالحذف **بلا صفّ** — والغيابُ «افتراضُ
    # الدور» لا «ممنوع» (`models/admin_permission.py`)، **وافتراضُ `admin` قبل هذه الترحيلة الكلّ**. فمن مُنح قراءةَ المحادثات
    # وحدَها كان سيعود مشرفاً كاملاً بنزول ترحيلة. **فيُكتب له `read.only` قبل الحذف** — أضيقُ ما في التعداد القديم، **وصفٌّ
    # يحكم** فلا يُقرأ افتراضُه. ومن له صفٌّ آخرُ معهما لا يُمسّ: صفوفُه الباقيةُ تحكم كما كانت
    op.execute(
        "INSERT INTO admin_permissions (id, user_id, permission, granted_at) "
        "SELECT gen_random_uuid(), user_id, 'read.only'::admin_permission, now() FROM admin_permissions "
        f"GROUP BY user_id HAVING bool_and(permission::text IN ({listed}))"
    )
    op.execute(f"DELETE FROM admin_permissions WHERE permission::text IN ({listed})")
    members = bind.execute(sa.text("SELECT unnest(enum_range(NULL::admin_permission))::text")).scalars().all()
    values = ", ".join(f"'{value}'" for value in members if value not in _NEW_PERMISSIONS)
    op.execute(sa.text(f"CREATE TYPE admin_permission_old AS ENUM ({values})"))
    op.execute(
        "ALTER TABLE admin_permissions "
        "ALTER COLUMN permission TYPE admin_permission_old "
        "USING permission::text::admin_permission_old"
    )
    op.execute("DROP TYPE admin_permission")
    op.execute("ALTER TYPE admin_permission_old RENAME TO admin_permission")
