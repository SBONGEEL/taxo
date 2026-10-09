"""أماكنُ الأردن المستوردة من OpenStreetMap (أمرُ المالك ٢٠٢٦-١٠-٠٩، SPEC §٧١-ح/٤) — **وسمُ المصدر ومرجعُه، وفئةُ المطار**.

**ما تضيفه** إلى `map_places`:
- `source` — `owner` (أضافه المالكُ بيده، افتراضاً لكلِّ صفٍّ قائم) أو `osm` (مستوردٌ يراجعه المالك).
- `osm_ref` — «node/123» · «way/456» · «relation/789»: **فريدٌ**، فالاستيرادُ الثاني لا يكرّر مكاناً، ومن يراجع يجد أصلَه.
- **فئةُ `airport`** في قيد الفئات — المطاراتُ من نصِّ المالك.

**ولا يمسّ جدولَ مال**، ولا قيمةً قائمة: كلُّ صفٍّ قائمٍ يصير `owner` بالافتراض — وهو كذلك.

Revision ID: 0108
Revises: 0107
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0108"
down_revision = "0107"
branch_labels = None
depends_on = None

#: **منسوخةٌ لا مستوردة** — والقيدُ الجديدُ هو قيدُ `0107` ومعه `airport`
_OLD = (
    "market", "shop", "mall", "mosque", "church", "hospital", "clinic", "school", "university", "hotel",
    "restaurant", "landmark", "government", "station", "neighborhood", "street", "other",
)
_CATEGORIES = (*_OLD, "airport")


def _check(values: tuple[str, ...]) -> str:
    return "category IN (" + ", ".join(f"'{value}'" for value in values) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_map_places_map_place_category_valid"), "map_places", type_="check")
    op.create_check_constraint(op.f("ck_map_places_map_place_category_valid"), "map_places", _check(_CATEGORIES))
    op.add_column("map_places", sa.Column("source", sa.String(8), nullable=False, server_default=sa.text("'owner'")))
    op.add_column("map_places", sa.Column("osm_ref", sa.String(32), nullable=True))
    op.create_check_constraint(op.f("ck_map_places_map_place_source_valid"), "map_places", "source IN ('owner', 'osm')")
    op.create_check_constraint(
        op.f("ck_map_places_map_place_osm_ref_with_source"), "map_places", "(source = 'osm') = (osm_ref IS NOT NULL)"
    )
    op.create_unique_constraint(op.f("uq_map_places_osm_ref"), "map_places", ["osm_ref"])


def downgrade() -> None:
    op.drop_constraint(op.f("uq_map_places_osm_ref"), "map_places", type_="unique")
    op.drop_constraint(op.f("ck_map_places_map_place_osm_ref_with_source"), "map_places", type_="check")
    op.drop_constraint(op.f("ck_map_places_map_place_source_valid"), "map_places", type_="check")
    op.drop_column("map_places", "osm_ref")
    op.drop_column("map_places", "source")
    # **صفٌّ بفئة المطار يُسقط النزولَ عمداً** — نزولٌ يمحو فئةً لم يعد يعرفها أسوأُ من نزولٍ يقف
    op.drop_constraint(op.f("ck_map_places_map_place_category_valid"), "map_places", type_="check")
    op.create_check_constraint(op.f("ck_map_places_map_place_category_valid"), "map_places", _check(_OLD))
