"""حارسُ صيغة المال في كل استجابة — الشكلُ السابع في عائلة «ما لا يراه البناء».

**العطبُ وقع مرتين، فهو نمطٌ لا صدفة**: `rewarded_total` عند تعميم الإحالة،
و`total_given_up` في عروض الاشتراكات. وفي الحالتين خرج `"0"` حيث تخرج بقيةُ
المال `"0.000"` — عمودُ `MONEY` يُسلسَل بثلاث خانات، و**قيمةٌ تُنشأ في بايثون**
(قيمةٌ افتراضية، أو `SUM` فارغٌ يعود صفراً) لا تُكمَّم من نفسها.

**ولا `tsc` ولا `check:*` يراه**: النوعُ `Decimal` صحيح، والحقلُ موجود، والقيمةُ
صحيحةٌ عدداً — ما يختلف هو **نصُّها**. والتطبيقات تعرض النصَّ كما هو (§14 يمنع
تمريرَ المال عبر `Number`)، فيقرأ الكبتنُ «٠» بين «٠٫٠٠٠».

---

**ولماذا هذا الحارس لا التكميمُ عند حدّ التسلسل؟** كِلاهما عُرض، وهذا أمتنُ عملياً:

* **التكميمُ الشامل لكل `Decimal` خاطئ**: من ١٨٧ حقلاً عشرياً في المخططات ٥١
  ليست مالاً — نسبةُ خصمٍ (`15`) وتقييمٌ (`4.5`) ومسافة. وطبعُها `15.000`
  و`4.500` تغييرُ عرضٍ لم يطلبه أحد.
* **فالتكميمُ يحتاج تمييزَ المال بنوعٍ خاص** (`Money`) على ١٣٦ حقلاً — و«هل
  استعملتَ النوعَ في الحقل الجديد؟» **هو نفسُه صنفُ السهو الذي نداويه**، فيعود
  الحارسُ محتاجاً حارساً.
* **وهذا يمرّ على ما تنتجه المجموعةُ فعلاً بلا تعليمِ حقل**: لا شيءَ يُضاف عند
  إضافة عمودٍ ماليٍّ جديد، ويكفي أن يمسّه اختبارٌ واحد ليُفحص. والحالتان
  السابقتان **كانتا مغطّاتين باختبارات** — لم يكن ينقص إلا أن يُفحص النصّ.

وحدُّه معلَنٌ لا مخفيّ: **ما لا تمسّه المجموعةُ لا يُفحص**. فهو يحرس ما يُختبر،
ولا يدّعي حراسةَ ما لا يُختبر.
"""

from __future__ import annotations

import re
from typing import Any

# أسماءُ المال — وتُطابَق على **الاسم الكامل أو نهايته**، لا بالاحتواء المجرّد:
# `discount_value` نسبةٌ لا مبلغ، و`rating_avg` تقييم.
MONEY_SUFFIXES = (
    "_amount",
    "_fare",
    "_price",
    "_fee",
    "_balance",
    "_total",
    "_budget",
    "_bonus",
    "_reward",
    # **`_charge` أُضيفت 2026-08-21 بعد قياس**: `waiting_charge` و`pause_charge`
    # و`stops_charge` مبالغُ تُحصَّل من راكبٍ منذ 12-ب، **ولم تكن هذه المفردات
    # تعدّها مالاً** — فلا هذا الحارسُ ولا `check:money-visible` كان يراها.
    # وقياسُ الحارس في الاتجاه الثاني هو ما أظهر الثغرة، لا مراجعةُ القائمة.
    "_charge",
)
MONEY_NAMES = frozenset(
    {
        "amount",
        "balance",
        "fare",
        "price",
        "list_price",
        "amount_paid",
        "final_fare",
        "estimated_fare",
        "paid_amount",
        "outstanding",
        "commission",
        "total_given_up",
        "total_list_price",
        "available_for_withdrawal",
        "min_withdrawal_amount",
        "withdrawal_reserve_amount",
    }
)

# **استثناءاتٌ مسمّاةٌ بسببها** — لا كنسٌ صامت:
# `discount_value` نسبةٌ مئوية، و`max_discount` سقفٌ قد يكون `null`،
# و`total_budget` مبلغٌ يقبل `null` (يُفحص حين لا يكون فارغاً).
NOT_MONEY = frozenset({"discount_value", "duration_min", "distance_km"})

_DECIMAL_TEXT = re.compile(r"^-?\d+(\.\d+)?$")


def _is_money_key(key: str) -> bool:
    if key in NOT_MONEY:
        return False
    return key in MONEY_NAMES or key.endswith(MONEY_SUFFIXES)


def offenders(payload: Any, path: str = "") -> list[str]:
    """أسماءُ الحقول المالية التي خرجت بغير ثلاث خانات — وموضعُها."""
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            here = f"{path}.{key}" if path else key
            if (
                _is_money_key(str(key))
                and isinstance(value, str)
                and _DECIMAL_TEXT.match(value)
            ):
                integer, _, fraction = value.partition(".")
                if len(fraction) != 3:
                    found.append(f"{here} = {value!r}")
            found.extend(offenders(value, here))
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            found.extend(offenders(item, f"{path}[{index}]"))
    return found
