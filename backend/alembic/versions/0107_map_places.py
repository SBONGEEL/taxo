"""أماكنُ المالك على الخريطة (SPEC §٧١-د/١٤، أمرُ المالك ٢٠٢٦-١٠-٠٩) — جدولٌ جديدٌ فارغ.

**ما تضيفه**: `map_places` — اسمٌ عربيٌّ (إلزاميّ) وإنجليزيّ، وفئةٌ بقيد، وموقعٌ رقمين، ودولة، وإخفاء. **ولا يمسّ جدولاً قائماً**:
`facilities` (رسمُ المطار) كما هو، والمطاراتُ تُقرأ منه مع الأماكن ولا تُنسخ هنا. **والمفتاحُ `map_places_enabled` لا يُكتب هنا**:
صفُّه يُكتب على الإنتاج بعد الرفع، **وليبيا لا تُمسّ**.

Revision ID: 0107
Revises: 0106
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0107"
down_revision = "0106"
branch_labels = None
depends_on = None

#: **منسوخةٌ لا مستوردة** — الترحيلةُ تبقى كما كُتبت ولو تغيّرت الفئاتُ في النموذج بعدها (وتغييرُها ترحيلةُ قيدٍ جديدة)
_CATEGORIES = (
    "market", "shop", "mall", "mosque", "church", "hospital", "clinic", "school", "university", "hotel",
    "restaurant", "landmark", "government", "station", "neighborhood", "street", "other",
)


def upgrade() -> None:
    op.create_table(
        "map_places",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "country_code",
            postgresql.ENUM("LY", "JO", name="country_code", create_type=False),
            nullable=False,
        ),
        sa.Column("name_ar", sa.String(80), nullable=False),
        sa.Column("name_en", sa.String(80), nullable=True),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "category IN (" + ", ".join(f"'{value}'" for value in _CATEGORIES) + ")",
            name=op.f("ck_map_places_map_place_category_valid"),
        ),
        sa.CheckConstraint(
            "lat BETWEEN -90 AND 90 AND lng BETWEEN -180 AND 180", name=op.f("ck_map_places_map_place_point_valid")
        ),
        sa.CheckConstraint("char_length(btrim(name_ar)) >= 2", name=op.f("ck_map_places_map_place_name_ar_present")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_map_places")),
    )
    op.create_index(op.f("ix_map_places_country_code"), "map_places", ["country_code"])


def downgrade() -> None:
    op.drop_index(op.f("ix_map_places_country_code"), table_name="map_places")
    op.drop_table("map_places")
