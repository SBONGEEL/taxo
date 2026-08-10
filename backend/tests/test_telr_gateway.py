"""مُحوِّل أسلاك Telr وحده — بلا HTTP وبلا قاعدة بيانات.

بقية اختبارات المرحلة تعمل على المزود الوهمي، فتُثبت **المنطق المالي**؛ وهذه
تُثبت **الترجمة**: أن ما يُرسل يحمل الحقول التي ينتظرها المزود، وأن ما يعود
يُقرأ كما يعنيه، وأن رمز الحالة لا يُخمَّن.

نقطة الحقن هي `_post` وحدها — نفس نهج `directions.fetch_route`: يُستبدل نداءُ
الشبكة فتبقى بقية الترجمة حقيقية.

هذه الاختبارات **تُثبّت قراءتنا لواجهة Telr، لا تصحّحها**: القراءة نفسها تحتاج
مطابقةً بالتوثيق الرسمي (انظر رأس `services/card_gateway/telr.py`). قيمتها أن
تكشف الفرق في مكان واحد إذا اختلف التوثيق — بدلاً من أن يظهر أول مرة في
Sandbox.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from decimal import Decimal

import pytest

from app.models.enums import Currency
from app.services.card_gateway.base import (
    CardGatewayError,
    InvalidWebhookSignature,
    OrderRequest,
)
from app.services.card_gateway.telr import (
    ORDER_URL,
    REMOTE_URL,
    STATUS_CANCELLED,
    STATUS_DECLINED,
    STATUS_PAID,
    STATUS_PENDING,
    TRAN_CHECK_FIELDS,
    TelrGateway,
)

STORE_ID = "20001"
AUTH_KEY = "secret-auth-key"


def _gateway() -> TelrGateway:
    return TelrGateway(store_id=STORE_ID, auth_key=AUTH_KEY, test_mode=True)


def _request(cart_id: str = "r0123456789abcdef01") -> OrderRequest:
    return OrderRequest(
        cart_id=cart_id,
        amount=Decimal("8.000"),
        currency=Currency.JOD,
        description="TAXO ride 1234abcd",
        return_url="https://app.example/return?cart_id=" + cart_id,
        customer_name="راكب الرحلات",
        customer_phone="+962791111111",
        customer_ref="1a2b3c",
        save_card=False,
    )


def _stub(gateway: TelrGateway, payload: dict) -> list[dict]:
    """يستبدل نداء الشبكة ويسجّل ما أُرسل."""
    sent: list[dict] = []

    async def _post(url: str, data: dict) -> dict:
        sent.append({"url": url, "data": data})
        return payload

    gateway._post = _post  # type: ignore[method-assign]
    return sent


# ------------------------------------------------------------------ الإنشاء


async def test_create_sends_the_contract_fields_and_returns_the_page() -> None:
    """المفاتيح تأتي من العقد لا من البيئة، والمبلغ نصاً بثلاث خانات."""
    gateway = _gateway()
    sent = _stub(
        gateway,
        {"order": {"ref": "ORDER-1", "url": "https://secure.telr.com/gateway/process"}},
    )

    page = await gateway.create_hosted_page(_request())

    assert page.provider_order_ref == "ORDER-1"
    assert page.redirect_url.startswith("https://secure.telr.com/")
    assert sent[0]["url"] == ORDER_URL

    data = sent[0]["data"]
    assert data["ivp_method"] == "create"
    assert data["ivp_store"] == STORE_ID
    assert data["ivp_authkey"] == AUTH_KEY
    assert data["ivp_test"] == "1"
    assert data["ivp_amount"] == "8.000"
    assert data["ivp_currency"] == "JOD"
    assert data["ivp_cart"] == _request().cart_id
    # `save_card=False` فلا يُرسل الحقل أصلاً — لا "0" يُقرأ كطلبٍ للحفظ
    assert "ivp_savecard" not in data


async def test_save_card_is_sent_only_when_asked() -> None:
    gateway = _gateway()
    sent = _stub(gateway, {"order": {"ref": "R", "url": "https://x"}})

    await gateway.create_hosted_page(replace(_request(), save_card=True))
    assert sent[0]["data"]["ivp_savecard"] == "1"


async def test_provider_error_becomes_a_gateway_error() -> None:
    """نصُّ المزود يظهر في الرسالة، ولا يُقرأ من الجواب شيء آخر."""
    gateway = _gateway()

    async def _post(url: str, data: dict) -> dict:
        raise CardGatewayError("مزود الدفع رفض العملية: Invalid store")

    gateway._post = _post  # type: ignore[method-assign]

    with pytest.raises(CardGatewayError) as exc:
        await gateway.create_hosted_page(_request())
    assert "Invalid store" in exc.value.message


async def test_create_without_a_page_url_is_an_error() -> None:
    """جوابٌ بلا رابط لا يُمرَّر ناقصاً: لا شيء يفتحه العميل فلا نسميه نجاحاً."""
    gateway = _gateway()
    _stub(gateway, {"order": {"ref": "ORDER-1"}})

    with pytest.raises(CardGatewayError):
        await gateway.create_hosted_page(_request())


# ------------------------------------------------------------------ الاستعلام


def _check_payload(code: int, **extra) -> dict:
    order = {
        "ref": "ORDER-1",
        "cartid": "r01",
        "amount": "8.000",
        "currency": "JOD",
        "status": {"code": code, "text": "Paid" if code == STATUS_PAID else "Other"},
        "transaction": {"ref": "TRAN-9"},
    } | extra
    return {"order": order}


async def test_paid_status_is_settled_and_paid() -> None:
    gateway = _gateway()
    _stub(
        gateway,
        _check_payload(
            STATUS_PAID,
            card={
                "type": "Visa",
                "last4": "4242",
                "first6": "424242",
                "token": "TKN-1",
                "expiry": {"month": "12", "year": "2030"},
            },
        ),
    )

    state = await gateway.check_order("ORDER-1")

    assert (state.settled, state.paid) == (True, True)
    assert state.amount == Decimal("8.000")
    assert state.currency == "JOD"
    assert state.transaction_ref == "TRAN-9"
    assert state.card.token == "TKN-1"
    assert state.card.last4 == "4242"
    assert (state.card.expiry_month, state.card.expiry_year) == (12, 2030)
    # ما لا يجوز حفظه لا يُقرأ ولو أرسله المزود
    assert not hasattr(state.card, "first6")


async def test_pending_status_is_not_settled() -> None:
    """`pending` وحدها «لم يُحسم» — وعليها يتوقف كل تحرّكٍ للدفتر."""
    gateway = _gateway()
    _stub(gateway, _check_payload(STATUS_PENDING))

    state = await gateway.check_order("ORDER-1")
    assert (state.settled, state.paid) == (False, False)


@pytest.mark.parametrize("code", [STATUS_DECLINED, STATUS_CANCELLED])
async def test_negative_statuses_are_settled_but_not_paid(code: int) -> None:
    gateway = _gateway()
    _stub(gateway, _check_payload(code))

    state = await gateway.check_order("ORDER-1")
    assert (state.settled, state.paid) == (True, False)


async def test_an_unknown_status_code_is_treated_as_unsettled() -> None:
    """رمزٌ لا نعرفه لا يُخمَّن في أيٍّ من الاتجاهين.

    عدُّه مدفوعاً يقيّد مالاً لم يصل، وعدُّه ساقطاً يفتح الرحلة للدفع مرتين
    ومالُ الراكب محجوز. فيبقى معلّقاً حتى يقول المزود ما نعرفه.
    """
    gateway = _gateway()
    _stub(gateway, _check_payload(77))

    state = await gateway.check_order("ORDER-1")
    assert (state.settled, state.paid) == (False, False)


async def test_an_unreadable_status_is_an_error() -> None:
    gateway = _gateway()
    _stub(gateway, {"order": {"ref": "R", "status": {"code": "nope"}}})

    with pytest.raises(CardGatewayError):
        await gateway.check_order("R")


# -------------------------------------------------------------- الدفع بضغطة


async def test_saved_card_charge_goes_to_the_remote_endpoint() -> None:
    """الخصم المباشر بلا صفحة، فله عنوانه ويحمل رمز البطاقة لا رقمها."""
    gateway = _gateway()
    sent = _stub(gateway, _check_payload(STATUS_PAID))

    state = await gateway.charge_saved_card(_request(), "TKN-1")

    assert state.paid is True
    assert sent[0]["url"] == REMOTE_URL
    assert sent[0]["data"]["card_token"] == "TKN-1"
    assert sent[0]["data"]["ivp_amount"] == "8.000"


# ------------------------------------------------------------------ الاسترداد


async def test_refund_returns_the_provider_reference() -> None:
    gateway = _gateway()
    sent = _stub(gateway, _check_payload(STATUS_PAID, transaction={"ref": "REFUND-3"}))

    ref = await gateway.refund_order(
        "ORDER-1", Decimal("8.000"), Currency.JOD, "شكوى الراكب"
    )

    assert ref == "REFUND-3"
    assert sent[0]["data"]["ivp_method"] == "refund"
    assert sent[0]["data"]["order_ref"] == "ORDER-1"
    assert sent[0]["data"]["ivp_amount"] == "8.000"


# -------------------------------------------------------------- التوقيع


def _signed(**overrides) -> dict:
    payload = {
        "tran_store": STORE_ID,
        "tran_type": "sale",
        "tran_class": "ecom",
        "tran_test": "1",
        "tran_ref": "TRAN-9",
        "tran_prevref": "",
        "tran_firstref": "",
        "tran_currency": "JOD",
        "tran_amount": "8.000",
        "tran_cartid": "r01",
        "tran_status": "A",
        "tran_authcode": "OK",
        "tran_authmessage": "Authorised",
    }
    payload |= overrides
    payload["tran_check"] = _gateway().expected_check(payload)
    return payload


def test_the_signature_is_sha1_over_the_auth_key_then_the_fields() -> None:
    """الصيغة مكتوبةٌ هنا صراحةً: لو خالف التوثيقُ الترتيبَ ظهر الفرق هنا أولاً.

    الحساب اليدوي مقصود ولا يعيد استدعاء الدالة المُختبَرة: اختبارٌ يستدعي ما
    يختبره يمرّ مهما كان الترتيب.
    """
    payload = _signed()
    expected = hashlib.sha1(
        ":".join(
            [AUTH_KEY] + [str(payload[field]) for field in TRAN_CHECK_FIELDS]
        ).encode()
    ).hexdigest()

    assert payload["tran_check"] == expected


def test_a_valid_notice_yields_its_cart_and_reference() -> None:
    notice = _gateway().verify_webhook(_signed())
    assert notice.cart_id == "r01"
    assert notice.provider_order_ref == "TRAN-9"


def test_a_tampered_field_invalidates_the_signature() -> None:
    """المبلغ داخلٌ في التوقيع، فتعديله يُسقط الإشعار كله.

    وهذا احتياطٌ فوق احتياط: الخلفية لا تقرأ المبلغ من الحمولة أصلاً.
    """
    payload = _signed() | {"tran_amount": "800.000"}
    with pytest.raises(InvalidWebhookSignature):
        _gateway().verify_webhook(payload)


def test_a_notice_without_a_signature_is_rejected() -> None:
    payload = _signed()
    del payload["tran_check"]
    with pytest.raises(InvalidWebhookSignature):
        _gateway().verify_webhook(payload)


def test_a_notice_without_a_cart_id_is_rejected() -> None:
    """بلا `cart_id` لا يُعرف صاحبُ الإشعار — ولا يُبحث له عن صاحب."""
    payload = _signed(tran_cartid="")
    with pytest.raises(InvalidWebhookSignature):
        _gateway().verify_webhook(payload)


def test_another_stores_key_does_not_validate() -> None:
    """توقيعٌ صحيحٌ بمفتاح متجرٍ آخر ليس صحيحاً هنا."""
    other = TelrGateway(store_id=STORE_ID, auth_key="another-key", test_mode=True)
    with pytest.raises(InvalidWebhookSignature):
        other.verify_webhook(_signed())
