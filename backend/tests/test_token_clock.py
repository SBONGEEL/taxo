"""**سماحُ الساعة عند فكّ الرمز** (قِيس ٢٠٢٦-١٠-٠٧) — رمزٌ سُكّ لتوّه لا يُردّ لأن الساعةَ رجعت خطوة.

**قِيس في حاوية التطوير**: ساعتُها رجعت أربعَ مرّاتٍ في دقيقة (أكبرُها ٠٫٤٣٥ ث)، و`iat` يُقطع إلى الثانية — فرمزٌ سُكّ بعد حدّ الثانية
بقليلٍ ثمّ رجعت الساعةُ قبله صار «لم يصلح بعد» عند PyJWT، **فرُدّ الطلبُ التالي ٤٠١** (رآه «كبتنان معاً» و«السقف عند نشوء الدَّين»).

**والحدُّ في الاتجاهين**: ثوانٍ تُقبل، **ودقيقةٌ في المستقبل تُرفض** — فالسماحُ يسع الساعةَ ولا يفتح باباً لرمزٍ مزوَّرِ الزمن.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import TokenError, _create_token, decode_token


def _access_issued(at: datetime) -> str:
    token, _jti, _exp = _create_token("user-1", "access", timedelta(minutes=30), None, issued_at=at)
    return token


def test_a_token_issued_a_moment_ahead_of_the_clock_is_accepted() -> None:
    """**ساعةٌ رجعت ثانيتين** بعد السكّ — الرمزُ يُقبل (كان يُردّ «لم يصلح بعد»)."""
    payload = decode_token(_access_issued(datetime.now(UTC) + timedelta(seconds=2)), "access")
    assert payload["sub"] == "user-1"


def test_a_token_from_a_minute_in_the_future_is_still_refused() -> None:
    """**والسماحُ ليس باباً**: رمزٌ زمنُه بعد دقيقةٍ يُردّ كما كان."""
    with pytest.raises(TokenError):
        decode_token(_access_issued(datetime.now(UTC) + timedelta(seconds=60)), "access")
