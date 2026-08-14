"""صورُ المركبة الستّ أنواعاً مسمّاة (البند ١١)

Revision ID: 0031
Revises: 0030
Create Date: 2026-08-14 18:40:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ستُّ قيمٍ على نوعٍ قائم — لا نوعَ جديد ولا جدول. و`IF NOT EXISTS` يجعلها
# قابلةً للإعادة بعد تراجعٍ جزئي (التراجعُ لا يُسقط النوع لأن جدولَه باقٍ).
#
# **ولا تُستعمل أيٌّ منها في هذه الترحيلة**: postgres يجيز إضافةَ القيمة داخل
# معاملة ويمنع استعمالَها فيها، ولا قيدَ هنا يحتاجها.
#
# **ولا تُحذف `vehicle_photo`**: التعدادُ لا تُنزع منه قيمة، وصفوفٌ قديمةٌ
# تحملها — فتبقى مهجورةً في الكود لا محذوفة، كي لا يصير صفٌّ في القاعدة بلا
# اسمٍ يقرؤه أحد.
NEW_TYPES = (
    "vehicle_front",
    "vehicle_back",
    "vehicle_side_right",
    "vehicle_side_left",
    "vehicle_interior",
    "vehicle_plate",
)


def upgrade() -> None:
    for value in NEW_TYPES:
        op.execute(f"ALTER TYPE document_type ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # قيمُ التعداد لا تُحذف في postgres، والنوعُ يُسقطه من أنشأه (`0002`).
    # ولا صفوفَ تُترك مكسورة: من رفع صورةً بنوعٍ جديد يبقى صفُّه صالحاً ما دام
    # النوعُ قائماً — والتراجعُ هنا لا شيء، وذلك أصدقُ من تظاهرٍ بعكسه.
    pass
