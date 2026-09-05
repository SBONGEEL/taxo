"""site settings — إعداداتُ الصفحة التعريفية (§49)

**صفٌّ واحدٌ لا صفٌّ لكلِّ سوق**، ويمنعُ الثانيَ عمودُ `singleton`: فريدٌ
وقيمتُه محجوزةٌ بـ`CHECK`. **وجدولُ إعداداتٍ بصفّين يجعل «أيُّهما يحكم؟»
سؤالاً لا جواب له.**

**ولا صفَّ يُبذر هنا**: `services/site.public_payload` يجيب بالقيم الأولى حين
لا صفّ، و`get_or_create` يكتبه عند أوّل فتحٍ للشاشة. **وبذرٌ في ترحيلةٍ يجعل
للقيم الأولى بيتين** — وهما يفترقان أوّلَ تعديل.

**ولا يمسّ هذا الملفُّ جدولاً غيرَ جدوله**: التوليدُ الآليُّ اقترح تعديلاً على
`otp_message_templates.id` (فرقُ `server_default` يراه المقارِنُ ولا يراه
النموذج) **فنُزع** — ترحيلةٌ تحمل تغييراً لا يخصّها تجعل الرجوعَ عنها يمسّ ما
لم يُقصد.

Revision ID: 0072
Revises: 0071
Create Date: 2026-09-05 05:39:12.202609
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0072"
down_revision: str | None = "0071"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_settings",
        sa.Column("singleton", sa.Boolean(), nullable=False),
        sa.Column("hero_title", sa.String(length=120), nullable=False),
        sa.Column("hero_subtitle", sa.String(length=240), nullable=False),
        sa.Column("hero_note", sa.String(length=80), nullable=False),
        sa.Column("announce_enabled", sa.Boolean(), nullable=False),
        sa.Column("announce_text", sa.String(length=200), nullable=False),
        sa.Column("announce_url", sa.String(length=300), nullable=False),
        sa.Column("support_email", sa.String(length=120), nullable=False),
        sa.Column("privacy_email", sa.String(length=120), nullable=False),
        sa.Column("social_facebook", sa.String(length=300), nullable=False),
        sa.Column("social_instagram", sa.String(length=300), nullable=False),
        sa.Column("social_tiktok", sa.String(length=300), nullable=False),
        sa.Column("social_x", sa.String(length=300), nullable=False),
        sa.Column("social_whatsapp", sa.String(length=300), nullable=False),
        sa.Column(
            "hidden_sections",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "hidden_cards",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "faq",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("distribution_mode", sa.String(length=8), nullable=False),
        sa.Column("play_url_rider", sa.String(length=300), nullable=False),
        sa.Column("play_url_driver", sa.String(length=300), nullable=False),
        sa.Column("ios_url", sa.String(length=300), nullable=False),
        sa.Column("apk_page_enabled", sa.Boolean(), nullable=False),
        sa.Column("policies_public", sa.Boolean(), nullable=False),
        sa.Column("seo_description", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "singleton = TRUE", name=op.f("ck_site_settings_site_settings_singleton")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_site_settings")),
        sa.UniqueConstraint("singleton", name=op.f("uq_site_settings_singleton")),
    )


def downgrade() -> None:
    op.drop_table("site_settings")
