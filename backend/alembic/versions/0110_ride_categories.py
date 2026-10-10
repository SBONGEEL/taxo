"""فئاتُ الرحلة من اللوحة (SPEC §٦٧، `design/RIDE-CATEGORIES-PLAN.md`) — الفئةُ بيانٌ لا تعداد.

1. **`ride_categories`** لكلِّ دولة — مفتاحٌ ثابت · اسمٌ وأيقونةٌ ووصفٌ ومقاعد · ترتيب · مشتعلٌ؟ (**مطفأٌ افتراضاً**) · مدمجةٌ؟ · الشروط.
   **وتُبذر المدمجتان** (`economy` · `comfort`) **مشتعلتين في كلِّ سوقٍ له صفُّ أسعارٍ لهما** — والأسعارُ نفسُها لا تُمسّ.
2. **`driver_category_access`** — منحُ المشرف فئةً جديدةً لكبتنٍ أو نزعُها منه، مدقَّقاً.
3. **صفاتُ المركبة** `body_type` · `fuel` · `seats` — **فارغةً**: فلا تستوفي مركبةٌ لم تُراجَع شرطَ فئةٍ جديدة.
4. **الأعمدةُ الأربعة** (`rides` · `ride_bookings` · `pricing_rules` · `vehicles`) **من نوع Postgres إلى نصّ** بالقيم نفسِها (`USING …::text`) —
   **لا قيمةَ تتغيّر في أيِّ صفٍّ قائم**، ثمّ يُسقط النوع.

**ولا جدولَ مالٍ يُمسّ قائمُه**: الدفترُ والدفعاتُ لا عمودَ فئةٍ فيها، و`pricing_rules` يتغيّر **نوعُ** عمودٍ فيه لا قيمةٌ.

**و`downgrade` مقيسٌ لا مقروء**: يُعيد النوعَ ويحوّل الأعمدةَ إليه — **وفئةٌ جديدةٌ في أيِّ صفٍّ تُسقط التراجعَ عمداً** (القيمةُ لا تُحوَّل)، فلا
تضيع رحلةٌ بتراجعٍ صامت.

Revision ID: 0110
Revises: 0109
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0110"
down_revision = "0109"
branch_labels = None
depends_on = None

#: (الجدول، العمود) — **بأسمائها في القاعدة**
COLUMNS = (
    ("rides", "vehicle_category"),
    ("ride_bookings", "vehicle_category"),
    ("pricing_rules", "vehicle_category"),
    ("vehicles", "category"),
)

#: **المدمجتان بوجهيهما في تطبيق الراكب اليوم حرفاً** (`VEHICLE_LABEL` · `VEHICLE_HINT` · `CATEGORY_ICON`) — فلا يتغيّر ما يُرى
BUILTINS = (
    ("economy", "اقتصادي", "local_taxi", "الخيار الأوفر", 4, 0),
    ("comfort", "مريح", "directions_car", "سيارة أوسع وأحدث", 4, 1),
)


def upgrade() -> None:
    op.create_table(
        "ride_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "country_code",
            postgresql.ENUM("LY", "JO", name="country_code", create_type=False),
            nullable=False,
        ),
        sa.Column("key", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("icon", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=120), nullable=True),
        sa.Column("seats", sa.SmallInteger(), nullable=False, server_default=sa.text("4")),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "allowed_body_types", postgresql.ARRAY(sa.String(length=20)), nullable=False, server_default=sa.text("'{}'")
        ),
        sa.Column("allowed_fuels", postgresql.ARRAY(sa.String(length=20)), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("min_year", sa.SmallInteger(), nullable=True),
        sa.Column("min_seats", sa.SmallInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ride_categories")),
        sa.UniqueConstraint("country_code", "key", name=op.f("uq_ride_categories_country_code_key")),
        sa.CheckConstraint("key ~ '^[a-z][a-z0-9_]{1,31}$'", name=op.f("ck_ride_categories_ride_category_key_shape")),
        sa.CheckConstraint(
            "seats BETWEEN 1 AND 20 AND (min_seats IS NULL OR min_seats BETWEEN 1 AND 20) "
            "AND (min_year IS NULL OR min_year BETWEEN 1990 AND 2100)",
            name=op.f("ck_ride_categories_ride_category_ranges"),
        ),
    )
    op.create_index(op.f("ix_ride_categories_country_code"), "ride_categories", ["country_code"])

    op.create_table(
        "driver_category_access",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.String(length=280), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_driver_category_access")),
        sa.ForeignKeyConstraint(
            ["driver_id"], ["drivers.id"], ondelete="CASCADE", name=op.f("fk_driver_category_access_driver_id_drivers")
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["ride_categories.id"],
            ondelete="CASCADE",
            name=op.f("fk_driver_category_access_category_id_ride_categories"),
        ),
        sa.UniqueConstraint("driver_id", "category_id", name=op.f("uq_driver_category_access_driver_id_category_id")),
    )
    op.create_index(op.f("ix_driver_category_access_category_id"), "driver_category_access", ["category_id"])

    op.add_column("vehicles", sa.Column("body_type", sa.String(length=20), nullable=True))
    op.add_column("vehicles", sa.Column("fuel", sa.String(length=20), nullable=True))
    op.add_column("vehicles", sa.Column("seats", sa.SmallInteger(), nullable=True))
    op.create_check_constraint("vehicle_seats_range", "vehicles", "seats IS NULL OR seats BETWEEN 1 AND 20")

    for table, column in COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE VARCHAR(32) USING {column}::text")
    op.execute("DROP TYPE vehicle_category")

    # **المدمجتان مشتعلتين حيث لهما أسعار** — صفٌّ لكلِّ (دولةٍ، فئةٍ) في `pricing_rules`
    for key, name, icon, description, seats, order in BUILTINS:
        op.execute(
            sa.text(
                "INSERT INTO ride_categories "
                "(id, country_code, key, name, icon, description, seats, sort_order, is_active, is_builtin) "
                "SELECT gen_random_uuid(), country_code, :key, :name, :icon, :description, :seats, :order, true, true "
                "FROM pricing_rules WHERE vehicle_category = :key"
            ).bindparams(key=key, name=name, icon=icon, description=description, seats=seats, order=order)
        )


def downgrade() -> None:
    op.execute("CREATE TYPE vehicle_category AS ENUM ('economy', 'comfort')")
    for table, column in COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE vehicle_category USING {column}::vehicle_category"
        )
    op.drop_constraint(op.f("ck_vehicles_vehicle_seats_range"), "vehicles", type_="check")
    for column in ("seats", "fuel", "body_type"):
        op.drop_column("vehicles", column)
    op.drop_index(op.f("ix_driver_category_access_category_id"), table_name="driver_category_access")
    op.drop_table("driver_category_access")
    op.drop_index(op.f("ix_ride_categories_country_code"), table_name="ride_categories")
    op.drop_table("ride_categories")
