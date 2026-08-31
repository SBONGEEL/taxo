"""حملةُ تأكيد الأرقام — **تُبنى ولا تُطلق** (قرارُ المالك 2026-08-31).

جدولان وعمود:

* **`verification_campaigns`** — حملةُ سوقٍ واحد، **وحيّةٌ واحدةٌ لكلِّ سوق**
  (فهرسٌ جزئيّ): اثنتان تُرسلان تذكيرين لواحد وتحسبان مهلتين لحسابٍ واحد.
* **`verification_enforcements`** — سطرُ حسابٍ في حملة، **والتقدّمُ في صفٍّ لا
  في ذاكرة المهمّة**: مهمّةٌ تموت في منتصفها تُستأنف ولا تُعاد.
* **`users.verification_suspended_at`** — **حالٌ مستقلّةٌ عن `is_blocked`**:
  ذاك قرارُ مشرفٍ بسببٍ مكتوب، وهذه آليّةٌ تشفي نفسَها بتأكيد الرقم. وخلطُهما
  يجعل ضغطةَ تأكيدٍ **تفكّ حظراً قرّره مشرفٌ لسببٍ آخر**.

**والتعدادُ يُنشأ هنا فيُسقطه النزولُ** — وإلا فشل صعودٌ ثانٍ بـ«type already
exists»، وهو الفخُّ المكتوبُ في `CLAUDE.md` منذ `0002`.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None

_STATUS = postgresql.ENUM(
    "draft",
    "running",
    "paused",
    "done",
    "cancelled",
    name="verification_campaign_status",
)


def upgrade() -> None:
    _STATUS.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "users",
        sa.Column("verification_suspended_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "verification_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "country_code",
            postgresql.ENUM(name="country_code", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="verification_campaign_status", create_type=False),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "deadline_days", sa.Integer(), nullable=False, server_default=sa.text("14")
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "paused_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "started_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "uq_verification_campaign_live",
        "verification_campaigns",
        ["country_code"],
        unique=True,
        postgresql_where=sa.text("status IN ('draft', 'running', 'paused')"),
    )

    op.create_table(
        "verification_enforcements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("verification_campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "reminders_sent",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_reminder_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subscription_days_granted", sa.SmallInteger(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "campaign_id", "user_id", name="uq_enforcement_per_campaign_user"
        ),
    )
    op.create_index(
        "ix_verification_enforcements_campaign_id",
        "verification_enforcements",
        ["campaign_id"],
    )
    op.create_index(
        "ix_verification_enforcements_user_id",
        "verification_enforcements",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("verification_enforcements")
    op.drop_index(
        "uq_verification_campaign_live", table_name="verification_campaigns"
    )
    op.drop_table("verification_campaigns")
    op.drop_column("users", "verification_suspended_at")
    # **النوعُ يُسقطه من أنشأه** — وإلا فشل صعودٌ ثانٍ بـ«type already exists»
    _STATUS.drop(op.get_bind(), checkfirst=True)
