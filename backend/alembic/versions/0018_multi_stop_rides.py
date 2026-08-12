"""تعدد الوجهات — المحطات الوسيطة (المرحلة 12-ب)

جدولُ `ride_stops`، وستةُ أعمدةٍ على `rides`، وعمودُ `leg` على نقاط المسار،
وأربعةُ حقولِ محطاتٍ في `pricing_rules`، وقيمةُ `at_stop` في `ride_status`.

**وثلاثةُ فخاخٍ في هذه الترحيلة بعينها:**

1. **قيمةٌ جديدة في تعدادٍ لا تُستعمل في نفس المعاملة.** والفهرسان الجزئيان
   `uq_rides_active_rider` و`uq_rides_active_driver` مبنيّان على قائمة
   الحالات ويجب أن يشملا `at_stop` — وإلا طلب راكبٌ رحلةً ثانيةً وهو واقفٌ
   عند محطة. **وحيلةُ `0009` لا تعمل هنا**: تلك قارنت `purpose::text` في
   **قيدِ فحص**، وشرطُ الفهرس الجزئي يشترط دالةً `IMMUTABLE` — و`enum::text`
   ليست كذلك، فيرتدّ Postgres بـ«functions in index predicate must be marked
   IMMUTABLE». و`alembic/env.py` يلفّ **كل السلسلة** في معاملةٍ واحدة، فلا
   يكفي شقُّ الترحيلة إلى ملفين. فالحلُّ `COMMIT` صريحٌ بعد `ALTER TYPE`
   وحدَه: أضيقُ ما ينهي المعاملة.
   **وثمنُه أن ما بعده لا يتراجع تلقائياً عند فشلٍ في منتصفه** — فكلُّ ما
   بعده مكتوبٌ **قابلاً لإعادة التنفيذ** (`IF NOT EXISTS`): سقوطٌ في السطر
   الأخير لا يترك ترحيلةً لا تُعاد. وهذا ما كان يقع فعلاً: أولُ محاولةٍ فشلت
   على الفهرس بعد أن ثبّتت الأعمدة، فارتدّت الثانيةُ بـ«column already
   exists» ولزم تنظيفٌ يدوي.
2. **الفهرسان يُسقطان ويُعاد بناؤهما**: تعديلُ شرطٍ جزئي لا يقع بغير ذلك.
3. **أسماءُ القيود بالسابقة التي يولّدها `NAMING_CONVENTION`**
   (`ck_<جدول>_<اسم>`): الاسمُ العاري يمرّ في القاعدة ثم يرفضه
   `test_migrations_match_models`، لأن autogenerate يقارن ما في القاعدة بما
   يولّده النموذج — وهو يولّده بالسابقة.
4. **`DROP TYPE` لا يقع هنا**: `ride_status` أنشأته `0005` وهي من تُسقطه،
   وPostgres لا يحذف قيمةً من تعداد — فالتراجعُ يترك `at_stop` قائمةً
   و`IF NOT EXISTS` هو ما يجعل إعادة الترقية تمرّ.

وكلُّ الأعمدة تصل بقيمةٍ محايدة (`0`)، فتشغيلُ الترحيلة وحده لا يغيّر سلوك
أحد: الميزةُ خلف `multi_stop_enabled` وهو مطفأٌ في الدولتين.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# نفس الثوابت التي يبني منها `models/ride.py` الفهرسين — مكتوبةً هنا نصّاً
# لأن الترحيلة لا تستورد النماذج (تصفُ لحظةً في التاريخ لا ما هو قائم اليوم)
RIDER_ACTIVE = ("requested", "searching", "accepted", "arrived", "in_progress", "at_stop")
DRIVER_ACTIVE = ("accepted", "arrived", "in_progress", "at_stop")

# القديمةُ بلا `at_stop` — يُعاد بناؤها بها في التراجع
RIDER_ACTIVE_OLD = ("requested", "searching", "accepted", "arrived", "in_progress")
DRIVER_ACTIVE_OLD = ("accepted", "arrived", "in_progress")


def _predicate(statuses: Sequence[str]) -> str:
    """شرطُ الفهرس الجزئي — **بلا `::text`**.

    شرطُ الفهرس يشترط دالةً `IMMUTABLE`، و`enum::text` ليست كذلك. والمقارنةُ
    المباشرة `status IN ('…')` تمرّ لأن القيمة أُثبتت بـ`COMMIT` قبلها. وهي
    نفسُ صيغة `models/ride.py::_status_in`، فلا يفترق الفهرسُ عن النموذج ولا
    يقترح autogenerate إعادةَ بنائه.
    """
    values = ", ".join(f"'{value}'" for value in statuses)
    return f"status IN ({values})"


def upgrade() -> None:
    op.execute("ALTER TYPE ride_status ADD VALUE IF NOT EXISTS 'at_stop'")
    # القيمةُ لا تُستعمل قبل أن تُثبَّت — وشرطُ الفهرس أدناه يستعملها
    op.execute("COMMIT")

    # ---------------------------------------------------------- التسعيرة
    # كلُّ ما بعد `COMMIT` بصيغةٍ تُعاد بلا ضرر (انظر رأس الملف)
    _add_columns(
        "pricing_rules",
        [
            ("stop_fee", "NUMERIC(12,3) NOT NULL DEFAULT 0"),
            ("stop_free_minutes", "SMALLINT NOT NULL DEFAULT 0"),
            ("stop_price_per_min", "NUMERIC(12,3) NOT NULL DEFAULT 0"),
            ("stop_max_wait_minutes", "SMALLINT NOT NULL DEFAULT 0"),
        ],
    )
    op.execute(
        "ALTER TABLE pricing_rules DROP CONSTRAINT IF EXISTS "
        "ck_pricing_rules_pricing_stop_amounts_non_negative"
    )
    op.execute(
        "ALTER TABLE pricing_rules ADD CONSTRAINT "
        "ck_pricing_rules_pricing_stop_amounts_non_negative "
        "CHECK (stop_fee >= 0 AND stop_price_per_min >= 0 "
        "AND stop_free_minutes >= 0 AND stop_max_wait_minutes >= 0)"
    )

    # ------------------------------------------------------------ الرحلة
    _add_columns(
        "rides",
        [
            ("stops_count", "SMALLINT NOT NULL DEFAULT 0"),
            ("current_leg", "SMALLINT NOT NULL DEFAULT 0"),
            ("stop_fee_at_ride", "NUMERIC(12,3) NOT NULL DEFAULT 0"),
            ("stop_free_minutes_at_ride", "SMALLINT NOT NULL DEFAULT 0"),
            ("stop_price_per_min_at_ride", "NUMERIC(12,3) NOT NULL DEFAULT 0"),
            ("stop_max_wait_minutes_at_ride", "SMALLINT NOT NULL DEFAULT 0"),
        ],
    )
    _add_columns("ride_route_points", [("leg", "SMALLINT NOT NULL DEFAULT 0")])

    # ------------------------------------------------------- المحطات نفسها
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ride_stops (
            id UUID PRIMARY KEY,
            ride_id UUID NOT NULL REFERENCES rides(id) ON DELETE RESTRICT,
            sequence SMALLINT NOT NULL,
            point geography(POINT, 4326) NOT NULL,
            address VARCHAR(255),
            arrived_at TIMESTAMPTZ,
            resumed_at TIMESTAMPTZ,
            notified_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_ride_stops_ride_sequence UNIQUE (ride_id, sequence),
            CONSTRAINT ck_ride_stops_ride_stop_sequence_range
                CHECK (sequence >= 1 AND sequence <= 2),
            CONSTRAINT ck_ride_stops_ride_stop_resume_needs_arrival
                CHECK (resumed_at IS NULL OR arrived_at IS NOT NULL)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_ride_stops_ride_id ON ride_stops (ride_id)")

    # ------------------------------- الفهرسان الجزئيان يشملان `at_stop` الآن
    _rebuild_active_indexes(RIDER_ACTIVE, DRIVER_ACTIVE)


def _add_columns(table: str, columns: Sequence[tuple[str, str]]) -> None:
    for name, definition in columns:
        op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {definition}")


def downgrade() -> None:
    _rebuild_active_indexes(RIDER_ACTIVE_OLD, DRIVER_ACTIVE_OLD)

    op.execute("DROP INDEX IF EXISTS ix_ride_stops_ride_id")
    op.execute("DROP TABLE IF EXISTS ride_stops")

    op.execute("ALTER TABLE ride_route_points DROP COLUMN IF EXISTS leg")
    for name in (
        "stop_max_wait_minutes_at_ride",
        "stop_price_per_min_at_ride",
        "stop_free_minutes_at_ride",
        "stop_fee_at_ride",
        "current_leg",
        "stops_count",
    ):
        op.execute(f"ALTER TABLE rides DROP COLUMN IF EXISTS {name}")

    op.execute(
        "ALTER TABLE pricing_rules DROP CONSTRAINT IF EXISTS "
        "ck_pricing_rules_pricing_stop_amounts_non_negative"
    )
    for name in (
        "stop_max_wait_minutes",
        "stop_price_per_min",
        "stop_free_minutes",
        "stop_fee",
    ):
        op.execute(f"ALTER TABLE pricing_rules DROP COLUMN IF EXISTS {name}")

    # `at_stop` تبقى في التعداد: Postgres لا يحذف قيمة، والنوع يسقط مع 0005


def _rebuild_active_indexes(
    rider: Sequence[str], driver: Sequence[str]
) -> None:
    op.execute("DROP INDEX IF EXISTS uq_rides_active_rider")
    op.execute("DROP INDEX IF EXISTS uq_rides_active_driver")
    op.create_index(
        "uq_rides_active_rider",
        "rides",
        ["rider_id"],
        unique=True,
        postgresql_where=sa.text(_predicate(rider)),
    )
    op.create_index(
        "uq_rides_active_driver",
        "rides",
        ["driver_id"],
        unique=True,
        postgresql_where=sa.text(_predicate(driver)),
    )
