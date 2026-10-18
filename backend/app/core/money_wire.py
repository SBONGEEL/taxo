"""**صيغةُ المال على السلك تتبع العملة** (SPEC §٧٣-ج/٥) — «150» للجزائريّ، و«150.000» للأردنيّ والليبيّ كما كان حرفاً.

**ومفرداتُ المال بيتُها هنا** — كانت في `tests/money_format.py` وحدَه، فلمّا احتاجها التشغيلُ نُقلت ولم تُنسخ: حارسُ الاختبار
(`tests/money_format.py`) يستوردها، و`tools/check-money-visible.mjs` و`tools/check-money-math.mjs` يقرآن كتلَها نصّاً **من هذا
الملفّ** — فالكتلُ الثلاثُ بأسمائها وأقواسها جزءٌ من العقد، **ولا يُكتب اسمُ كتلةٍ متبوعاً بعلامة الإسناد في غير موضعها**: الأداتان
تبحثان عن أوّل ظهورٍ له نصّاً، وظهورُه هنا في التوثيق أعمى الحارسين في أوّل تشغيل (قِيس ٢٠٢٦-١٠-١١).

**ونقطتا الصياغة** (لا ثالثةَ لهما): ردُّ HTTP (`MoneyWireMiddleware`) وبثُّ المقبس (`ws/routes.py`). **وكلتاهما لا تمسّ إلا ما
عملتُه أقلُّ من ثلاث خانات**: الوسيطُ لا يفتح جسماً لا يذكر عملةً منها نصّاً (فجوابٌ أردنيٌّ أو ليبيٌّ يمرّ بايتاً بايتاً)، والدالّةُ
تعيد الحمولةَ نفسَها حين لا تغيّر شيئاً.

**والعملةُ تُقرأ من الحمولة نفسِها**: حقلُ `currency` (أو `…_currency`) في الكائن **أو في أصله** — فقيودُ محفظةٍ تحت جوابٍ يحمل
عملتَه تُصاغ بها. **وما لا عملةَ في سياقه يبقى كما هو** (ثلاثُ خانات)، والتطبيقُ يصوغه بعملة صاحبه.

**ولا تُصلح كسراً**: مبلغٌ جزائريٌّ فيه كسرٌ (`"150.500"`) يبقى كما هو — **فيُسقطه الحارس** ولا يستر خطأَ تقريبٍ قبلها
(الشكلُ الثاني عشر). الصياغةُ تحذف أصفاراً لا قيمة.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.currency import COUNTRY_CURRENCY, CURRENCY_DECIMALS, STORAGE_DECIMALS
from app.models.enums import CountryCode, Currency

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
    "_debt",
    "_compensation",
    # **`_revenue` و`revenue` أُضيفتا 2026-10-07** (§٦٢-ب/٥٢): إيرادُ «نظرة عامة» خرج «0» ليومٍ بلا رحلات (رآه وكيلُ اللوحة) —
    # **ولم تكن المفرداتُ تعدّه مالاً**، فمرّ من هذا الحارس كما مرّت الرسومُ قبل `_charge`
    "_revenue",
)
MONEY_NAMES = frozenset(
    {
        "amount",
        "revenue",
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
        # **`hourly_rate` أُضيف ٢٠٢٦-١٠-١١** (§٧٣، البندُ المفتوح ٤): سعرُ الساعة يُدفع كما هو — «500» للجزائريّ — **ولم تكن
        # المفرداتُ تعدّه مالاً** فخرج «500.000». **ولا تُضاف `_rate` لاحقةً**: `cancellation_rate` نسبةٌ لا مبلغ
        "hourly_rate",
        # **`in_transit` و`topup_choices` أُضيفا ٢٠٢٦-١٠-١٣** (§٧٤-ي): «قيد التحويل» في محفظة الكبتن، **وخياراتُ الشحن قائمةُ
        # مبالغ** — فالقائمةُ تُصاغ عنصراً عنصراً بعملة سياقها (`normalize`)، و«500» للجزائريّ لا «500.000»
        "in_transit",
        "topup_choices",
        "balance_after",
        "ceiling",
    }
)

#: **أسماءُ مالٍ تُصاغ على السلك ولا تدخل مفرداتِ الحارسين** (§٧٦-ع/٢، ٢٠٢٦-١٠-١٧). مسحُ أجوبة الكبتن والراكب الجزائريَّين أخرج
#: «200.000» لثمن الخطّة و«0.000» لصافي اليوم وسقفِ السلفة وسقفِ الدَّين ورسومِ الإلغاء. **ولمَ ليست في الكتلتين أعلاه**: الحارسان
#: الساكنان (`check:money-math` و`check:money-visible`) يقرآنهما نصّاً — **فـ`total` و`cap` كلمتان عامّتان** أمسكتا `event.total` في
#: تقدّم الرفع وقسمةَ صفحاتٍ في اللوحة مالاً (قِيس: سقط الحارسان بتسعة أسطرٍ ليس فيها مال). **والصياغةُ تحذف أصفاراً ولا تغيّر قيمة**،
#: فاسمٌ زائدٌ هنا لا يُفسد رقماً؛ **وحارسُ الاختبار (`tests/money_format.py`) يقرؤها** عبر `is_money_key` فيُفحص نصُّها في كلِّ جواب.
#: **وعادت `balance_after` و`ceiling` و`_debt` و`_compensation` إلى المفردات** (§٧٦-ع/٥، ٢٠٢٦-١٠-١٨) بعد أن عُرض السقفُ في شاشة
#: المستحقّات والرصيدُ بعدها في دفتر اللوحة، وكُتبت علّةُ الصفرَين بالبناء في `DELIBERATE`
WIRE_ONLY_NAMES = frozenset({"price_to_pay", "net", "tips", "cap", "total", "total_rewarded"})
WIRE_ONLY_SUFFIXES = ("_earnings", "_repaid", "_collected")

# **استثناءاتٌ مسمّاةٌ بسببها** — لا كنسٌ صامت:
# `discount_value` نسبةٌ مئوية، و`max_discount` سقفٌ قد يكون `null`،
# و`total_budget` مبلغٌ يقبل `null` (يُفحص حين لا يكون فارغاً).
NOT_MONEY = frozenset({"discount_value", "duration_min", "distance_km"})

DECIMAL_TEXT = re.compile(r"^-?\d+(\.\d+)?$")

#: العملاتُ التي تُصاغ — **ما خاناتُه أقلُّ من خانات التخزين وحدَه**
_SHORT: dict[str, int] = {
    currency.value: places for currency, places in CURRENCY_DECIMALS.items() if places < STORAGE_DECIMALS
}
#: **ودولُها** — صفٌّ يحمل دولتَه بلا عملة (إعداداتُ السوق في اللوحة) يُصاغ بعملة دولته
_SHORT_COUNTRIES: tuple[str, ...] = tuple(
    country.value for country, currency in COUNTRY_CURRENCY.items() if currency.value in _SHORT
)
#: **ما يفتح الوسيطُ الجسمَ لأجله** — رمزُ عملةٍ منها أو دولتِها نصّاً بين علامتي تنصيص
MARKERS: tuple[bytes, ...] = tuple(f'"{code}"'.encode() for code in (*_SHORT, *_SHORT_COUNTRIES))


def is_money_key(key: str) -> bool:
    if key in NOT_MONEY:
        return False
    return key in MONEY_NAMES or key.endswith(MONEY_SUFFIXES) or key in WIRE_ONLY_NAMES or key.endswith(WIRE_ONLY_SUFFIXES)


def currency_in(mapping: dict) -> str | None:
    """عملةُ الكائن نفسِه — `currency` أوّلاً ثمّ أيُّ `…_currency` **ثمّ عملةُ `country_code`** — أو `None`.

    **والدولةُ آخرُ ما يُقرأ**: صفُّ إعداداتِ سوقٍ (سعرُ الساعة، حدودُ المحفظة) يحمل دولتَه وحدَها، وعملتُه من بيتها
    (`COUNTRY_CURRENCY`) لا من شرط — **فيُصاغ «500» لصفِّ الجزائر**، وصفُّ الأردن وليبيا بثلاث خاناته كما كان.
    """
    value = mapping.get("currency")
    if isinstance(value, str) and value in Currency._value2member_map_:
        return value
    for key, value in mapping.items():
        if isinstance(key, str) and key.endswith("_currency") and isinstance(value, str):
            if value in Currency._value2member_map_:
                return value
    country = mapping.get("country_code")
    if isinstance(country, str) and country in CountryCode._value2member_map_:
        return COUNTRY_CURRENCY[CountryCode(country)].value
    return None


def _trimmed(text: str, places: int) -> str:
    """يحذف الأصفارَ بعد خانات العملة — **ولا يمسّ نصّاً فيه غيرُ الصفر هناك**."""
    whole, dot, fraction = text.partition(".")
    if not dot or len(fraction) <= places or fraction[places:].strip("0"):
        return text
    return f"{whole}.{fraction[:places]}" if places else whole


def normalize(payload: Any, currency: str | None = None) -> Any:
    """**الحمولةُ بصيغة عملاتها** — وهي هي (الكائنُ نفسُه) حين لا يتغيّر فيها شيء."""
    if isinstance(payload, dict):
        here = currency_in(payload) or currency
        places = _SHORT.get(here) if here is not None else None
        changed: dict | None = None
        for key, value in payload.items():
            new = value
            if (
                places is not None
                and isinstance(value, str)
                and isinstance(key, str)
                and is_money_key(key)
                and DECIMAL_TEXT.match(value)
            ):
                new = _trimmed(value, places)
            elif (
                places is not None
                and isinstance(value, list)
                and isinstance(key, str)
                and is_money_key(key)
                and value
                and all(isinstance(item, str) and DECIMAL_TEXT.match(item) for item in value)
            ):
                # **قائمةُ مبالغ** (`topup_choices`) — كلُّ عنصرٍ بعملة سياقه، والقائمةُ هي هي إن لم يتغيّر عنصر
                trimmed = [_trimmed(item, places) for item in value]
                new = value if trimmed == value else trimmed
            elif isinstance(value, (dict, list)):
                new = normalize(value, here)
            if new is not value:
                if changed is None:
                    changed = dict(payload)
                changed[key] = new
        return payload if changed is None else changed
    if isinstance(payload, list):
        out: list | None = None
        for index, item in enumerate(payload):
            new = normalize(item, currency)
            if new is not item:
                if out is None:
                    out = list(payload)
                out[index] = new
        return payload if out is None else out
    return payload


class MoneyWireMiddleware:
    """**وسيطُ ASGI يصوغ جسمَ JSON بعملاته** — ولا يفتح إلا جسماً يذكر عملةً قصيرة الخانات نصّاً.

    **ولمَ وسيطٌ لا صنفُ ردٍّ افتراضيّ**: FastAPI يسلسل بـ`dump_json` السريع ما دام الصنفُ افتراضيّاً، وصنفٌ مخصَّصٌ يُطفئه **على
    كلِّ باب** فيغيّر مسارَ تسلسلِ كلِّ جوابٍ أردنيٍّ وليبيّ؛ والوسيطُ يترك ذلك كلَّه كما هو ويمرّر الجسمَ بايتاً بايتاً.
    """

    def __init__(self, app) -> None:  # noqa: ANN001
        self.app = app

    async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001
        if scope["type"] != "http" or not MARKERS:
            await self.app(scope, receive, send)
            return

        held: dict | None = None
        chunks: list[bytes] = []
        passthrough = False

        async def wrapped(message) -> None:  # noqa: ANN001
            nonlocal held, passthrough
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers") or [])
                if not headers.get(b"content-type", b"").startswith(b"application/json"):
                    passthrough = True
                    await send(message)
                    return
                held = message
                return
            if message["type"] != "http.response.body" or passthrough or held is None:
                await send(message)
                return
            chunks.append(message.get("body", b""))
            if message.get("more_body", False):
                return
            body = b"".join(chunks)
            if any(marker in body for marker in MARKERS):
                try:
                    data = json.loads(body)
                except ValueError:  # pragma: no cover — جسمٌ غيرُ مقروءٍ ليس شأنَه
                    data = None
                if data is not None:
                    shaped = normalize(data)
                    if shaped is not data:
                        body = json.dumps(
                            shaped, ensure_ascii=False, allow_nan=False, separators=(",", ":")
                        ).encode()
                        held["headers"] = [
                            (name, str(len(body)).encode() if name == b"content-length" else value)
                            for name, value in held.get("headers") or []
                        ]
            await send(held)
            await send({"type": "http.response.body", "body": body, "more_body": False})

        await self.app(scope, receive, wrapped)
