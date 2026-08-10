from __future__ import annotations

import re

from app.models.enums import CountryCode

# أطوال الأرقام الوطنية (بدون الصفر البادئ) وبادئة كل دولة
_COUNTRY_RULES: dict[CountryCode, tuple[str, tuple[int, ...], tuple[str, ...]]] = {
    # code: (dial_code, national_lengths, allowed_prefixes)
    CountryCode.LY: ("218", (9,), ("9",)),   # 09X XXX XXXX
    CountryCode.JO: ("962", (9,), ("7",)),   # 07X XXX XXXX
}

_NON_DIGITS = re.compile(r"[\s\-()._]")


class InvalidPhoneNumber(ValueError):
    """رقم هاتف لا يطابق قواعد الدولة."""


def dial_code_for(country_code: CountryCode) -> str:
    """بادئة الدولة كما تراها الواجهات — من نفس الجدول الذي يطبّع به.

    تُنشر في `GET /config` لترسمها الواجهةُ ثابتةً أمام الحقل بدل أن تكتبها
    في كودها: بادئةٌ مكتوبةٌ في تطبيقين تفترق عن هذا الجدول يوماً، وتفترق
    عن نفسها في التطبيقين قبل ذلك.
    """
    return _COUNTRY_RULES[country_code][0]


def national_length_for(country_code: CountryCode) -> int:
    """طول الرقم الوطني بلا الصفر البادئ — تحدّ به الواجهةُ طولَ الحقل."""
    return _COUNTRY_RULES[country_code][1][0]


def normalize_phone(raw: str, country_code: CountryCode) -> str:
    """يُحوّل أي صيغة مدخلة إلى E.164 (`+962791234567`).

    يقبل: `0791234567`, `791234567`, `00962791234567`, `+962 79 123 4567`.
    التخزين والبحث يتمان بالصيغة المُطبّعة حصراً — الهاتف هو مُعرّف الدخول.
    """
    if not raw:
        raise InvalidPhoneNumber("رقم الهاتف مطلوب")

    dial_code, lengths, prefixes = _COUNTRY_RULES[country_code]

    value = _NON_DIGITS.sub("", raw.strip())
    if value.startswith("+"):
        value = value[1:]
    elif value.startswith("00"):
        value = value[2:]

    if not value.isdigit():
        raise InvalidPhoneNumber("رقم الهاتف يجب أن يحتوي أرقاماً فقط")

    if value.startswith(dial_code):
        national = value[len(dial_code):]
    elif value.startswith("0"):
        national = value[1:]
    else:
        national = value

    if len(national) not in lengths or not national.startswith(prefixes):
        raise InvalidPhoneNumber(
            f"رقم هاتف غير صالح لدولة {country_code.value}"
        )

    return f"+{dial_code}{national}"


def resolve_phone(raw: str, country_code: CountryCode | None = None) -> str:
    """تطبيع رقم عند الدخول حيث قد لا تُرسل الواجهة رمز الدولة.

    الأولوية: رمز الدولة الصريح، ثم استنتاجه من الصيغة الدولية (+962…).
    """
    if country_code is not None:
        return normalize_phone(raw, country_code)

    value = _NON_DIGITS.sub("", (raw or "").strip())
    if value.startswith("+"):
        value = value[1:]
    elif value.startswith("00"):
        value = value[2:]

    for code, (dial_code, _, _) in _COUNTRY_RULES.items():
        if value.startswith(dial_code):
            return normalize_phone(raw, code)

    raise InvalidPhoneNumber("أرسل الرقم بالصيغة الدولية أو حدّد رمز الدولة")
