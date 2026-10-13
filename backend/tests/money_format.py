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

---

**ويعرف العملةَ منذ §٧٣** (SPEC §٧٣-ج/٦): **ثلاثُ خاناتٍ بالضبط للأردنيّ والليبيّ ولِما لا عملةَ في سياقه** — كما كان حرفاً —
**وصفرٌ بالضبط للجزائريّ** (`"150"`). والعملةُ تُقرأ كما تقرؤها الصياغةُ على السلك (`app/core/money_wire.py`): حقلُ `currency`
(أو `…_currency`) في الكائن أو في أصله. **ومفرداتُ المال انتقلت إلى هناك** — التشغيلُ يحتاجها لا الاختبارُ وحدَه — وتُستورد هنا.

**ولمَ لا يُقرأ تساوي الحارس والصياغة تحصيلَ حاصل**: الصياغةُ تحذف أصفاراً ولا تصلح كسراً، **فمبلغٌ جزائريٌّ لم يمرّ بعملته
(`"150.500"`) يخرج كما هو ويُسقطه هذا الحارس**؛ والصياغةُ لا تمسّ عملةً بثلاث خانات، **فصفرُ الشكل السابع (`"0"`) يبقى مُمسَكاً
هنا كما كان**.
"""

from __future__ import annotations

from typing import Any

from app.core.currency import CURRENCY_DECIMALS, STORAGE_DECIMALS
from app.core.money_wire import DECIMAL_TEXT, currency_in, is_money_key
from app.core.money_wire import MONEY_NAMES, MONEY_SUFFIXES, NOT_MONEY  # noqa: F401 — يُقرأ من هنا لمن اعتاده
from app.models.enums import Currency


def places_for(currency: str | None) -> int:
    """خاناتُ المبلغ المنتظرة — **ثلاثٌ لما لا عملةَ في سياقه**، كما كان الحارسُ قبل أن يعرف العملة."""
    return CURRENCY_DECIMALS[Currency(currency)] if currency is not None else STORAGE_DECIMALS


def offenders(payload: Any, path: str = "", currency: str | None = None) -> list[str]:
    """أسماءُ الحقول المالية التي خرجت بغير خانات عملتها — وموضعُها."""
    found: list[str] = []
    if isinstance(payload, dict):
        here_currency = currency_in(payload) or currency
        places = places_for(here_currency)
        for key, value in payload.items():
            here = f"{path}.{key}" if path else key
            if (
                is_money_key(str(key))
                and isinstance(value, str)
                and DECIMAL_TEXT.match(value)
            ):
                _, dot, fraction = value.partition(".")
                if len(fraction) != places or (places == 0 and dot):
                    found.append(f"{here} = {value!r} ({here_currency or 'بلا عملة'}: {places} خانات)")
            # **قائمةُ مبالغ تحت اسم مال** (`topup_choices`) — كلُّ عنصرٍ يُفحص كالمفرد
            if is_money_key(str(key)) and isinstance(value, list):
                for index, item in enumerate(value):
                    if isinstance(item, str) and DECIMAL_TEXT.match(item):
                        _, dot, fraction = item.partition(".")
                        if len(fraction) != places or (places == 0 and dot):
                            found.append(f"{here}[{index}] = {item!r} ({here_currency or 'بلا عملة'}: {places} خانات)")
            found.extend(offenders(value, here, here_currency))
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            found.extend(offenders(item, f"{path}[{index}]", currency))
    return found
