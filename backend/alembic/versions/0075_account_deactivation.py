"""إلغاءُ التفعيل يصير للحساب لا للكبتن وحدَه (٢٠٢٦-٠٩-٠٧).

**العلّةُ شرطُ متجر**: «If your app allows users to create an account, you must
also provide an option to request account deletion» — **ولا مسارَ للراكب**،
والمسارُ القائم مبنيٌّ على `drivers.id` فلا يسع من لا صفَّ له في `drivers`.

**ولا يُبنى ثانٍ بجانبه** (أمرُ المالك): الجدولُ نفسُه **يُوسَّع من الكبتن إلى
الحساب** — `driver_id` تصير `user_id`. فالسؤالُ واحد: «هذا الحسابُ يريد
الخروج»، **وطلبان لسؤالٍ واحدٍ يفترقان أوّلَ تعديل**.

**والتعبئةُ من `drivers.user_id` لا من فراغ**: كلُّ صفٍّ قائمٍ له مالكٌ
معروف، **فلا صفَّ يُفقد ولا طلبٌ يُيتَّم**.

## و`users.deactivated_at` عمودٌ جديدٌ **غيرُ `is_blocked`**

**والفرقُ مكتوبٌ في النموذج نفسِه**: `is_blocked` **قرارُ مشرفٍ في شخص**،
وهذا **قرارُ الشخص في نفسه**. **وخلطُهما يجعل من أغلق حسابَه يُقرأ محظوراً**
في كلِّ شاشةٍ وتقرير — وهي تهمةٌ لا حال.

**ولا يُمحى صفّ**: القاعدةُ تمنع حذفَ الدفتر وشواهد الرحلات، **والحذفُ هنا
تعطيلٌ وإخفاء** — وهو ما يقوله نصُّ التأكيد للمستخدم حرفاً.

**والرجوعُ يعيد الحالَ لا الصواب**: `downgrade` يعيد `driver_id` **ويُسقط
طلباتِ من ليسوا كباتن** — لأنها لا موضعَ لها في الشكل القديم، **ويقول ذلك في
تعليقه** بدل أن يفشل صامتاً.

Revision ID: 0075
Revises: 0074
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ١) حالُ الحساب — **مستقلّةٌ عن الحظر**
    op.add_column(
        "users",
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── ٢) موضوعُ الطلب يصير الحساب
    op.add_column(
        "deactivation_requests", sa.Column("user_id", UUID(as_uuid=True), nullable=True)
    )
    op.execute(
        """
        UPDATE deactivation_requests AS r
           SET user_id = d.user_id
          FROM drivers AS d
         WHERE d.id = r.driver_id
        """
    )
    # **ولا صفَّ بلا مالك**: لو بقي واحدٌ بلا `user_id` فالمفتاحُ الأجنبيُّ
    # سيوقف الترحيلةَ هنا — **وهو الصوابُ**: صفٌّ يتيمٌ يُسأل عنه ولا يُمرَّر
    op.alter_column("deactivation_requests", "user_id", nullable=False)
    op.create_foreign_key(
        "fk_deactivation_requests_user",
        "deactivation_requests",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_deactivation_requests_user_id", "deactivation_requests", ["user_id"]
    )

    # ── ٣) والفهرسُ الجزئيُّ ينتقل معه — **طلبٌ قائمٌ واحدٌ لكلِّ حساب**
    op.drop_index("uq_deactivation_pending", table_name="deactivation_requests")
    op.create_index(
        "uq_deactivation_pending",
        "deactivation_requests",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.drop_column("deactivation_requests", "driver_id")


def downgrade() -> None:
    op.add_column(
        "deactivation_requests",
        sa.Column("driver_id", UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        """
        UPDATE deactivation_requests AS r
           SET driver_id = d.id
          FROM drivers AS d
         WHERE d.user_id = r.user_id
        """
    )
    # **وطلباتُ من ليسوا كباتن تُحذف**: لا موضعَ لها في الشكل القديم،
    # **والحذفُ هنا نزولٌ لا محوُ دفتر** — لا مالَ في هذا الجدول ولا شاهدَ رحلة
    op.execute("DELETE FROM deactivation_requests WHERE driver_id IS NULL")
    op.alter_column("deactivation_requests", "driver_id", nullable=False)
    op.create_foreign_key(
        "deactivation_requests_driver_id_fkey",
        "deactivation_requests",
        "drivers",
        ["driver_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_deactivation_requests_driver_id", "deactivation_requests", ["driver_id"]
    )
    op.drop_index("uq_deactivation_pending", table_name="deactivation_requests")
    op.create_index(
        "uq_deactivation_pending",
        "deactivation_requests",
        ["driver_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.drop_index("ix_deactivation_requests_user_id", table_name="deactivation_requests")
    op.drop_constraint(
        "fk_deactivation_requests_user", "deactivation_requests", type_="foreignkey"
    )
    op.drop_column("deactivation_requests", "user_id")
    op.drop_column("users", "deactivated_at")
