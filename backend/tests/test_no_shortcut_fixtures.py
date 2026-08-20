"""**البند ٨**: مساعدُ اختبارٍ يختصر مساراً حقيقياً يصير مصدرَ حقيقةٍ ثانياً.

**وقع مرتين مقيستين.** `awaiting_confirmation` مرّ من مراجعةٍ كاملةٍ لأن
معايناتِ الواجهة كُتبت بيدٍ **بالقيمة المخترعة نفسِها** — فوافق المساعدُ
افتراضَ كاتبه؛ وفي 2026-08-20 بنَت أولُ صياغةٍ لاختبار العمولة صفَّ `Ride`
بيدها، فسقطت على عمودين ناقصين (`vehicle_category` ثم `pickup_point`) — **وهذا
هو الإنذارُ المحظوظ**: لو كان العمودُ الناقص ذا افتراضٍ لمرّت، وقاست عالماً
لا وجودَ له.

**والقاعدة**: صفوفُ المسارات المالية والحالاتية تُنشأ **بمسارها الحقيقيّ**
(`helpers.completed_ride`، `helpers.pay_ride`)، لا بـ`Model(...)` في ملفِّ
اختبار. **وكلُّ حقلٍ يضيفه الأصلُ ولا يضيفه المساعد يجعل الاختباراتِ تقيس
عالماً لا وجودَ له.**

**وما يُسمح به بعلّته**: بناءُ صفٍّ مباشرةً حين يكون موضوعُ الاختبار **العرضَ**
لا المسار — كتابةُ قيدٍ لقياس ما تعرضه الشاشة عنه. ويُصنَّف بنصّه، لأن قائمةً
بلا عللٍ تصير أعذاراً.
"""

from __future__ import annotations

import ast
import pathlib

TESTS = pathlib.Path(__file__).resolve().parent

#: نماذجُ لها مسارٌ حقيقيٌّ في `helpers.py` — بناؤها بيدٍ يختصره.
GUARDED = {"Ride", "Payment", "DriverSubscription", "WithdrawalRequest"}

#: ملفٌّ ← علّةُ سماحه بالبناء المباشر.
ALLOWED: dict[str, str] = {
    "helpers.py": "هو المسارُ الحقيقيُّ نفسُه — البابُ الذي يُنادى لا الذي يُختصر",
    "conftest.py": "تهيئةُ بيئةٍ لا قياسُ مسار",
}


def test_no_test_builds_a_money_row_by_hand() -> None:
    offenders: list[str] = []
    scanned = 0

    for path in sorted(TESTS.glob("test_*.py")):
        scanned += 1
        if path.name in ALLOWED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in GUARDED
                # `Model(...)` بوسائطَ مسمّاة = بناءُ صفّ. و`Model` وحدَه في
                # `select(Ride)` ليس نداءً أصلاً فلا يصل هنا
                and (node.keywords or node.args)
            ):
                key = f"{path.name}:{node.lineno}"
                if key.split(":")[0] in ALLOWED:
                    continue
                offenders.append(f"{key}  {node.func.id}(…)")

    # **إثباتُ الصمت** (قاعدةُ المِسبار ٥)
    assert scanned >= 50, f"لم يُقرأ إلا {scanned} ملفَّ اختبار — المسحُ أعمى"

    known = set(_ACCEPTED)
    surprises = [o for o in offenders if o.rsplit("  ", 1)[0] not in known]
    assert not surprises, (
        "اختباراتٌ تبني صفَّ مسارٍ ماليٍّ بيدها بدل مسارِه الحقيقيّ:\n  "
        + "\n  ".join(surprises)
        + "\n\n  استعمل `helpers.completed_ride` / `helpers.pay_ride`، أو صنّفه"
        "\n  في `_ACCEPTED` بعلّته إن كان موضوعُ الاختبار العرضَ لا المسار."
    )


#: `ملف:سطر` ← علّةُ قبوله. **والسطرُ جزءٌ من المفتاح عمداً**: نقلُ البناء أو
#: إضافةُ ثانٍ يُظهره من جديد فيُراجَع، ولا يختبئ تحت عذرٍ كُتب لغيره.
_ACCEPTED: dict[str, str] = {
    # **ماضٍ لا يُقاد**: مستوى الكبتن يُحسب على شهرٍ من الرحلات، ولا يمكن
    # قيادةُ ثلاثين رحلةً في اختبار — والتاريخُ نفسُه هو موضوعُ القياس
    "test_missions_levels.py:66": "رحلاتٌ تاريخيةٌ لحساب المستوى — الماضي لا يُقاد",
    "test_missions_levels.py:241": "رحلاتٌ تاريخيةٌ لحساب المستوى — الماضي لا يُقاد",
    # **الفهرسُ هو الموضوع**: يُقاس ما تمنعه القاعدةُ نفسُها، بأقلِّ صفٍّ تقبله.
    # والمرورُ بالمسار الحقيقيّ يجعل الخدمةَ تردّ قبل أن تصل القاعدةُ فلا يُقاس
    # الفهرسُ أصلاً
    "test_ride_sharing_index.py:55": "الفهرسُ هو المقيس لا التسعير — وصفُّه موثَّقٌ في الملف",
    "test_ride_sharing_join_concurrency.py:38": "تشابكٌ صريحٌ يحتاج صفَّين في حالةٍ محدَّدة",
    # **جغرافيا مصطنعة**: المطابقةُ تُقاس بنقاطٍ متباعدةٍ بالكيلومترات، ولا
    # يقودها راكبٌ في اختبار
    "test_ride_sharing.py:288": "نقاطٌ جغرافيةٌ محدَّدةٌ لقياس الممرّ",
    "test_ride_sharing_matching.py:79": "نقاطٌ جغرافيةٌ محدَّدةٌ لقياس الممرّ",
    # **اشتراكٌ بدأ في الماضي**: شرطُ السلفة «اشتراكٌ انقضى»، ولا يُنتظر شهر
    "test_advances.py:113": "اشتراكٌ بدأ قبل ٤٥ يوماً — شرطُ الاستحقاق زمنيّ",
    "test_advances.py:248": "اشتراكٌ بدأ في الماضي — شرطُ الاستحقاق زمنيّ",
    "test_subscription_auto_renew.py:36": "اشتراكٌ يوشك أن ينتهي — التجديدُ يُقاس على حافّته",
    "test_subscriptions.py:318": "مدّةٌ سابقةٌ لقياس تراكم الفترات",
    "test_subscriptions.py:366": "مدّةٌ سابقةٌ لقياس تراكم الفترات",
}
