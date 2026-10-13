"""Chargily بأمر المالك ٢٠٢٦-١٠-١٣ (SPEC §٧٤-ط/٥، §٧٤-ي) — **ما يُقاس هنا شروطُه بلفظها**:

- «confirm ONLY from Chargily's webhook with its signature verified — never from the app's redirect alone»: عودةُ التطبيق تسأل
  ولا تقيِّد «دُفع»، والإشعارُ الموقَّعُ وحدَه يشحن.
- «never trust the app for the amount»: ثمنُ الاشتراك من الخادم، والشحنُ خيارٌ من خيارات السوق.
- «failed, cancelled and expired … cleanly»: المهلةُ مهلتُنا، **ودفعٌ يصل بعدها يُقيَّد ولا يضيع**.
- وضعُ التجربة لحسابات التجربة وحدَها، والحيُّ لغيرها — **فلا مالٌ تجريبيٌّ في محفظةٍ حقيقيّة**.

**والمحوِّلُ الحقيقيُّ هو المُختبَر** — الشبكةُ وحدَها مزيّفة (`tests/payment_fakes.py`).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.enums import CountryCode
from app.models.payment_request import PaymentRequest
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.models.wallet_setting import WalletSetting
from app.services import payment_requests
from tests.helpers import ensure_plan, rider_session
from tests.payment_fakes import ChargilyFake, add_gateway_method, install_transport
from tests.test_payment_requests import ALGERIAN_RIDER, SECOND_ALGERIAN, _algerian_captain, algeria_market, balance

pytestmark = pytest.mark.asyncio


async def _mark_test(session_factory, user_id: str) -> None:
    """**وسمُ التجربة كما يكتبه سكربتُ الإنشاء وحدَه** (SPEC §٦٥-ج) — لا بابَ في التطبيقات ولا اللوحة يكتبه."""
    async with session_factory() as session:
        await session.execute(update(User).where(User.id == uuid.UUID(user_id)).values(is_test=True))
        await session.commit()


async def _checkout(client: AsyncClient, headers: dict, method_id: uuid.UUID, **body) -> object:
    return await client.post(
        "/payment-requests/checkout",
        json={"provider_id": str(method_id), "purpose": "wallet_topup", "amount": "3000"} | body,
        headers=headers,
    )


async def _deliver(client: AsyncClient, checkout_id: str) -> dict:
    body, headers = ChargilyFake.signed(checkout_id)
    response = await client.post("/payment-requests/webhook/chargily", content=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _row(session_factory, request_id: str) -> PaymentRequest:
    async with session_factory() as session:
        return await session.get(PaymentRequest, uuid.UUID(request_id))


# ------------------------------------------------------------------ الإشعارُ الموقَّعُ وحدَه يشحن


async def test_the_return_alone_never_credits_and_the_signed_webhook_does(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await _checkout(client, rider["headers"], method_id)).json()["request"]["id"]

    # **Chargily يقول «دُفع» والتطبيقُ عاد** — ولا إشعار: يبقى معلَّقاً ولا رصيد
    chargily.status["chk_0001"] = "paid"
    returned = await client.post(f"/payment-requests/{request_id}/refresh", headers=rider["headers"])
    assert returned.status_code == 200 and returned.json()["status"] == "pending"
    assert await balance(client, rider["headers"]) == "0"

    # **إشعارٌ بتوقيعٍ مزوَّر** لا يحرّك شيئاً
    forged_body, _ = ChargilyFake.signed("chk_0001")
    forged = await client.post("/payment-requests/webhook/chargily", content=forged_body,
                               headers={"signature": "f" * 64, "content-type": "application/json"})
    assert forged.status_code == 401
    assert await balance(client, rider["headers"]) == "0"

    # **الإشعارُ الموقَّع** ⇐ قيدٌ واحد، ومكرَّرُه لا يقيّد ثانية
    assert (await _deliver(client, "chk_0001"))["applied"] == 1
    assert (await _deliver(client, "chk_0001"))["applied"] == 0
    assert await balance(client, rider["headers"]) == "3000"
    assert (await _row(session_factory, request_id)).status.value == "approved"


# ------------------------------------------------------------------ المبلغُ من الخادم


async def test_topup_amounts_are_the_market_choices(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    async with session_factory() as session:
        session.add(WalletSetting(country_code=CountryCode.DZ, topup_choices=[Decimal("500"), Decimal("1000")]))
        await session.commit()
    rider = await rider_session(client, ALGERIAN_RIDER)

    listed = (await client.get("/payment-requests/methods", headers=rider["headers"])).json()
    assert listed["topup_choices"] == ["500", "1000"]

    odd = await _checkout(client, rider["headers"], method_id, amount="3000")
    assert odd.status_code == 422 and odd.json()["field"] == "amount"
    missing = await _checkout(client, rider["headers"], method_id, amount=None)
    assert missing.status_code == 422 and missing.json()["field"] == "amount"
    ok = await _checkout(client, rider["headers"], method_id, amount="1000")
    assert ok.status_code == 201, ok.text
    assert ok.json()["request"]["amount"] == "1000"


async def test_a_subscription_checkout_charges_the_plan_price_not_the_app_amount(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    captain = await _algerian_captain(client, session_factory)
    plan_id = await ensure_plan(session_factory, country="DZ", name="خطةُ اختبارٍ جزائريّة", price="1500")

    opened = await _checkout(client, captain["headers"], method_id, purpose="subscription", amount="10",
                             plan_id=str(plan_id))
    assert opened.status_code == 201, opened.text
    assert opened.json()["request"]["amount"] == "1500"
    assert chargily.created[0]["amount"] == 1500

    chargily.status["chk_0001"] = "paid"
    assert (await _deliver(client, "chk_0001"))["applied"] == 1
    row = await _row(session_factory, opened.json()["request"]["id"])
    assert row.status.value == "approved" and row.subscription_id is not None
    # **شحنٌ ثمّ شراءٌ من المحفظة** — فالمحفظةُ عادت صفراً والاشتراكُ قائم
    assert await balance(client, captain["headers"]) == "0"


# ------------------------------------------------------------------ وضعُ التجربة لحسابات التجربة وحدَها


async def test_test_mode_serves_test_accounts_only_and_marks_their_money(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily", test_mode=True)
    real = await rider_session(client, ALGERIAN_RIDER)
    tester = await rider_session(client, SECOND_ALGERIAN)
    await _mark_test(session_factory, tester["user"]["id"])

    # **الحسابُ الحقيقيُّ لا يرى الطريقةَ ولا يفتحها**
    real_methods = (await client.get("/payment-requests/methods", headers=real["headers"])).json()["methods"]
    assert str(method_id) not in [m["id"] for m in real_methods]
    refused = await _checkout(client, real["headers"], method_id)
    assert refused.status_code == 403 and refused.json()["code"] == "payment_test_mode_only"

    # **وحسابُ التجربة يراها موسومةً ويدفع، ومالُه «رصيد تجريبي»**
    test_methods = (await client.get("/payment-requests/methods", headers=tester["headers"])).json()["methods"]
    shown = next(m for m in test_methods if m["id"] == str(method_id))
    assert shown["test_mode"] is True
    request_id = (await _checkout(client, tester["headers"], method_id)).json()["request"]["id"]
    chargily.status["chk_0001"] = "paid"
    assert (await _deliver(client, "chk_0001"))["applied"] == 1
    async with session_factory() as session:
        entry = await session.scalar(
            select(WalletTransaction).where(WalletTransaction.idempotency_key == f"payment_request:{request_id}")
        )
    assert entry is not None and entry.reference.startswith(payment_requests.TEST_MONEY_MARK)


async def test_a_live_contract_refuses_a_test_account(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily", test_mode=False)
    tester = await rider_session(client, SECOND_ALGERIAN)
    await _mark_test(session_factory, tester["user"]["id"])
    listed = (await client.get("/payment-requests/methods", headers=tester["headers"])).json()["methods"]
    assert str(method_id) not in [m["id"] for m in listed]
    refused = await _checkout(client, tester["headers"], method_id)
    assert refused.status_code == 403


# ------------------------------------------------------------------ المهلةُ والدفعُ المتأخّر


async def test_an_unpaid_checkout_expires_and_a_late_payment_is_still_credited(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await _checkout(client, rider["headers"], method_id)).json()["request"]["id"]

    # **قبل المهلة لا يُلغى شيء**
    async with session_factory() as session:
        assert await payment_requests.expire_stale(session) == 0
    async with session_factory() as session:
        await session.execute(
            update(PaymentRequest)
            .where(PaymentRequest.id == uuid.UUID(request_id))
            .values(created_at=datetime.now(UTC) - timedelta(hours=payment_requests.CHECKOUT_TTL_HOURS + 1))
        )
        await session.commit()
    async with session_factory() as session:
        assert await payment_requests.expire_stale(session) == 1
    row = await _row(session_factory, request_id)
    assert row.status.value == "cancelled" and row.cancel_reason == payment_requests.EXPIRED_REASON
    assert await balance(client, rider["headers"]) == "0"

    # **ثمّ دفع على الصفحة المفتوحة** — الإشعارُ الموقَّعُ يقيّده ولا يضيع، ويُكتب لماذا
    chargily.status["chk_0001"] = "paid"
    assert (await _deliver(client, "chk_0001"))["applied"] == 1
    row = await _row(session_factory, request_id)
    assert row.status.value == "approved" and "بعد أن حُسم" in (row.outcome_note or "")
    assert await balance(client, rider["headers"]) == "3000"


async def test_a_checkout_chargily_says_paid_is_not_expired(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await _checkout(client, rider["headers"], method_id)).json()["request"]["id"]
    chargily.status["chk_0001"] = "paid"
    async with session_factory() as session:
        await session.execute(
            update(PaymentRequest)
            .where(PaymentRequest.id == uuid.UUID(request_id))
            .values(created_at=datetime.now(UTC) - timedelta(hours=payment_requests.CHECKOUT_TTL_HOURS + 1))
        )
        await session.commit()
    async with session_factory() as session:
        assert await payment_requests.expire_stale(session) == 0
    assert (await _row(session_factory, request_id)).status.value == "pending"
