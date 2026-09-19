"""ثغرةُ الرمز — رمزٌ لحسابٍ لا يُثبت ملكيةَ حسابٍ آخر بالرقم نفسِه (1-أ/5، `SPEC-DELIVERY.md` §D7).

**الثغرة**: مفاتيحُ الرمز الثلاثة كانت بالرقم وحده (`otp:code:{phone}` وأختاها)،
فبعد أن صار للرقم حسابٌ من كلِّ نوع (§D1.4) **يصلح رمزٌ طُلب لحساب الزبون
لاستعادة كلمة مرور حساب الراكب**. وهي ثغرةُ استيلاءٍ على حساب لا بندٌ تقني.

**والإغلاق**: الرمزُ يُحفظ ويُتحقّق منه بالرقم **والنوع**. **والسقوفُ الستُّ تبقى
على الرقم** — الشريحةُ واحدةٌ والكلفةُ واحدة.
"""

from __future__ import annotations

import pytest

from app.core.exceptions import InvalidOtpCode
from app.core.redis_client import get_redis_client
from app.models.enums import AccountKind
from app.services import otp, otp_limits

PHONE = "+962790000077"


class _Recorder:
    """مرسِلٌ يسجّل الرمزَ الذي وصل — على شكل `test_otp_template_isolation`."""

    provider_name = "recorder"

    def __init__(self) -> None:
        self.codes: list[str] = []

    async def send_code(
        self, to: str, code: str, *, ttl_minutes: int, purpose: str, body: str
    ) -> str:
        self.codes.append(code)
        return "recorded"


async def _issue(session_factory, kind: AccountKind) -> str:
    recorder = _Recorder()
    async with session_factory() as session:
        await otp.issue(
            session, get_redis_client(), PHONE, sender=recorder, account_kind=kind
        )
    return recorder.codes[-1]


async def test_a_code_issued_for_the_market_account_does_not_prove_the_taxo_one(
    session_factory,
) -> None:
    """**يحمرّ قبل الإغلاق**: رمزُ الزبون كان يُقبل للراكب بالرقم نفسِه."""
    code = await _issue(session_factory, AccountKind.MARKET)

    with pytest.raises(InvalidOtpCode):
        await otp.verify(get_redis_client(), PHONE, code, account_kind=AccountKind.TAXO)

    # وهو صالحٌ لحسابه هو — الإغلاقُ لا يكسر المسارَ الصحيح
    await otp.verify(get_redis_client(), PHONE, code, account_kind=AccountKind.MARKET)


async def test_a_code_issued_for_the_taxo_account_does_not_prove_the_market_one(
    session_factory,
) -> None:
    """والاتجاهُ الآخر: رمزُ الراكب لا يفتح حسابَ الزبون."""
    code = await _issue(session_factory, AccountKind.TAXO)

    with pytest.raises(InvalidOtpCode):
        await otp.verify(get_redis_client(), PHONE, code, account_kind=AccountKind.MARKET)

    await otp.verify(get_redis_client(), PHONE, code, account_kind=AccountKind.TAXO)


async def test_the_request_caps_stay_on_the_number(session_factory) -> None:
    """**السقوفُ على الشريحة لا على الحساب**: طلبان لنوعين يُعدّان في نافذةٍ واحدة."""
    await _issue(session_factory, AccountKind.TAXO)
    await get_redis_client().delete(otp_limits.RESEND_KEY.format(phone=PHONE))
    await _issue(session_factory, AccountKind.MARKET)

    counted = await get_redis_client().get(otp_limits.WINDOW_KEY.format(phone=PHONE))
    assert int(counted) == 2
    assert not await get_redis_client().exists(
        otp_limits.WINDOW_KEY.format(phone=f"{PHONE}:market")
    )


async def test_the_taxo_code_key_is_unchanged(session_factory) -> None:
    """**مفتاحُ `taxo` هو هو حرفاً** — فلا يسقط رمزٌ في الطريق ساعةَ الرفع."""
    await _issue(session_factory, AccountKind.TAXO)
    assert await get_redis_client().exists(f"otp:code:{PHONE}")
