"""المنبعُ الرابعُ للخطأ، والرقمُ المرجعيّ، وحجبُ الرقم في السجل (2026-09-20).

**ثلاثةُ أشياءٍ كان غيابُها يُقرأ في مكانٍ واحد**: هاتفُ إنسانٍ يعرض رسالةً
عامّة، وسجلٌّ لا يحمل حرفاً مشتركاً معها، ورقمُ هاتفٍ كاملٌ في ذلك السجل.
"""

from __future__ import annotations


import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.middleware.cors import CORSMiddleware

from app.core.exceptions import register_exception_handlers
from app.core.phone import mask_phone
from app.core.request_id import HEADER, RequestIdMiddleware
from app.main import app


# --------------------------------------------------------------- حجبُ الرقم


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+962791234567", "+962…567"),
        ("0791234567", "…567"),
        ("+218912345678", "+218…678"),
        ("", "«لا رقم»"),
        (None, "«لا رقم»"),
        ("+96", "«رقمٌ غيرُ صالح»"),
        ("abc", "«رقمٌ غيرُ صالح»"),
    ],
)
def test_mask_phone_keeps_market_and_tail_only(raw: str | None, expected: str) -> None:
    assert mask_phone(raw) == expected


def test_mask_phone_never_returns_the_whole_number() -> None:
    """**الشرطُ الحقيقيُّ ليس الشكلَ بل ما لا يبقى**."""
    phone = "+962791234567"
    masked = mask_phone(phone)
    assert phone not in masked
    assert "791234" not in masked


async def test_firebase_mismatch_logs_masked_numbers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """السطرُ يبقى تحذيراً، **والرقمان لا يبقيان**.

    **ولا يمرّ القياسُ بنظام التسجيل أصلاً** (قِيس في CI مرّتين، 2026-09-20
    و2026-09-21): جُرِّب بـ`caplog` فجاء فارغاً، ثمّ بمِقبضٍ يُركَّب على
    مسجِّل الوحدة فجاء فارغاً أيضاً. **والسببُ لم يُثبت** — والمحاولتان
    كلتاهما تسألان **حالاً عامّةً** يمرّ بها ألفٌ وخمسُمئة اختبارٍ قبلها.

    **فصار المقياسُ ما يُمرَّر إلى النداء نفسِه**: يُستبدل `logger` بمُسجِّلٍ
    يحفظ الوسائط. لا مستوياتٌ، ولا انتشارٌ، ولا مِقابض — **ولا حالَ يملكها
    أحدٌ غيرُ هذا الاختبار**. وهو أيضاً أقربُ إلى الدعوى: الدعوى «ما يُكتب في
    السطر محجوب»، وهذه تقرأ السطرَ قبل أن يغادر.

    **ويصيح إن لم يُبلَغ الفرعُ أصلاً**: `assert calls` قبل كلِّ شيء —
    **واختبارٌ يمرّ لأن الشرطَ لم يقع أسوأُ من اختبارٍ يسقط**، وهو ما كان
    يمكن أن يقع هنا لولا هذه الدعوى.
    """
    from app.services.auth import firebase_identity
    from app.services.firebase_auth import InvalidIdToken, VerifiedIdentity

    token_phone = "+962791111111"
    asked_phone = "+962792222222"

    class _Verifier:
        async def verify(self, _token: str) -> VerifiedIdentity:
            return VerifiedIdentity(
                phone=token_phone,
                provider_uid="uid-xyz",
                sign_in_provider="phone",
            )

    async def _get_verifier(_session: object) -> _Verifier:
        return _Verifier()

    monkeypatch.setattr(firebase_identity, "get_verifier", _get_verifier)

    calls: list[tuple] = []

    class _Recorder:
        """يحفظ الوسائطَ كما وصلت — ولا يكتب شيئاً في أيِّ مكان."""

        def warning(self, *args: object, **kwargs: object) -> None:
            calls.append((args, kwargs))

    monkeypatch.setattr(firebase_identity, "logger", _Recorder())

    with pytest.raises(InvalidIdToken):
        await firebase_identity.verify_phone_ownership(
            None, phone=asked_phone, id_token="whatever"
        )

    # **أوّلاً: أوُقع الفرعُ أصلاً؟** — وبغير هذه الدعوى يمرّ الاختبارُ فارغاً
    assert calls, "لم يُنادَ التحذيرُ — الفرعُ لم يُبلَغ، والاختبارُ لا يقيس شيئاً"
    assert len(calls) == 1, f"نداءٌ واحدٌ يُنتظر، ووصل {len(calls)}"

    args, _kwargs = calls[0]
    rendered = args[0] % tuple(args[1:])

    assert token_phone not in rendered, "الرقمُ الكاملُ ما زال في السطر"
    assert asked_phone not in rendered, "الرقمُ الكاملُ ما زال في السطر"
    assert "+962…111" in rendered and "+962…222" in rendered
    # **و`provider_uid` يبقى عارياً بقصد** — هو مُعرِّفُ المزوّد لا رقمَ هاتف
    assert "uid-xyz" in rendered


# ------------------------------------------------- المنبعُ الرابعُ والمُعرِّف


def _probe_app() -> FastAPI:
    """تطبيقٌ صغيرٌ بنفس تركيب الحقيقيّ — **لأن الحقيقيَّ لا بابَ فيه يرمي**."""
    probe = FastAPI()
    register_exception_handlers(probe)
    probe.add_middleware(RequestIdMiddleware)

    @probe.get("/boom")
    async def _boom() -> dict[str, str]:
        raise RuntimeError("انفجارٌ مقصودٌ في اختبار")

    @probe.get("/ok")
    async def _ok() -> dict[str, str]:
        return {"status": "ok"}

    return probe


async def test_unexpected_exception_answers_with_the_contract() -> None:
    """**لا نصَّ عارياً**: `code` و`message` عربيةً و`request_id` يُبحث به."""
    transport = ASGITransport(app=_probe_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://probe") as ac:
        response = await ac.get("/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "server_error"
    assert body["message"] == "خطأٌ في الخادم — أعد المحاولة"
    assert body["request_id"]
    # **والجسمُ والرأسُ يقولان الشيءَ نفسَه** — وإلا لم يصل شيءٌ يُبحث به
    assert response.headers[HEADER] == body["request_id"]


async def test_every_response_carries_a_request_id() -> None:
    """ولا يقتصر على السقوط: الناجحُ يحمله أيضاً فيُقرَن طلبٌ بسطرٍ.

    **والمِجَسُّ لا القاعدة**: طرقُ `/health` بالمحرّك الحقيقيّ يفتح وصلاتٍ
    تبقى في المسبح، فيسقط `DROP DATABASE` في تفكيك الجلسة — عطبٌ في الاختبار
    يُقرأ عطباً في الكود. والوسيطُ هو المقيس، وهو نفسُه هنا وهناك.
    """
    transport = ASGITransport(app=_probe_app())
    async with AsyncClient(transport=transport, base_url="http://probe") as ac:
        response = await ac.get("/ok")

    assert response.status_code == 200
    assert len(response.headers[HEADER]) == 16


async def test_two_requests_get_two_different_ids() -> None:
    transport = ASGITransport(app=_probe_app())
    async with AsyncClient(transport=transport, base_url="http://probe") as ac:
        first = await ac.get("/ok")
        second = await ac.get("/ok")

    assert first.headers[HEADER] != second.headers[HEADER]


def test_the_real_app_registers_the_fourth_handler() -> None:
    """**الوصلُ يُقاس لا يُفترض** — معالجٌ مكتوبٌ وغيرُ مركَّبٍ لا يفعل شيئاً."""
    assert Exception in app.exception_handlers
    assert any(item.cls is RequestIdMiddleware for item in app.user_middleware)


def test_cors_exposes_the_request_id_header() -> None:
    """**ورأسٌ غيرُ مُصرَّحٍ هنا لا يقرؤه متصفّحٌ ولو وصل** — فالفحصُ عليه."""
    cors = next(item for item in app.user_middleware if item.cls is CORSMiddleware)
    exposed = cors.kwargs.get("expose_headers") if hasattr(cors, "kwargs") else None
    assert exposed and HEADER in exposed
