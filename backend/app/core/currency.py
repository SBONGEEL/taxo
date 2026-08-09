from __future__ import annotations

from app.models.enums import CountryCode, Currency

# لكل سوق عملته الواحدة — لا حاجة لعمود عملة في كل جدول يرتبط بدولة
COUNTRY_CURRENCY: dict[CountryCode, Currency] = {
    CountryCode.LY: Currency.LYD,
    CountryCode.JO: Currency.JOD,
}


def currency_for_country(country_code: CountryCode) -> Currency:
    return COUNTRY_CURRENCY[CountryCode(country_code)]
