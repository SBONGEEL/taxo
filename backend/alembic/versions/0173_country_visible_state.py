"""مُنتقي الدول بأربع حالات (أمرُ المالك ٢٠٢٦-١١-١٨ الثاني): «ظاهرة»، ونصُّها، و«أعلمني فور الإطلاق»، والدولةُ الجديدةُ مخفيّة.

**لا جدولَ مالٍ يُمسّ.** وما يُكتب من صفوف **يُثبّت ما يُرى اليوم بعينه** قبل أن يتغيّر الافتراض: كان غيابُ صفِّ الدولة غيرِ السوق
«متوقفة» وغيابُ صفِّ السوق «قريباً»، **وصار الغيابُ «مخفية»** (الدولةُ الجديدةُ لا تظهر حتى يختار المالك) — فتُكتب صفوفٌ صريحةٌ
بالحال القديمة لكلِّ دولةٍ في القائمة بلا صفّ، **فلا يتغيّر علمٌ واحدٌ في المنتقي بهذه الترحيلة**.
والقائمةُ **مكتوبةٌ هنا حرفاً** كما كانت يومَ كُتبت (ترحيلةٌ لا تقرأ الشيفرةَ الحيّة).

**والرجوعُ** يحذف الجدولَ والعمودين، ويُعيد كلَّ «ظاهرة» إلى «قريباً»، ويحذف الصفوفَ التي كتبها (بعلامتها `updated_by IS NULL`
وحالها كما كُتبت) — وقيمةُ التعداد تبقى (Postgres لا ينزعها).

Revision ID: 0173
Revises: 0172
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0173"
down_revision = "0172"
branch_labels = None
depends_on = None

MARKETS = ("JO", "DZ", "LY")
OTHERS = (
    "BH", "KM", "DJ", "EG", "IQ", "KW", "LB", "MR", "MA", "OM", "PS", "QA", "SA", "SO", "SD", "SY", "TN", "AE", "YE",
    "TR", "FR", "DE", "GB", "IT", "ES", "BE", "NL", "CH", "AT", "SE", "NO", "DK", "MT", "CY", "CA", "US",
)


def upgrade() -> None:
    op.execute("ALTER TYPE signup_display ADD VALUE IF NOT EXISTS 'visible'")
    op.add_column("country_markets", sa.Column("visible_message", sa.String(300), nullable=True))
    op.add_column("signup_countries", sa.Column("visible_message", sa.String(300), nullable=True))
    op.create_table(
        "launch_interests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_launch_interests")),
        sa.UniqueConstraint("country", "phone", name="uq_launch_interests_country_phone"),
    )
    # **ما يُرى اليوم يُثبَّت صفّاً** — قبل أن يصير الغيابُ «مخفية»
    values = ", ".join(f"('{code}', 'stopped')" for code in OTHERS)
    op.execute(
        f"INSERT INTO signup_countries (code, display) VALUES {values} ON CONFLICT (code) DO NOTHING"
    )
    markets = ", ".join(f"('{code}')" for code in MARKETS)
    op.execute(
        f"INSERT INTO country_markets (country_code) SELECT v.code::country_code FROM (VALUES {markets}) AS v(code) "
        "ON CONFLICT (country_code) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("UPDATE country_markets SET signup_display = 'soon' WHERE signup_display::text = 'visible'")
    op.execute("UPDATE signup_countries SET display = 'soon' WHERE display::text = 'visible'")
    op.drop_table("launch_interests")
    op.drop_column("signup_countries", "visible_message")
    op.drop_column("country_markets", "visible_message")
