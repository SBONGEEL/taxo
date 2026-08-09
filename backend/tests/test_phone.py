from __future__ import annotations

import pytest

from app.core.phone import InvalidPhoneNumber, normalize_phone, resolve_phone
from app.models.enums import CountryCode


@pytest.mark.parametrize(
    ("raw", "country", "expected"),
    [
        ("0791234567", CountryCode.JO, "+962791234567"),
        ("791234567", CountryCode.JO, "+962791234567"),
        ("00962791234567", CountryCode.JO, "+962791234567"),
        ("+962 79 123-4567", CountryCode.JO, "+962791234567"),
        ("0912345678", CountryCode.LY, "+218912345678"),
        ("+218 91 234 5678", CountryCode.LY, "+218912345678"),
    ],
)
def test_normalize_phone(raw: str, country: CountryCode, expected: str) -> None:
    assert normalize_phone(raw, country) == expected


@pytest.mark.parametrize(
    ("raw", "country"),
    [
        ("079123456", CountryCode.JO),      # قصير
        ("07912345678", CountryCode.JO),    # طويل
        ("0612345678", CountryCode.JO),     # بادئة غير مسموحة
        ("abcdefghij", CountryCode.JO),
        ("", CountryCode.LY),
    ],
)
def test_normalize_phone_rejects_invalid(raw: str, country: CountryCode) -> None:
    with pytest.raises(InvalidPhoneNumber):
        normalize_phone(raw, country)


def test_resolve_phone_infers_country_from_dial_code() -> None:
    assert resolve_phone("+962791234567") == "+962791234567"
    assert resolve_phone("00218912345678") == "+218912345678"


def test_resolve_phone_requires_country_for_local_format() -> None:
    with pytest.raises(InvalidPhoneNumber):
        resolve_phone("0791234567")
