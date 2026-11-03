"""إرشادُ اقتراح «مريح» (أمرُ المالك ٢٠٢٦-١١-٠٣، SPEC §٩١-ب/٥) — **يُملأ قبل أن تصل قائمةُ المراجعة إلى المشرف**، فيؤكّد ولا يقرّر.

بلا إرشادٍ مكتوبٍ يجيب `categories.suggest` «لا اقتراح» لكلِّ مركبة — وقائمةُ «بحاجة لمراجعة الفئة» تحمل كلَّ مركبات الإنتاج يومَ 0138.
فتُكتب لـ«مريح» في الأردن والجزائر: **أدنى سنةٍ 2018** و**قائمةُ طُرزٍ** (سيدانٌ متوسّطةٌ وكبيرة · SUV · كهربائيّةٌ بحجمها)،
ونصٌّ للمشرف في الفئتين. **والمقترحةُ «مريح» حين تستوفي المركبةُ الاثنين معاً، وإلا «اقتصادي»** (`suggest`).

- **لا يمسّ التوزيع**: المدمجتان تُؤخذان بـ`vehicles.category` وحدَه (`_own_clause`)، و`min_year` لا يدخل شرطَهما — فلا كبتنَ يفقد فئتَه.
- **لا يكتب فوق ما كتبه مشرف**: يُملأ الصفُّ حيث الإرشادُ فارغٌ كلُّه (`min_year` و`suggest_models` و`guidance`) وحدَه.
- **لا مال**: `ride_categories` وحدَه.

**والرجوعُ** يفرغ ما كتبته هذه الترحيلةُ حرفاً، ولا يمسّ ما غيّره مشرفٌ بعدها.

Revision ID: 0140
Revises: 0139
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0140"
down_revision = "0139"
branch_labels = None
depends_on = None

COMFORT_MIN_YEAR = 2018
#: **طُرزُ «مريح»** — جزءٌ من «الشركة الطراز» يكفي (`_model_matches`)، فـ«Sonata» يطابق «Hyundai Sonata Hybrid»
COMFORT_MODELS = (
    "Camry", "Accord", "Sonata", "K5", "Optima", "Altima", "Mazda 6", "Mazda6", "Passat", "Superb", "Octavia",
    "Peugeot 508", "Talisman", "Avalon", "Azera", "Grandeur", "Cadenza", "K8", "Teana",
    "Tucson", "Sportage", "Santa Fe", "Sorento", "RAV4", "CR-V", "X-Trail", "Tiguan", "Peugeot 3008", "Peugeot 5008",
    "Ioniq 5", "Ioniq 6", "Model 3", "Model Y", "BYD Han", "BYD Seal", "Atto 3",
)
COMFORT_GUIDANCE = (
    "مريح: سيدانٌ متوسّطةٌ أو كبيرة أو SUV، صنعُ 2018 فأحدث، مقصورةٌ واسعةٌ نظيفة ومكيّفٌ يعمل. "
    "الاقتراحُ من الطراز والسنة — انظر الصورَ قبل التأكيد."
)
ECONOMY_GUIDANCE = "اقتصادي: كلُّ مركبةٍ معتمَدةٍ لا تستوفي إرشادَ فئةٍ أعلى."


def _models_literal() -> str:
    return "ARRAY[" + ", ".join(f"'{model}'" for model in COMFORT_MODELS) + "]::varchar(60)[]"


def upgrade() -> None:
    op.execute(
        sa.text(
            f"UPDATE ride_categories SET min_year = {COMFORT_MIN_YEAR}, suggest_models = {_models_literal()}, guidance = :comfort "
            "WHERE key = 'comfort' AND country_code IN ('JO', 'DZ') "
            "AND min_year IS NULL AND suggest_models = '{}' AND guidance IS NULL"
        ).bindparams(comfort=COMFORT_GUIDANCE)
    )
    op.execute(
        sa.text(
            "UPDATE ride_categories SET guidance = :economy "
            "WHERE key = 'economy' AND country_code IN ('JO', 'DZ') AND guidance IS NULL"
        ).bindparams(economy=ECONOMY_GUIDANCE)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE ride_categories SET min_year = NULL, suggest_models = '{}', guidance = NULL "
            f"WHERE key = 'comfort' AND min_year = {COMFORT_MIN_YEAR} AND suggest_models = {_models_literal()} AND guidance = :comfort"
        ).bindparams(comfort=COMFORT_GUIDANCE)
    )
    op.execute(
        sa.text("UPDATE ride_categories SET guidance = NULL WHERE key = 'economy' AND guidance = :economy").bindparams(
            economy=ECONOMY_GUIDANCE
        )
    )
