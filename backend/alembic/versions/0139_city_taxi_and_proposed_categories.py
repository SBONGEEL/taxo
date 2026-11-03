"""«تاكسي المدينة» ووثيقتُها، والطاقمُ المقترح (أمرُ المالك ٢٠٢٦-١١-٠٢، SPEC §٩١-ب/٧) — **مطفأةً كلُّها، بلا سعرٍ ولا رصيد**.

- `document_type` + `taxi_licence` — **رخصةُ/تسجيلُ التاكسي**: وثيقةٌ اختياريّةٌ يرفعها الكبتنُ ويراجعها المشرف، ولا تحبس اعتماداً.
- `ride_categories.required_document` — **وثيقةٌ يشترطها منحُ الفئة يدوياً** (فارغٌ = لا شرط، وهو كلُّ صفٍّ قائم).
- **الفئاتُ الأربع تولد مطفأة** حيث للاقتصادي صفُّ أسعارٍ — **الأردن والجزائر لا ليبيا** (تبقى مخفيّة): «تاكسي المدينة» (بالمنح بعد
  الرخصة) · «عائليّة» (٦ مقاعد فأكثر) · «مميّزة» (بالمنح) · «فان» (هيكلُ فان). **ولا تُشعَل فئةٌ بلا أسعارٍ موجبة** (`require_priced`) —
  فلا صفَّ أسعارٍ يُكتب هنا، والمالكُ يسعّر ويشعل من اللوحة حين يوجد كباتن. **وما كتبه المشرفُ بالمفتاح نفسِه يبقى** (`ON CONFLICT`).

**والرجوع**: حذفُ العمود، وحذفُ الصفوف الأربعة **ما دامت مطفأةً بلا أسعار**. **وقيمةُ التعداد لا تُنزع** — `ALTER TYPE … ADD VALUE` لا
عكسَ له في Postgres (كـ`0037`)، ولا يضرّ بقاؤها.

Revision ID: 0139
Revises: 0138
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0139"
down_revision = "0138"
branch_labels = None
depends_on = None

#: (المفتاح، الاسم، fr، en، الأيقونة، الوصف، المقاعد، الترتيب، الهياكل، أدنى مقاعد، الوثيقة)
PROPOSED: tuple[tuple, ...] = (
    ("city_taxi", "تاكسي المدينة", "Taxi de ville", "City taxi", "local_taxi", "تاكسي مرخَّص من المدينة", 4, 2, [], None, "taxi_licence"),
    ("family", "عائليّة", "Familiale", "Family", "airport_shuttle", "حتى ٦ ركّاب", 6, 3, [], 6, None),
    ("vip", "مميّزة", "Premium", "Premium", "diamond", "سيارةٌ فاخرةٌ وكبتنٌ مختار", 4, 4, [], None, None),
    ("van", "فان", "Van", "Van", "airport_shuttle", "مساحةٌ للأمتعة والحمولة", 7, 5, ["van"], None, None),
)
KEYS = tuple(row[0] for row in PROPOSED)


def upgrade() -> None:
    op.execute("ALTER TYPE document_type ADD VALUE IF NOT EXISTS 'taxi_licence'")
    op.add_column("ride_categories", sa.Column("required_document", sa.String(length=32), nullable=True))
    for key, name, name_fr, name_en, icon, description, seats, order, bodies, min_seats, document in PROPOSED:
        op.execute(
            sa.text(
                "INSERT INTO ride_categories "
                "(id, country_code, key, name, name_fr, name_en, icon, description, seats, sort_order, is_active, is_builtin, "
                " allowed_body_types, allowed_fuels, min_seats, suggest_models, serves_lower, required_document) "
                "SELECT gen_random_uuid(), m.country_code, :key, :name, :name_fr, :name_en, :icon, :description, :seats, :order, "
                "       false, false, CAST(:bodies AS VARCHAR(20)[]), '{}', :min_seats, '{}', false, :document "
                # **سوقٌ مرّةً واحدة** ولو تعدّدت صفوفُ أسعاره
                "FROM (SELECT DISTINCT country_code FROM pricing_rules "
                "      WHERE vehicle_category = 'economy' AND country_code IN ('JO', 'DZ')) m "
                "ON CONFLICT (country_code, key) DO NOTHING"
            ).bindparams(
                key=key, name=name, name_fr=name_fr, name_en=name_en, icon=icon, description=description, seats=seats,
                order=order, bodies="{" + ",".join(bodies) + "}", min_seats=min_seats, document=document,
            )
        )


def downgrade() -> None:
    # **المطفأةُ بلا أسعارٍ وحدَها** — ما أشعله المالكُ أو سعّره بقي له
    op.execute(
        sa.text(
            "DELETE FROM ride_categories rc WHERE rc.key IN :keys AND rc.is_active = false AND NOT EXISTS "
            "(SELECT 1 FROM pricing_rules pr WHERE pr.country_code = rc.country_code AND pr.vehicle_category = rc.key)"
        ).bindparams(sa.bindparam("keys", value=KEYS, expanding=True))
    )
    op.drop_column("ride_categories", "required_document")
