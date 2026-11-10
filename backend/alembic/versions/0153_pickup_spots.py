"""نقاطُ التقاطٍ ذكيّة (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١١، SPEC §٩٧/١١).

- **فئةُ `pickup`** في قيد فئات `map_places` — نقطةُ التقاطٍ يضعها المالك (بوّابة، زاوية، جانبُ الشارع الرئيسيّ).
- **`map_settings.pickup_suggest_enabled`** — مفتاحُ الاقتراح لكلِّ سوق، مشتعلٌ افتراضاً.

**لا جدولَ مالٍ يُمسّ.** والنقاطُ المتعلَّمةُ من الالتقاطات السابقة **مجمَّعةٌ في Redis** لا في جدول.

Revision ID: 0153
Revises: 0152
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0153"
down_revision = "0152"
branch_labels = None
depends_on = None

#: **منسوخةٌ لا مستوردة** — قيدُ `0108` ومعه `pickup`
_OLD = (
    "market", "shop", "mall", "mosque", "church", "hospital", "clinic", "school", "university", "hotel",
    "restaurant", "landmark", "government", "station", "neighborhood", "street", "other", "airport",
)
_CATEGORIES = (*_OLD, "pickup")


def _check(values: tuple[str, ...]) -> str:
    return "category IN (" + ", ".join(f"'{value}'" for value in values) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_map_places_map_place_category_valid"), "map_places", type_="check")
    op.create_check_constraint(op.f("ck_map_places_map_place_category_valid"), "map_places", _check(_CATEGORIES))
    op.add_column(
        "map_settings", sa.Column("pickup_suggest_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true"))
    )


def downgrade() -> None:
    op.drop_column("map_settings", "pickup_suggest_enabled")
    # **صفٌّ بفئة نقطة التقاط يُسقط النزولَ عمداً** — نزولٌ يمحو فئةً لم يعد يعرفها أسوأُ من نزولٍ يقف
    op.drop_constraint(op.f("ck_map_places_map_place_category_valid"), "map_places", type_="check")
    op.create_check_constraint(op.f("ck_map_places_map_place_category_valid"), "map_places", _check(_OLD))
