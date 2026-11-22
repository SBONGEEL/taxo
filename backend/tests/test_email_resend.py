"""مُرسِلُ Resend — **أسلاكُه وحدَها**، والتدفّقُ فوقه مقيسٌ في `test_email_channel.py`.

## ما يُقاس هنا

* **`build_provider` يبني Resend من العقد**، ويرفض **اسماً غيرَ مبنيّ** و**عقداً
  ناقصاً** بنصّه — لا سقوطَ صامتٌ إلى مُرسِلٍ لا وجودَ له.
* **والوهميُّ مرفوضٌ في الإنتاج** — رمزٌ يُقرأ من Redis لا من الصندوق.
* **والإرسالُ يحمل الشكلَ الذي تقبله Resend**، **وخطؤها لا يطبع نصَّ الرسالة**
  (فيه الرمز).
* **ومفتاحُ الإرسال وحدَه يُقرأ «صالحاً» في اختبار الاتصال** — وردُّ المفتاح
  الباطل خطأٌ لا نجاح.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import httpx
import pytest

import app.services.email as email_pkg
from app.services.email import (
    EmailError,
    EmailUnavailable,
    ResendEmailProvider,
    build_provider,
)

FROM = "noreply@example.com"


def _key() -> str:
    # مفتاحٌ وهميٌّ مولَّدٌ لا حرفيّ — فلا يصيح ماسحُ الأسرار على اختبار
    return "test-" + uuid.uuid4().hex


def _response(status: int, body: dict | str) -> httpx.Response:
    request = httpx.Request("POST", "https://api.resend.com/emails")
    if isinstance(body, dict):
        return httpx.Response(status, json=body, request=request)
    return httpx.Response(status, text=body, request=request)


# ═════════════════════════════ ١) البناءُ من العقد


def test_build_provider_makes_resend_from_the_contract():
    provider = build_provider(
        {"provider_name": "Resend", "api_key": _key(), "from_address": FROM, "from_name": "TAXO"}
    )
    assert isinstance(provider, ResendEmailProvider)
    assert provider.provider_name == "resend"


def test_an_empty_provider_name_means_resend():
    assert isinstance(build_provider({"api_key": _key(), "from_address": FROM}), ResendEmailProvider)


def test_an_unbuilt_sender_is_refused_by_name():
    with pytest.raises(EmailUnavailable) as caught:
        build_provider({"provider_name": "brevo", "api_key": _key(), "from_address": FROM})
    assert "brevo" in caught.value.message


@pytest.mark.parametrize("missing", ["api_key", "from_address"])
def test_an_incomplete_contract_is_refused(missing):
    values = {"provider_name": "resend", "api_key": _key(), "from_address": FROM}
    values[missing] = "  "
    with pytest.raises(EmailUnavailable):
        build_provider(values)


def test_the_mock_is_refused_in_production(monkeypatch):
    monkeypatch.setattr(email_pkg, "settings", SimpleNamespace(is_production=True))
    with pytest.raises(EmailUnavailable):
        build_provider({"use_mock": True})


# ═════════════════════════════ ٢) الإرسال


async def test_send_posts_the_shape_resend_accepts(monkeypatch):
    provider = ResendEmailProvider(api_key=_key(), from_address=FROM, from_name="TAXO")
    seen: dict = {}

    async def fake_post(payload):
        seen.update(payload)
        return _response(200, {"id": "msg-123"})

    monkeypatch.setattr(provider, "_post", fake_post)
    reference = await provider.send("a@b.co", subject="رمزك 123456", body="الرمز 123456")
    assert reference == "msg-123"
    assert seen == {
        "from": f"TAXO <{FROM}>",
        "to": ["a@b.co"],
        "subject": "رمزك 123456",
        "text": "الرمز 123456",
    }


async def test_a_refused_send_raises_without_echoing_the_code(monkeypatch):
    provider = ResendEmailProvider(api_key=_key(), from_address=FROM)

    async def fake_post(payload):
        return _response(403, {"name": "validation_error", "message": "domain not verified"})

    monkeypatch.setattr(provider, "_post", fake_post)
    with pytest.raises(EmailError) as caught:
        await provider.send("a@b.co", subject="رمزك 987654", body="الرمز 987654")
    assert "domain not verified" in caught.value.message
    assert "987654" not in caught.value.message


async def test_a_network_failure_is_an_email_error(monkeypatch):
    provider = ResendEmailProvider(api_key=_key(), from_address=FROM)

    async def fake_post(payload):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(provider, "_post", fake_post)
    with pytest.raises(EmailError):
        await provider.send("a@b.co", subject="s", body="b")


# ═════════════════════════════ ٣) اختبارُ الاتصال


async def test_a_sending_only_key_reads_as_valid(monkeypatch):
    provider = ResendEmailProvider(api_key=_key(), from_address=FROM)

    async def fake_get(path):
        return _response(401, {"name": "restricted_api_key", "message": "only send"})

    monkeypatch.setattr(provider, "_get", fake_get)
    assert "صالح" in await provider.test_connection()


async def test_an_invalid_key_is_an_error_not_a_success(monkeypatch):
    provider = ResendEmailProvider(api_key=_key(), from_address=FROM)

    async def fake_get(path):
        return _response(400, {"name": "validation_error", "message": "API key is invalid"})

    monkeypatch.setattr(provider, "_get", fake_get)
    with pytest.raises(EmailError):
        await provider.test_connection()
