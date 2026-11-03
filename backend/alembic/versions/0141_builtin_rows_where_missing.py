"""صفّا المدمجتين في السوق الذي لم يُبذرا فيه، وأسماءُ «مريح» بالعربيّة (أمرُ المالك ٢٠٢٦-١١-٠٣، SPEC §٩١-ب/٥).

**قِيس على الإنتاج بعد `0140`**: قائمةُ «بحاجة لمراجعة الفئة» في الجزائر (٦ مركبات) بقيت «لا إرشادَ مكتوبٌ للفئتين» — لأن `0110` بذرت
المدمجتين حيث كان لهما صفُّ أسعارٍ **يومَها**، والجزائرُ وُلدت بعدها (`0111`) فلا صفَّ لهما فيها، و`0140` تكتب في صفٍّ موجودٍ لا تُنشئه.

1. **يُنشأ صفّا «اقتصادي» و«مريح» حيث لهما أسعارٌ ولا صفّ** (الأردن والجزائر لا ليبيا) — **مشتعلين، بترتيب ٠ و١، وبوجههما الافتراضيّ
   حرفاً** (`categories._BUILTIN_FACES`)، ومعهما إرشادُ `0140` وأسماؤه بالعربيّة. **وما كتبه مشرفٌ بالمفتاح نفسِه يبقى** (`ON CONFLICT`).
2. **أسماءُ طُرز «مريح» بالعربيّة** — الكبتنُ يكتب طرازَه كما يشاء («تويوتا كامري» في قائمة الأردن)، و`_model_matches` يطابق النصَّ لا
   المعنى. **تُضاف حيث القائمةُ هي قائمةُ `0140` حرفاً** — فلا يُكتب فوق قائمةٍ عدّلها مشرف.

**لا يمسّ التوزيعَ ولا ما يراه الراكب**: صفٌّ مدمجٌ مشتعلٌ بترتيب ٠/١ و«الأعلى يأخذ الأدنى» مطفأةٌ فيه يساوي غيابَه في `requestable_keys`
و`takers` و`_own_clause` (المدمجةُ تُؤخذ بـ`vehicles.category` وحدَه، و`min_year` لا يدخل شرطَها) و`public_face`. **ولا مال**: `ride_categories` وحدَه.

**والرجوع** يعيد قائمةَ `0140` حيث القائمةُ قائمةُ هذه حرفاً، **ولا يحذف الصفّين**: غيابُهما وحضورُهما سواءٌ سلوكاً، وحذفُ صفٍّ لا يُعرف
أأنشأته هذه أم مشرفٌ بعدها ليس رجوعاً — و`0140` نازلةً تفرغ إرشادَهما كما تفرغه في كلِّ صف.

Revision ID: 0141
Revises: 0140
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0141"
down_revision = "0140"
branch_labels = None
depends_on = None

#: **قائمةُ `0140` حرفاً** — الترحيلةُ لقطةٌ لا تستورد من أختها
COMFORT_MODELS_0140 = (
    "Camry", "Accord", "Sonata", "K5", "Optima", "Altima", "Mazda 6", "Mazda6", "Passat", "Superb", "Octavia",
    "Peugeot 508", "Talisman", "Avalon", "Azera", "Grandeur", "Cadenza", "K8", "Teana",
    "Tucson", "Sportage", "Santa Fe", "Sorento", "RAV4", "CR-V", "X-Trail", "Tiguan", "Peugeot 3008", "Peugeot 5008",
    "Ioniq 5", "Ioniq 6", "Model 3", "Model Y", "BYD Han", "BYD Seal", "Atto 3",
)
#: **الطُّرزُ نفسُها بالعربيّة كما تُكتب** — بالهمزة وبلاها حيث يكثر الوجهان
COMFORT_MODELS_AR = (
    "كامري", "أكورد", "اكورد", "سوناتا", "أوبتيما", "اوبتيما", "ألتيما", "التيما", "مازدا 6", "باسات", "سوبيرب", "أوكتافيا",
    "اوكتافيا", "بيجو 508", "أفالون", "افالون", "أزيرا", "ازيرا", "جراندير", "غراندير", "تيانا",
    "توسان", "سبورتاج", "سانتا في", "سانتافي", "سورنتو", "راف 4", "راف4", "تيغوان", "تيجوان", "بيجو 3008", "بيجو 5008",
    "أيونيك", "ايونيك",
)
COMFORT_MODELS = COMFORT_MODELS_0140 + COMFORT_MODELS_AR
COMFORT_MIN_YEAR = 2018
COMFORT_GUIDANCE = (
    "مريح: سيدانٌ متوسّطةٌ أو كبيرة أو SUV، صنعُ 2018 فأحدث، مقصورةٌ واسعةٌ نظيفة ومكيّفٌ يعمل. "
    "الاقتراحُ من الطراز والسنة — انظر الصورَ قبل التأكيد."
)
ECONOMY_GUIDANCE = "اقتصادي: كلُّ مركبةٍ معتمَدةٍ لا تستوفي إرشادَ فئةٍ أعلى."

#: (المفتاح، الاسم، الأيقونة، الوصف، الترتيب، أدنى سنة، الطُّرز، الإرشاد) — **وجهُ `_BUILTIN_FACES` حرفاً**
BUILTINS = (
    ("economy", "اقتصادي", "local_taxi", "الخيار الأوفر", 0, None, (), ECONOMY_GUIDANCE),
    ("comfort", "مريح", "directions_car", "سيارة أوسع وأحدث", 1, COMFORT_MIN_YEAR, COMFORT_MODELS, COMFORT_GUIDANCE),
)


def _literal(models: tuple[str, ...]) -> str:
    return "ARRAY[" + ", ".join(f"'{model}'" for model in models) + "]::varchar(60)[]" if models else "'{}'::varchar(60)[]"


def upgrade() -> None:
    for key, name, icon, description, order, min_year, models, guidance in BUILTINS:
        op.execute(
            sa.text(
                "INSERT INTO ride_categories "
                "(id, country_code, key, name, icon, description, seats, sort_order, is_active, is_builtin, "
                " min_year, suggest_models, guidance) "
                "SELECT gen_random_uuid(), country_code, :key, :name, :icon, :description, 4, :order, true, true, "
                f"       CAST(:min_year AS SMALLINT), {_literal(models)}, :guidance "
                "FROM pricing_rules WHERE vehicle_category = :key AND country_code IN ('JO', 'DZ') "
                "ON CONFLICT (country_code, key) DO NOTHING"
            ).bindparams(
                key=key, name=name, icon=icon, description=description, order=order, min_year=min_year, guidance=guidance
            )
        )
    op.execute(
        f"UPDATE ride_categories SET suggest_models = {_literal(COMFORT_MODELS)} "
        f"WHERE key = 'comfort' AND suggest_models = {_literal(COMFORT_MODELS_0140)}"
    )


def downgrade() -> None:
    op.execute(
        f"UPDATE ride_categories SET suggest_models = {_literal(COMFORT_MODELS_0140)} "
        f"WHERE key = 'comfort' AND suggest_models = {_literal(COMFORT_MODELS)}"
    )
