from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.models.enums import CountryCode, Currency

# لكل سوق عملته الواحدة — لا حاجة لعمود عملة في كل جدول يرتبط بدولة
COUNTRY_CURRENCY: dict[CountryCode, Currency] = {
    CountryCode.LY: Currency.LYD,
    CountryCode.JO: Currency.JOD,
    CountryCode.DZ: Currency.DZD,
}


def currency_for_country(country_code: CountryCode) -> Currency:
    return COUNTRY_CURRENCY[CountryCode(country_code)]


def country_for_currency(currency: Currency | str) -> CountryCode:
    """**الدولةُ من عملتها** — عكسُ الجدول نفسِه لا شرطٌ بدولة (كان `"JO" if JOD else "LY"` في `cliq_qr`)."""
    wanted = Currency(currency)
    return next(country for country, value in COUNTRY_CURRENCY.items() if value is wanted)


# **اسمُ الدولة بيتُه هنا** (SPEC §24): كان مكتوباً في ترويسة اللوحة وحدَها،
# فصار يُنشر مع الدول — وواجهةٌ تكتب أسماءَها تُصبح بيتاً ثانياً يفترق عند
# إضافة سوقٍ ثالث.
COUNTRY_NAME: dict[CountryCode, str] = {
    CountryCode.JO: "الأردن",
    CountryCode.LY: "ليبيا",
    CountryCode.DZ: "الجزائر",
}


# ------------------------------------------------------------------ خاناتُ العملة (SPEC §٧٣-ج/٢)
#
# **أصغرُ وحدةٍ للمال نفسِه في كلِّ عملة** — بها يُحسب كلُّ مبلغٍ ويُقيَّد في الدفتر، وبها يُصاغ على السلك وفي النصّ.
# **وليست تقريبَ §٧٠**: ذاك سياسةٌ على ما يدفعه الشخصُ فوقها (`services/rounding.py`)، ووحدتُه مضاعفٌ لهذه.
#
# **والأردنيُّ والليبيُّ ثلاثٌ كما كانا حرفاً، والجزائريُّ صفر** (قرارُ المالك ٢٠٢٦-١٠-١١: «150 د.ج»).
CURRENCY_DECIMALS: dict[Currency, int] = {
    Currency.LYD: 3,
    Currency.JOD: 3,
    Currency.DZD: 0,
}

#: **علامةُ العملة كما تُرسم بعد المبلغ** — كانت مكتوبةً في الواجهات الثلاث (خمسَ مرّاتٍ ومرّةً في الخلفية)، فصارت تُنشر مع الدولة.
CURRENCY_LABEL: dict[Currency, str] = {
    Currency.JOD: "د.أ",
    Currency.LYD: "د.ل",
    Currency.DZD: "د.ج",
}

#: **اسمُ العملة كاملاً** — سطرٌ تحت المبلغ الكبير في طبقة الدفع.
CURRENCY_NAME: dict[Currency, str] = {
    Currency.JOD: "دينار أردني",
    Currency.LYD: "دينار ليبي",
    Currency.DZD: "دينار جزائري",
}

#: **دقّةُ التخزين** (`NUMERIC(12,3)`) — أوسعُ خانات العملات. **كلُّ مبلغٍ في بايثون يُحمل بها** أيّاً كانت عملتُه، فلا
#: يختلط مقياسان في جمع؛ وخاناتُ العملة تحكم **القيمة** (`round_to_currency`) **والصيغة** على السلك وفي النصّ (`money_text`).
STORAGE_STEP = Decimal("0.001")
STORAGE_DECIMALS = 3


def decimals_of(currency: Currency | str) -> int:
    return CURRENCY_DECIMALS[Currency(currency)]


def step_of(currency: Currency | str) -> Decimal:
    """أصغرُ وحدةٍ في العملة — `0.001` للأردنيّ والليبيّ و`1` للجزائريّ."""
    return Decimal(1).scaleb(-decimals_of(currency))


def round_to_currency(amount: Decimal, currency: Currency | str) -> Decimal:
    """**تقريبُ مبلغٍ محسوبٍ إلى أصغر وحدةٍ في عملته** — نصفُه للأعلى، **ويعود بدقّة التخزين**.

    للأردنيّ والليبيّ هي `quantize(0.001, ROUND_HALF_UP)` التي كانت `round_money` حرفاً؛ وللجزائريّ دينارٌ صحيح
    (`150.5 ⇐ 151.000`). **والعملةُ إلزاميّةٌ لا افتراض** (SPEC §٧٣-ج/٤): افتراضٌ يقع على ثلاث خاناتٍ لمن نسيها يستر
    العطبَ الذي وُجد هذا البيتُ لأجله.
    """
    return amount.quantize(step_of(currency), rounding=ROUND_HALF_UP).quantize(STORAGE_STEP)


def is_precise(amount: Decimal, currency: Currency | str) -> bool:
    """هل المبلغُ بخانات عملته؟ — كلُّ مبلغٍ بثلاث خاناتٍ دقيقٌ للأردنيّ والليبيّ، والجزائريُّ دينارٌ صحيح."""
    return Decimal(amount) % step_of(currency) == 0


def money_text(amount: Decimal, currency: Currency | str) -> str:
    """**المبلغُ نصّاً بخانات عملته** — «1.500» للأردنيّ و«150» للجزائريّ، بخاناتٍ لاتينيّة.

    **ولا يُصلح كسراً**: مبلغٌ جزائريٌّ فيه كسرٌ يُكتب بدقّة التخزين كما هو (`150.500`) — فيراه من يقرأ ولا يُبتلع
    (الشكلُ الثاني عشر: احتياطٌ يعمل فيخفي العطب).
    """
    value = Decimal(amount)
    if is_precise(value, currency):
        return f"{value.quantize(step_of(currency)):f}"
    return f"{value.quantize(STORAGE_STEP):f}"
