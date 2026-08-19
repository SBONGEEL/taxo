from __future__ import annotations

from app.models.enums import CountryCode, Currency

# لكل سوق عملته الواحدة — لا حاجة لعمود عملة في كل جدول يرتبط بدولة
COUNTRY_CURRENCY: dict[CountryCode, Currency] = {
    CountryCode.LY: Currency.LYD,
    CountryCode.JO: Currency.JOD,
}


def currency_for_country(country_code: CountryCode) -> Currency:
    return COUNTRY_CURRENCY[CountryCode(country_code)]


# **اسمُ الدولة بيتُه هنا** (SPEC §24): كان مكتوباً في ترويسة اللوحة وحدَها،
# فصار يُنشر مع الدول — وواجهةٌ تكتب أسماءَها تُصبح بيتاً ثانياً يفترق عند
# إضافة سوقٍ ثالث.
COUNTRY_NAME: dict[CountryCode, str] = {
    CountryCode.JO: "الأردن",
    CountryCode.LY: "ليبيا",
}
