"""قناةُ صفحة فيسبوك «Taxo» (SPEC §٩٤/٢، أمرُ المالك ٢٠٢٦-١١-٠٤).

Revision ID: 0142
Revises: 0141
Create Date: 2026-11-04

**ما تضيفه**:
- `facebook_posts` — منشوراتُ الصفحة بلغاتها وحالها وموعدها ومعرّفها على فيسبوك وأرقامِ تفاعلها.
- `facebook_post_requests` — «اطلب منشوراتٍ جديدة».
- `admin_permission` ← `facebook.manage` (حسّاسة: لا تُعطى افتراضاً، والمالكُ يملكها بدوره).
- `provider_key` ← `facebook_page` (عقدُ الصفحة المعمّى).

**ولا جدولَ مالٍ يُمسّ**: جدولان جديدان فارغان، مفتاحاهما الأجنبيّان إلى `users` وحدَه. **ولا صفَّ يُكتب** — العقدُ يُدخَل من صفحة
العقود، والمنشوراتُ من القناة. والنزولُ يحذف الجدولين؛ وقيمتا التعداد تبقيان (لا تُحذف قيمةُ تعدادٍ في PostgreSQL)، و`IF NOT EXISTS`
يجعل الصعودَ بعده نظيفاً.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0142"
down_revision = "0141"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE admin_permission ADD VALUE IF NOT EXISTS 'facebook.manage'")
    op.execute("ALTER TYPE provider_key ADD VALUE IF NOT EXISTS 'facebook_page'")

    op.create_table(
        "facebook_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False, server_default=""),
        sa.Column("lang", sa.String(4), nullable=False, server_default="ar"),
        sa.Column("kind", sa.String(12), nullable=False, server_default="photo"),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending_review"),
        sa.Column("group_key", sa.String(80), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("media_paths", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("preview_url", sa.Text(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fb_post_id", sa.String(80), nullable=True),
        sa.Column("permalink", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("stats", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("stats_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending_review', 'changes_requested', 'approved', 'scheduled', 'published', 'rejected', 'failed')",
            name="ck_facebook_posts_status",
        ),
        sa.CheckConstraint("kind IN ('photo', 'carousel', 'video')", name="ck_facebook_posts_kind"),
        sa.CheckConstraint("lang IN ('ar', 'fr', 'dz', 'en')", name="ck_facebook_posts_lang"),
        sa.UniqueConstraint("fb_post_id", name="uq_facebook_posts_fb_post_id"),
    )
    op.create_index("ix_facebook_posts_status", "facebook_posts", ["status"])
    op.create_index("ix_facebook_posts_group_key", "facebook_posts", ["group_key"])
    op.create_index("ix_facebook_posts_scheduled_at", "facebook_posts", ["scheduled_at"])

    op.create_table(
        "facebook_post_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(8), nullable=False, server_default="open"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('open', 'done')", name="ck_facebook_post_requests_status"),
    )


def downgrade() -> None:
    op.drop_table("facebook_post_requests")
    op.drop_index("ix_facebook_posts_scheduled_at", table_name="facebook_posts")
    op.drop_index("ix_facebook_posts_group_key", table_name="facebook_posts")
    op.drop_index("ix_facebook_posts_status", table_name="facebook_posts")
    op.drop_table("facebook_posts")
