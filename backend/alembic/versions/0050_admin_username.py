"""اسمُ مستخدمٍ للمشرفين — والرقمُ يقبل NULL

Revision ID: 0050
Revises: 0049
Create Date: 2026-08-20

**ولمَ جدولٌ لا عمودٌ على `users`؟** اسمُ المستخدم صفةُ حسابٍ إداريّ لا صفةُ
إنسان (§22). وعمودٌ على `users` يتيح «اسمُ مستخدمٍ لراكب» **بالبناء** ثم يحتاج
حارساً يمنع ما أتاحه.

**وحُذف من هذه الترحيلة ما أقحمه المولِّد**: `otp_message_templates.id` كان
سيفقد `gen_random_uuid()` — فارقٌ قديمٌ بين النموذج والقاعدة لا علاقةَ له
بالمهمة، وإسقاطُه هنا يخلط تغييرين في ترحيلةٍ واحدةٍ ويكسر إدراجاً يعتمد عليه.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0050"
down_revision: str | None = "0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_credentials",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column(
            "is_break_glass", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_admin_credentials_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_credentials")),
        sa.UniqueConstraint("user_id", name=op.f("uq_admin_credentials_user_id")),
    )
    op.create_index(
        op.f("ix_admin_credentials_username"),
        "admin_credentials",
        ["username"],
        unique=True,
    )

    # **والفريدُ باقٍ على الرقم**: Postgres يسمح بعدّة `NULL` في فهرسٍ فريد،
    # فرقمٌ حقيقيٌّ ما زال لا يتكرر، ومشرفٌ بلا رقمٍ لا يزاحم أحداً
    op.alter_column("users", "phone", existing_type=sa.VARCHAR(length=20), nullable=True)


def downgrade() -> None:
    # **والعودةُ تفشل إن وُجد مشرفٌ بلا رقم** — وهذا صحيح: إعادةُ `NOT NULL`
    # على عمودٍ فيه `NULL` خسارةٌ صامتة لو مُلئ بقيمةٍ مخترَعة. فتُحذف
    # حساباتُ المشرفين أولاً أو يُملأ رقمُها بيدٍ قبل النزول.
    op.drop_index(op.f("ix_admin_credentials_username"), table_name="admin_credentials")
    op.drop_table("admin_credentials")
    op.alter_column(
        "users", "phone", existing_type=sa.VARCHAR(length=20), nullable=False
    )
