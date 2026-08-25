"""تاريخُ انتهاء صلاحية مستندِ الكبتن (البند ب).

**تاريخٌ لا وقتٌ** (`Date` لا `DateTime`): صلاحيةُ رخصةٍ تنتهي **بيومٍ** مطبوعٍ
على البطاقة، لا بلحظةٍ في منطقةٍ زمنية. وتخزينُه لحظةً يجعل «انتهت اليوم؟»
سؤالاً جوابُه يختلف بين عمّان وطرابلس على الصفِّ نفسِه.

**ولاغٍ بحقّ** (`nullable=True`): صورةُ المركبة الأمامية لا تنتهي، والرخصةُ
تنتهي — **والفراغُ هنا يعني «لا تاريخَ لهذا النوع»** لا «تاريخٌ نُسي». وكلُّ
ما يقرؤه (البند ج) يتجاهل الفارغَ صراحةً، فلا يُعلَّق حسابٌ لأن حقلاً لم يُملأ.

**ومن يكتبه اثنان**: الكبتنُ عند الرفع، والمشرفُ عند المراجعة يقارنه بالصورة
ويصحّحه — و`expiry_source` يقول **أيُّهما كتبه آخراً**، فلا يُقرأ تصحيحُ
المشرف إقراراً من الكبتن ولا العكس.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0057"
down_revision: str | None = "0056"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "driver_documents",
        sa.Column("expires_on", sa.Date(), nullable=True),
    )
    op.add_column(
        "driver_documents",
        sa.Column("expiry_source", sa.String(16), nullable=True),
    )
    # **فهرسٌ على التاريخ وحدَه**: المسحُ الدوريُّ (البند ج) يسأل «أيُّ صفٍّ
    # ينتهي قبل يومٍ ما؟» على كلِّ الكباتن — لا على كبتنٍ بعينه. والصفوفُ
    # الفارغةُ خارجَه بشرطٍ جزئيّ، فلا يحمل الفهرسُ ما لا يُسأل عنه.
    op.create_index(
        "ix_driver_documents_expires_on",
        "driver_documents",
        ["expires_on"],
        postgresql_where=sa.text("expires_on IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_driver_documents_expires_on", table_name="driver_documents")
    op.drop_column("driver_documents", "expiry_source")
    op.drop_column("driver_documents", "expires_on")
