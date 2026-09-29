"""حذفُ الحساب بعد مهلة — أعمدةُ الطلب والتأجيل والتجهيل على `users` (SPEC §59).

**ولمَ على `users` لا جدولٌ مستقلّ**: الطلبُ حالُ الحساب نفسِه — يقرؤها كلُّ
بابٍ يقرّر أيسمح (طلبُ رحلة · تسجيلُ جهاز · تسجيلُ رقم) **في الصفِّ الذي بيده
أصلاً**. وجدولٌ ثانٍ يجعل «أهو مجدولٌ للحذف؟» سؤالاً بنداءٍ ثانٍ في كلِّ باب.

**ولا بياناتَ تُرحَّل**: كلُّها `NULL` لكلِّ حسابٍ قائم — لا أحدَ طلب الحذفَ
بهذا الباب قبل وجوده. **و`deactivation_requests` يبقى كما هو** لطلبات الإغلاق
القديمة.

Revision ID: 0081
Revises: 0080
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0081"
down_revision = "0080"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("deletion_requested_at", "deletion_due_at"):
        op.add_column(
            "users", sa.Column(name, sa.DateTime(timezone=True), nullable=True)
        )
    # **المبلغُ الذي أقرّ بضياعه كما كتبه** — يُقارَن بالرصيد تحت القفل عند
    # التأكيد وفي اليوم الثلاثين. وليس قيداً: الدفترُ لا يُمسّ.
    op.add_column(
        "users",
        sa.Column("deletion_forfeit_amount", sa.Numeric(12, 3), nullable=True),
    )
    # **حالُ الكبتن قبل الطلب** — تعود إليها عند الاستعادة لا إلى افتراض
    op.add_column(
        "users",
        sa.Column("deletion_driver_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("deletion_deferred_reason", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("deletion_deferred_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )
    # **المهمّةُ تسأل «من حلّ موعدُه؟» كلَّ ساعة** — والحسابُ الذي لم يطلب شيئاً
    # لا يدخل الفهرسَ أصلاً
    op.create_index(
        "ix_users_deletion_due_at",
        "users",
        ["deletion_due_at"],
        postgresql_where=sa.text("deletion_due_at IS NOT NULL AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_users_deletion_due_at", table_name="users")
    for name in (
        "deleted_at",
        "deletion_deferred_at",
        "deletion_deferred_reason",
        "deletion_driver_status",
        "deletion_forfeit_amount",
        "deletion_due_at",
        "deletion_requested_at",
    ):
        op.drop_column("users", name)
