"""**حارسُ الكتابة: لا مالَ بكسرٍ في عملةٍ بلا كسور** (SPEC §٧٣-ج/٧) — في الجلسة، قبل كلِّ `flush`.

**لماذا هنا لا في كلِّ باب**: مالُ السوق يُكتب من عشرات الأبواب — إعداداتُ اللوحة (التسعيرة · الرسوم · الحدود · الخطط) ومبالغُ
تُحسب (أجرةٌ · عمولةٌ · خصمٌ). **وحارسٌ في كلِّ بابٍ حارسٌ ينساه البابُ القادم**؛ والجلسةُ يمرّ بها كلُّ ما يُكتب. فيُفحص كلُّ
عمودِ مالٍ (`NUMERIC(12,3)`) **في صفٍّ يحمل دولتَه أو عملتَه**، بخانات تلك العملة.

**ولا عملَ له إلا حيث العملةُ أقلُّ من ثلاث خانات** — يعود قبل أن يقرأ عموداً واحداً في صفٍّ أردنيٍّ أو ليبيّ، **فلا يتغيّر
سلوكُ السوقين بسطر**. **ولا يُصلح شيئاً**: كسرٌ جزائريٌّ وصل إلى هنا يُردّ بنصٍّ يسمّي العمود — **إمّا مدخلٌ لم يُفحص** (يُردّ
كما يُردّ كلُّ مدخلٍ خاطئ) **وإمّا حسابٌ لم يمرّ بعملته** (`round_money(…, العملة)`) فيُرى ولا يُبتلع.

**وما لا يراه — مكتوبٌ لا مسكوتٌ عنه**:
- **صفوفٌ بلا دولةٍ ولا عملة** (الدفتر · طلباتُ الشحن والسحب · حجوزُ بين المدن · اشتراكاتُ الكباتن): الدفترُ يحرسه بابُه الواحد
  (`wallet.record`)، والباقي يُكتب من مبالغ مرّت بعملتها.
- **والمعدّلاتُ** (`RATE_COLUMNS`) — سعرُ الكيلومتر والدقيقة وقيمةُ الخصم (نسبةً أو مبلغاً): **مضروبٌ فيه لا مدفوع**، وربعُ دينارٍ
  جزائريٍّ للدقيقة معدّلٌ صحيح؛ ما يُحسب به هو الذي يُقرَّب.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Numeric, event, inspect
from sqlalchemy.orm import Session

from app.core.currency import (
    STORAGE_DECIMALS,
    currency_for_country,
    decimals_of,
    is_precise,
    money_text,
)
from app.core.exceptions import InvalidInput
from app.models.enums import CountryCode, Currency

#: **أعمدةُ مالٍ ليست مبالغ** — كلٌّ بعلّته، والجديدُ يُفحص افتراضاً (القائمةُ استثناءٌ لا إذن).
RATE_COLUMNS: frozenset[str] = frozenset(
    {
        # معدّلاتٌ تُضرب في كيلومتراتٍ أو دقائق — والناتجُ يُقرَّب بعملته
        "price_per_km",
        "price_per_min",
        "stop_price_per_min",
        "pause_price_per_min",
        "stop_price_per_min_at_ride",
        "pause_price_per_min_at_ride",
        "price_per_min_at_pause",
        # قيمةُ الخصم نسبةً أو مبلغاً بحسب نوعه (`discount_type`) — ونسبةُ ١٢٫٥٪ صحيحة
        "discount_value",
        "promo_value_at_ride",
        # هدفُ المهمّة عددٌ أو مبلغٌ بمقياس مقياسه (`mission.METRIC_SCALE`) لا بخانات العملة
        "target",
    }
)

_COLUMNS: dict[type, tuple[str, ...]] = {}


def _money_columns(cls: type) -> tuple[str, ...]:
    """أعمدةُ `NUMERIC(12,3)` في النموذج — تُحسب مرّةً لكلِّ صنف."""
    if cls not in _COLUMNS:
        table = getattr(cls, "__table__", None)
        names: list[str] = []
        if table is not None:
            for column in table.columns:
                kind = column.type
                if (
                    isinstance(kind, Numeric)
                    and kind.precision == 12
                    and kind.scale == 3
                    and column.key not in RATE_COLUMNS
                ):
                    names.append(column.key)
        _COLUMNS[cls] = tuple(names)
    return _COLUMNS[cls]


def _currency_of(loaded: dict) -> Currency | None:
    """عملةُ الصفّ **من حالته المحمَّلة وحدَها** — `getattr` على حقلٍ منتهٍ يُحمِّل كسولاً داخل `flush` فيسقط بـ`MissingGreenlet`."""
    currency = loaded.get("currency")
    if currency is not None:
        try:
            return Currency(currency)
        except ValueError:  # pragma: no cover — عمودٌ اسمُه `currency` لغير العملة
            return None
    country = loaded.get("country_code")
    if country is not None:
        try:
            return currency_for_country(CountryCode(country))
        except (KeyError, ValueError):  # pragma: no cover
            return None
    return None


def check(session: Session) -> None:
    for obj in (*session.new, *session.dirty):
        loaded = inspect(obj).dict
        currency = _currency_of(loaded)
        if currency is None or decimals_of(currency) >= STORAGE_DECIMALS:
            continue
        for key in _money_columns(type(obj)):
            value = loaded.get(key)
            if value is None:
                continue
            if not is_precise(Decimal(value), currency):
                raise InvalidInput(
                    f"المبلغُ بـ{currency.value} بلا كسور — «{key}» = {money_text(Decimal(value), currency)}",
                    field=key,
                )


@event.listens_for(Session, "before_flush")
def _before_flush(session: Session, flush_context, instances) -> None:  # noqa: ANN001
    check(session)
