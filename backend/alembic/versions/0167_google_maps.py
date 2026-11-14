"""google maps: مزوّدُ الخرائط لكلِّ دولةٍ وميزة، والأسماءُ البديلة، والأماكنُ المتعلَّمة (قرارُ المالك ٢٠٢٦-١١-١٥)

Revision ID: 0167
Revises: 0166
Create Date: 2026-11-15

**ولا جدولَ مالٍ بينها**:
- قيمةُ `google_maps` في `provider_key` — تُختم قبل أيِّ استعمال.
- **ثلاثةُ مفاتيحَ لكلِّ دولةٍ مطفأة** (`google_maps_display` · `google_places_search` · `google_routes`) — **مطفأةً تُرفع**: Mapbox كما كان
  حرفاً حتى يُدخل العقدُ ويجتاز اختبارُ الستّين مكاناً، ثمّ تُشعل من «مزوّد الخرائط».
- `map_places.aliases` — أسماءٌ بديلةٌ للبحث، فارغةٌ افتراضاً.
- `learned_places` — جدولٌ جديد: نصُّ الراكب وموقعُ نهاية رحلةٍ مكتملة وعددُ الرحلات.

**والنزولُ** يُطفئ المفاتيح وينزع الجدولَ الجديد والعمودَ الجديد (لا مالَ فيهما)، والقيمةُ في التعداد تبقى.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0167"
down_revision = "0166"
branch_labels = None
depends_on = None

FLAGS = ("google_maps_display", "google_places_search", "google_routes")
COUNTRIES = ("JO",)  # **والجزائرُ وليبيا يُنشئ صفَّهما زرُّ اللوحة** (`test_0111`: سوقٌ يولد بمفتاح الظهور وحدَه)


def upgrade() -> None:
    op.execute("ALTER TYPE provider_key ADD VALUE IF NOT EXISTS 'google_maps'")
    op.execute("COMMIT")
    op.add_column(
        "map_places",
        sa.Column("aliases", postgresql.ARRAY(sa.String(80)), nullable=False, server_default=sa.text("'{}'::varchar[]")),
    )
    op.create_table(
        "learned_places",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("country_code", postgresql.ENUM(name="country_code", create_type=False), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("label_norm", sa.String(80), nullable=False),
        sa.Column("cell", sa.String(24), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("trips", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("lat BETWEEN -90 AND 90 AND lng BETWEEN -180 AND 180", name="learned_place_point_valid"),
        sa.CheckConstraint("char_length(btrim(label)) >= 2", name="learned_place_label_present"),
        sa.UniqueConstraint("country_code", "label_norm", "cell", name="uq_learned_places_label_cell"),
    )
    op.create_index("ix_learned_places_country_code", "learned_places", ["country_code"])
    bind = op.get_bind()
    for country in COUNTRIES:
        for flag in FLAGS:
            bind.execute(
                sa.text(
                    "INSERT INTO feature_flags (id, country_code, feature_key, enabled)"
                    " VALUES (:id, :country, :flag, false) ON CONFLICT (country_code, feature_key) DO NOTHING"
                ),
                {"id": uuid.uuid4(), "country": country, "flag": flag},
            )


def downgrade() -> None:
    # **بنيةٌ جديدةٌ تُنزع بنزولها** (دورةُ `test_migrations` الكاملة تُسقط نوعَ `country_code` تحتها) — ولا مالَ فيهما:
    # جدولُ ما تعلّمته الرحلات وعمودُ الأسماء البديلة، ويُعادان بالصعود
    op.drop_index("ix_learned_places_country_code", table_name="learned_places")
    op.drop_table("learned_places")
    op.drop_column("map_places", "aliases")
    op.get_bind().execute(
        sa.text("UPDATE feature_flags SET enabled = false WHERE feature_key IN :flags").bindparams(
            sa.bindparam("flags", expanding=True)
        ),
        {"flags": list(FLAGS)},
    )
