"""**سحبُ الكبتن الليبيّ** (قرارُ المالك ٢٠٢٦-١١-١١، البند ٤): التحويلُ البنكيُّ وحدَه بلا كليك، وبرقم حسابٍ أو IBAN يُجمَّد على الطلب.

ليبيا مغلقةٌ للتسجيل، فالقياسُ على الدالّتين اللتين يمرّ بهما كلُّ طلب (`methods_for` ثمّ `payout_destination`) — والبابُ نفسُه
مقيسٌ للجزائر في `test_algeria_withdrawals.py`.
"""

from __future__ import annotations

import pytest

from app.core.exceptions import InvalidInput
from app.models.enums import CountryCode, WithdrawalMethod
from app.services import withdrawals


def test_libya_offers_bank_transfer_only_and_never_cliq() -> None:
    assert withdrawals.methods_for(CountryCode.LY) == (WithdrawalMethod.BANK,)
    assert WithdrawalMethod.CLIQ not in withdrawals.methods_for(CountryCode.LY)


def test_jordan_and_algeria_are_unchanged() -> None:
    assert withdrawals.methods_for(CountryCode.JO) == (WithdrawalMethod.CLIQ, WithdrawalMethod.BANK)
    assert withdrawals.methods_for(CountryCode.DZ) == (
        WithdrawalMethod.BARIDIMOB,
        WithdrawalMethod.CCP,
        WithdrawalMethod.BANK,
        WithdrawalMethod.CASH_OFFICE,
    )
    assert withdrawals.payout_destination(CountryCode.JO, WithdrawalMethod.BANK, "123456", "أحمد علي") == (None, None)


@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        ("LY83 0020 4800 0000 0000 0000 1", "LY83002048000000000000001"),
        ("ly83-002048-000000", "LY83002048000000"),
        ("٠٠١٢٣٤٥٦٧٨٩", "00123456789"),
    ],
)
def test_the_libyan_account_is_normalised_and_frozen_with_its_holder(raw: str, stored: str) -> None:
    account, holder = withdrawals.payout_destination(CountryCode.LY, WithdrawalMethod.BANK, raw, "  محمد   علي ")
    assert account == stored
    assert holder == "محمد علي"


@pytest.mark.parametrize("raw", [None, "", "12345", "رقم حسابي", "LY12#45678", "1" * 35])
def test_a_wrong_or_missing_libyan_account_is_refused(raw: str | None) -> None:
    with pytest.raises(InvalidInput) as caught:
        withdrawals.payout_destination(CountryCode.LY, WithdrawalMethod.BANK, raw, "محمد علي")
    assert caught.value.extra["field"] == "payout_account"


def test_a_missing_holder_is_refused() -> None:
    with pytest.raises(InvalidInput) as caught:
        withdrawals.payout_destination(CountryCode.LY, WithdrawalMethod.BANK, "LY83002048000000", " ")
    assert caught.value.extra["field"] == "payout_holder"
