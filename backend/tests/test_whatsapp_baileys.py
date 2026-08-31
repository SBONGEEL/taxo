"""القناةُ الذاتية لواتساب — البوابةُ وسقوفُها وارتدادُها (قرارُ المالك 2026-08-16).

**وما يُقاس هنا هو ما يمنع الحظرَ ويمنع البابَ المسدود**، لا أن النداء يمرّ:

* أن `transport` **وحدَه** يقرّر أيَّ سلكٍ يمشي عليه العقد، وأن غيابَه يبقي
  القناةَ الرسميةَ على حالها (فترقيةٌ لا تبدّل سلوكَ عقدٍ قائم).
* أن **السقوف تُقاس قبل السلك** — سقفٌ يُفحص بعد الإرسال سقفٌ لا يحمي شيئاً.
* أن **الفشلَ يرتدّ** إلى القناة التالية بدل أن يترك مستخدماً عالقاً.
* أن **البوابةَ لا تقبل نصّاً**: تأخذ رمزاً ورقماً، والنصُّ عندها — فوعدُ «بلا
  روابط» يحرسه من يملك السلك.
"""

from __future__ import annotations

import pytest

from app.core.redis_client import get_redis_client
from app.services.whatsapp import (
    TRANSPORT_BAILEYS,
    BaileysGatewayProvider,
    WhatsAppCloudProvider,
    WhatsAppError,
    WhatsAppNumberUnknown,
    build_provider,
)
from app.services.whatsapp.baileys import (
    DEFAULT_HOURLY,
    DEFAULT_PER_PHONE_HOURLY,
    HOUR_SECONDS,
)

CONTRACT = {
    "transport": TRANSPORT_BAILEYS,
    "gateway_url": "http://whatsapp-gateway:8080",
    "gateway_key": "test-key",
}


def _provider(**overrides) -> BaileysGatewayProvider:
    provider = build_provider({**CONTRACT, **overrides})
    assert isinstance(provider, BaileysGatewayProvider)
    return provider


class _Gateway:
    """بوابةٌ مُقلَّدة — **تسجّل ما وصلها**، فيُقاس ما يُرسل لا ما يُقال إنه أُرسل."""

    def __init__(self, *, status: int = 200, body: dict | None = None) -> None:
        self.status = status
        self.body = body if body is not None else {"reference": "wamid.TEST"}
        self.calls: list[tuple[str, str, dict | None]] = []

    async def __call__(self, method, path, *, json=None, params=None):
        self.calls.append((method, path, json if json is not None else params))
        return self.status, self.body


@pytest.fixture(autouse=True)
async def _clean_limits():
    """السقوفُ على Redis، والاختباراتُ تتشارك القاعدةَ نفسَها."""
    redis = get_redis_client()
    async for key in redis.scan_iter("ratelimit:whatsapp:*"):
        await redis.delete(key)
    yield
    async for key in redis.scan_iter("ratelimit:whatsapp:*"):
        await redis.delete(key)


# ------------------------------------------------------------ اختيارُ القناة


def test_the_transport_field_alone_decides_the_wire() -> None:
    """حقلٌ واحدٌ يبدّل القناة — **بلا كودٍ جديد ولا نشر** (شرطُ المالك)."""
    assert isinstance(_provider(), BaileysGatewayProvider)

    official = build_provider(
        {
            "phone_number_id": "1",
            "access_token": "t",
            "template_name": "otp",
            "transport": "cloud",
        }
    )
    assert isinstance(official, WhatsAppCloudProvider)


def test_a_contract_with_no_transport_stays_on_the_official_wire() -> None:
    """**الغيابُ يعني ما كان** لا ما استُحدث.

    عقدُ ميتا القائمُ لا يتبدّل سلوكُه بترقيةٍ تضيف حقلاً — ومن أراد الذاتيةَ
    كتبها. والعكسُ (غيابٌ يعني الأحدث) يحوّل قناةَ تسجيلٍ عاملةً بلا أن يطلب أحد.
    """
    provider = build_provider(
        {"phone_number_id": "1", "access_token": "t", "template_name": "otp"}
    )
    assert isinstance(provider, WhatsAppCloudProvider)


# ------------------------------------------------------------ السقوف


async def test_the_per_phone_cap_stops_before_the_wire(monkeypatch) -> None:
    """السقفُ يُقاس **قبل** النداء — وسقفٌ يُفحص بعده لا يحمي رقماً.

    ويُقاس بعدد ما وصل البوابةَ فعلاً، لا برمز الاستجابة: بوابةٌ استُدعيت ثم
    رُفض جوابُها **أرسلت رسالةً** — والحظرُ يقع على ما خرج لا على ما رُدّ.
    """
    provider = _provider(per_phone_hourly="2")
    gateway = _Gateway()
    monkeypatch.setattr(provider, "_call", gateway)

    await provider.send_code("+962790000021", "1111", ttl_minutes=5)
    await provider.send_code("+962790000021", "2222", ttl_minutes=5)
    with pytest.raises(WhatsAppError):
        await provider.send_code("+962790000021", "3333", ttl_minutes=5)

    assert len(gateway.calls) == 2

    # ورقمٌ آخر لا يُعاقَب بسقف غيره
    await provider.send_code("+962790000022", "4444", ttl_minutes=5)
    assert len(gateway.calls) == 3


async def test_the_hourly_cap_is_global_and_measured_in_an_hour(monkeypatch) -> None:
    provider = _provider(per_phone_hourly="0", hourly_limit="2")
    gateway = _Gateway()
    monkeypatch.setattr(provider, "_call", gateway)

    await provider.send_code("+962790000031", "1111", ttl_minutes=5)
    await provider.send_code("+962790000032", "2222", ttl_minutes=5)
    with pytest.raises(WhatsAppError):
        await provider.send_code("+962790000033", "3333", ttl_minutes=5)
    assert len(gateway.calls) == 2

    redis = get_redis_client()
    assert 0 < await redis.ttl("ratelimit:whatsapp:baileys:global") <= HOUR_SECONDS


async def test_a_written_zero_means_no_cap_but_an_empty_field_means_the_default(
    monkeypatch,
) -> None:
    """حالتان لا يحملهما حقلٌ واحد — درسُ أصفار `wallet_settings`."""
    unlimited = _provider(per_phone_hourly="0", hourly_limit="0")
    gateway = _Gateway()
    monkeypatch.setattr(unlimited, "_call", gateway)
    for index in range(6):
        await unlimited.send_code("+962790000041", str(1000 + index), ttl_minutes=5)
    assert len(gateway.calls) == 6

    # **يُقارَن بالثابت نفسِه لا برقمٍ منسوخ.** كان الرقمُ ٣ مكتوباً هنا، فرفعه
    # المالكُ إلى ٢٠ في `0525bdb` وبقي الاختبارُ على القديم — **فظلَّت المجموعةُ
    # حمراءَ على master** بينما `CLAUDE.md` يقول «صفرُ إخفاقات». وقيمةٌ واحدةٌ
    # في بيتين تفترقان عند أوّل تعديل؛ والمقصودُ هنا «الفارغُ يعني الافتراضي»
    # لا «الافتراضيُّ رقمٌ بعينه».
    default = _provider(per_phone_hourly="", hourly_limit="")
    assert default._per_phone_hourly == DEFAULT_PER_PHONE_HOURLY
    assert default._hourly == DEFAULT_HOURLY


# ------------------------------------------------------------ الأسلاك


async def test_the_gateway_is_handed_the_text_and_the_purpose(monkeypatch) -> None:
    """**الحارسُ انتقل ولم يُحذف** (قرارُ المالك 2026-08-19، SPEC §19.1).

    كان هذا الاختبار يحرس «لا نصَّ يُسلَّم أبداً»، وكانت صياغةُ البوابة هي ما
    يحمل وعدَ «بلا روابط». والوعدُ المقصودُ لم يكن «البوابةُ تصوغ» بل **«لا يخرج
    على السلك ما يخالف الشروط»** — وهو الآن محروسٌ عندها **بالفحص**
    (`whatsapp-gateway/src/template.js::chooseText`) وعند الحفظ في اللوحة، من
    ملفِّ شروطٍ واحدٍ يقرؤه الاثنان.

    فما يُحرس هنا صار: أنّ النصَّ يصل **ومعه هويّةُ قالبه** — بغيرها يصير سؤالُ
    «أيُّ قالبٍ خالف؟» بلا جوابٍ في سجلّ البوابة.
    """
    provider = _provider()
    gateway = _Gateway()
    monkeypatch.setattr(provider, "_call", gateway)

    await provider.send_code(
        "+962790000051",
        "9182",
        ttl_minutes=7,
        purpose="password_reset",
        body="رمزك 9182",
    )
    method, path, body = gateway.calls[0]
    assert (method, path) == ("POST", "/send")
    assert body == {
        "to": "+962790000051",
        "code": "9182",
        "ttl_minutes": 7,
        "purpose": "password_reset",
        "body": "رمزك 9182",
        # **التصريحُ بالإرسال** — بابُ البوابة افتراضُه ألّا يخرج شيءٌ على السلك
        "deliver": True,
    }


async def test_a_dead_session_raises_so_the_chain_can_fall_back(monkeypatch) -> None:
    """سقوطُ الجلسة **خطأٌ يرتدّ** لا نجاحٌ صامت.

    و`WhatsAppError` بعينه هو ما تلتقطه طبقةُ التحقق لتعرض القناةَ التالية —
    فنجاحٌ كاذبٌ هنا يترك صاحبَ الرقم ينتظر رمزاً لن يجيء.
    """
    provider = _provider()
    monkeypatch.setattr(
        provider,
        "_call",
        _Gateway(status=503, body={"error": "الجلسةُ awaiting_qr", "session": "awaiting_qr"}),
    )
    with pytest.raises(WhatsAppError):
        await provider.send_code("+962790000061", "1111", ttl_minutes=5)


async def test_a_number_not_on_whatsapp_is_told_so_by_name(monkeypatch) -> None:
    """خطأٌ يخصّ صاحبَ الرقم لا القناة — ونصُّه يقوله له صراحةً."""
    provider = _provider()
    monkeypatch.setattr(
        provider,
        "_call",
        _Gateway(status=422, body={"error": "…", "not_on_whatsapp": True}),
    )
    with pytest.raises(WhatsAppError) as caught:
        await provider.send_code("+962790000071", "1111", ttl_minutes=5)
    assert "ليس على واتساب" in caught.value.message


async def test_an_unreachable_gateway_is_a_state_not_an_exception(monkeypatch) -> None:
    """شاشةُ الحالة تُفتح غالباً **لأن** شيئاً ساقط — فلا ترمي في وجه من يسأل."""
    provider = _provider()

    async def _boom(*args, **kwargs):
        raise WhatsAppError("تعذّر الوصول إلى بوابة واتساب")

    monkeypatch.setattr(provider, "_call", _boom)
    state = await provider.session_status()
    assert state["state"] == "unreachable"
    assert state["needs_human"] is True


async def test_test_connection_refuses_an_unlinked_session(monkeypatch) -> None:
    """زرُّ الاختبار يسأل **هل الجلسةُ مربوطة**، لا «هل الخدمةُ ترد».

    وهو الفرقُ الذي يوفّر على المشرف ساعةً: «البوابةُ تعمل والجلسةُ غيرُ
    مربوطة» يقول له ما يفعل، و«تعذّر الإرسال» لا يقول شيئاً.
    """
    provider = _provider()
    monkeypatch.setattr(
        provider, "_call", _Gateway(body={"state": "awaiting_qr", "needs_human": True})
    )
    with pytest.raises(WhatsAppError) as caught:
        await provider.test_connection()
    assert "امسح رمزَ الربط" in caught.value.message



# ═══════ منفذُ الفحص — سؤالٌ بلا إرسال (2026-08-31) ═══════


async def test_the_check_asks_and_sends_nothing(monkeypatch) -> None:
    """**يسأل `GET /check` ولا يمسّ `/send`** — وهذا هو الشرطُ كلُّه.

    **ولا يكفي أن يجيب**: بابٌ يجيب صحيحاً **ويرسل في طريقه** يفعل ما وُجد
    ليمنعه، ولا يظهر ذلك في قيمةِ العودة. **فيُقاس ما وصل البوّابة.**
    """
    provider = _provider()
    gateway = _Gateway(status=200, body={"on_whatsapp": True})
    monkeypatch.setattr(provider, "_call", gateway)

    await provider.check_number("+962790000011")

    assert [(m, p) for m, p, _ in gateway.calls] == [("GET", "/check")]
    assert all(path != "/send" for _, path, _ in gateway.calls)


async def test_a_number_not_on_whatsapp_is_its_own_error(monkeypatch) -> None:
    """**٤٢٢ خبرٌ عن الرقم — ولا يُخلط بعطب القناة.**

    **والفرقُ هو الغرض**: خلطُهما يقول لصاحب رقمٍ صحيحٍ «رقمُك ليس على واتساب»
    فيذهب يبحث عن عطبٍ في هاتفه، والعطبُ عندنا.
    """
    provider = _provider()
    monkeypatch.setattr(
        provider,
        "_call",
        _Gateway(
            status=422,
            body={"error": "هذا الرقم ليس على واتساب", "not_on_whatsapp": True},
        ),
    )

    with pytest.raises(WhatsAppNumberUnknown):
        await provider.check_number("+962799999999")


async def test_a_gateway_that_cannot_ask_is_a_channel_fault(monkeypatch) -> None:
    """**٥٠٣ عطبُ قناةٍ لا خبرُ رقم** — فيرتدّ المسارُ إلى القناة التالية."""
    provider = _provider()
    monkeypatch.setattr(
        provider,
        "_call",
        _Gateway(
            status=503,
            body={"error": "الجلسةُ مغلقة", "not_on_whatsapp": False},
        ),
    )

    with pytest.raises(WhatsAppError):
        await provider.check_number("+962790000011")
