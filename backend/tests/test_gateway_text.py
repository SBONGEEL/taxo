"""**نصُّ البوّابة لا يبلغ الشاشة** — حارسُ مسارٍ كان مفتوحاً بالكامل.

## العلّةُ مقيسةٌ لا مفترضة (٢٠٢٦-٠٩-٠٩)

قرأ المالكُ على شاشةٍ عربيةٍ: **«بوابة واتساب: known is not defined»**. نصُّ
`ReferenceError` من جافاسكربت، بالإنجليزية، إلى مستخدمٍ يطلب رمزَ تحقّق.

**والمسارُ كان مفتوحاً في أربع طبقاتٍ ولا واحدةٌ تسأل «أهذا نصٌّ كُتب
لإنسان؟»**: البوّابةُ تعيد `{"error": "..."}` → `baileys.py` يحقنه في رسالةٍ
(`f"بوابة واتساب: {detail}"`) → `verification.py` يمرّره `detail` → التطبيقُ
يعرض `caught.message`.

**والقاعدة**: نصُّ المزوّد **تشخيصٌ لا خطاب** — يُسجَّل كاملاً، **ويُرمى صنفٌ
رسالتُه عربيةٌ مسمّاةٌ من `base.py`**.

**ويُقاس بالنقض**: بإعادة `f"...{detail}"` إلى موضعه تسقط خمسةٌ من ستّة.
"""

from __future__ import annotations

import contextlib
import logging
import re

import pytest

from app.services.whatsapp.base import (
    WhatsAppError,
    WhatsAppNumberUnanswered,
    WhatsAppNumberUnknown,
)

# نصٌّ خامٌّ بالإنجليزية كالذي خرج فعلاً على شاشة المالك
RAW = "known is not defined"

# حرفٌ لاتينيٌّ واحدٌ في رسالةٍ للمستخدم كافٍ ليكون النصُّ غيرَ مكتوبٍ له
LATIN = re.compile(r"[A-Za-z]")

LOGGER = "app.services.whatsapp.baileys"


class _Sink(logging.Handler):
    """مِقبضٌ يُثبَّت على المسجِّل نفسِه.

    **ولا يُعتمد على `caplog`**: إعدادُ سجلِّ التطبيق يقطع الانتشارَ إلى
    الجذر، فيلتقط `caplog` فراغاً — **وفراغٌ يُقرأ «لم يُسجَّل» وهو خطأُ
    قياسٍ لا خطأُ شيفرة**. وقياسٌ يكذب في اتجاه الفشل يُطفئ حارساً صحيحاً.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


@contextlib.contextmanager
def _capture():
    # **كائنُ المسجِّل من الوحدة نفسِها لا اسمٌ يُخمَّن**: اسمٌ يُكتب بيدٍ
    # يفترق عن  أوّلَ نقلِ ملفّ، **فيلتقط المِقبضُ فراغاً ويُقرأ
    # الفراغُ عطباً**. وهو «حارسٌ يخترع عطباً» في ثوب قياس.
    from app.services.whatsapp import baileys as module

    log = module.logger
    sink = _Sink()
    level, log.level = log.level, logging.DEBUG
    # **ومسجِّلٌ مُعطَّلٌ يبتلع بلا خطأ**: إعدادُ السجلّ عند الإقلاع يعطّل
    # المسجِّلاتِ القائمة، فيمرّ  بلا أثرٍ ولا شكوى — وهو
    # «فعلٌ يُنفَّذ ولا أثرَ له» في ثوبِ سجلّ.
    disabled, log.disabled = log.disabled, False
    log.addHandler(sink)
    try:
        yield sink
    finally:
        log.removeHandler(sink)
        log.level = level
        log.disabled = disabled


def _provider():
    """مزوّدُ البوّابة بلا شبكة — `_call` وحدَه يُستبدَل."""
    from app.services.whatsapp.baileys import BaileysGatewayProvider

    return BaileysGatewayProvider(base_url="http://gw", gateway_key="k", redis=None)


async def _noop(*a: object, **k: object) -> None:
    return None


def _assert_clean(caught, sink) -> None:
    message = caught.value.message
    assert RAW not in message, f"النصُّ الخامُّ بلغ الرسالة: {message}"
    assert not LATIN.search(message), f"حرفٌ لاتينيٌّ في رسالةِ مستخدم: {message}"
    assert message.strip(), "رسالةٌ فارغةٌ ليست جواباً"
    # **ولا يضيع**: من يشخّص يحتاجه، وموضعُه السجلّ
    assert any(RAW in line for line in sink.lines), (
        "النصُّ الخامُّ لم يُسجَّل — فضاع التشخيص. المسجَّل: " + " | ".join(sink.lines)
    )


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({"error": RAW}, WhatsAppError),
        ({"error": RAW, "number_unanswered": True}, WhatsAppNumberUnanswered),
    ],
)
async def test_gateway_text_never_reaches_the_screen_on_send(
    monkeypatch, body, expected
) -> None:
    """`/send` يفشل — **والرسالةُ عربيةٌ والنصُّ الخامُّ في السجلّ.**"""
    provider = _provider()

    async def _call(method: str, path: str, **kw: object):
        return 503, body

    monkeypatch.setattr(provider, "_call", _call)
    monkeypatch.setattr(provider, "_guard_limits", _noop)

    with _capture() as sink:
        with pytest.raises(expected) as caught:
            await provider.send_code("+962790000038", "123456", ttl_minutes=5)

    _assert_clean(caught, sink)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({"error": RAW}, WhatsAppError),
        ({"error": RAW, "not_on_whatsapp": True}, WhatsAppNumberUnknown),
        ({"error": RAW, "number_unanswered": True}, WhatsAppNumberUnanswered),
    ],
)
async def test_gateway_text_never_reaches_the_screen_on_check(
    monkeypatch, body, expected
) -> None:
    """و`/check` كذلك — **والبابان يقولان الشيءَ نفسَه**.

    وبابان يفترقان في هذا أسوأُ من بابٍ واحدٍ يخطئ: يُصلَح أحدُهما ويُنسى
    الآخر، **فيعود النصُّ الخامُّ من الطريق الذي لم يُقرأ**.
    """
    provider = _provider()

    async def _call(method: str, path: str, **kw: object):
        return 503, body

    monkeypatch.setattr(provider, "_call", _call)

    with _capture() as sink:
        with pytest.raises(expected) as caught:
            await provider.check_number("+962790000038")

    _assert_clean(caught, sink)


def test_every_gateway_message_in_base_is_arabic() -> None:
    """**ورسائلُ الأصناف نفسِها عربيةٌ كلُّها** — وإلا فالحارسُ يحرس ثقباً.

    فلو صار افتراضُ صنفٍ إنجليزياً يوماً، مرّ النصُّ من الاختبارات فوق **لأنها
    تقيس ألّا يُحقَن الخامُّ، لا أن البديلَ عربيّ**.
    """
    for cls in (WhatsAppError, WhatsAppNumberUnknown, WhatsAppNumberUnanswered):
        assert not LATIN.search(cls.message), f"{cls.__name__}: {cls.message}"
