"""مسارُ Chargily بعد مراجعة المالك (SPEC §٧٦-ع/٢، ٢٠٢٦-١٠-١٧) — **كلُّ اختبارٍ هنا يُثبت إصلاحاً من `design/CHARGILY-FLOW.md`**:

- **عميلُ Chargily** يُنشأ مرّةً ويُعاد، ولا يُرسل إلا بمفتاحه في العقد، **وعميلٌ رفضه الوسيطُ لا يوقف الدفع**.
- **لغةُ صفحته لغةُ التطبيق** (`locale`)، **وأسبابُ الخادم وأسماءُ الطرق والخطط بالفرنسيّة** لمن طلبها.
- **«أكمل الدفع»** يعيد الصفحةَ نفسَها ولا يفتح ثانية، ولا يكتب شيئاً.
- **صفحةٌ «قيد المعالجة» حين تنتهي المهلة** لا يُقال عنها «لم يُدفع شيء».
- **ومبالغُ الجزائر بلا كسورٍ على السلك** — في الأجوبة التي خرجت «200.000» و«0.000».

**والمحوِّلُ الحقيقيُّ هو المُختبَر** — الشبكةُ وحدَها مزيّفة (`tests/payment_fakes.py`).
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.models.gateway_customer import GatewayCustomer
from app.models.payment_request import PayMethod, PaymentRequest
from app.services import payment_requests
from tests.helpers import ensure_plan, rider_session
from tests.payment_fakes import ChargilyFake, add_gateway_method, install_transport
from tests.test_payment_requests import ALGERIAN_RIDER, SECOND_ALGERIAN, _algerian_captain, algeria_market

pytestmark = pytest.mark.asyncio

FRENCH = {"Accept-Language": "fr-DZ,fr;q=0.9"}
THREE_PLACES = re.compile(r"^-?\d+\.\d{3}$")


async def _checkout(client: AsyncClient, headers: dict, method_id: uuid.UUID, **body) -> object:
    return await client.post(
        "/payment-requests/checkout",
        json={"provider_id": str(method_id), "purpose": "wallet_topup", "amount": "3000"} | body,
        headers=headers,
    )


async def _customers(session_factory) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(GatewayCustomer))


def _three_places(value: object, path: str = "") -> list[str]:
    """**كلُّ نصٍّ عشريٍّ بثلاث خانات** في الجواب — والجزائريُّ بلا كسور."""
    if isinstance(value, dict):
        return [hit for key, item in value.items() for hit in _three_places(item, f"{path}.{key}")]
    if isinstance(value, list):
        return [hit for index, item in enumerate(value) for hit in _three_places(item, f"{path}[{index}]")]
    return [f"{path}={value}"] if isinstance(value, str) and THREE_PLACES.match(value) else []


# ------------------------------------------------------------------ عميلُ Chargily


async def test_the_customer_is_created_once_reused_and_carries_name_and_phone(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily", send_customer=True)
    rider = await rider_session(client, ALGERIAN_RIDER)

    assert (await _checkout(client, rider["headers"], method_id)).status_code == 201
    assert (await _checkout(client, rider["headers"], method_id)).status_code == 201
    assert len(chargily.customers) == 1
    assert chargily.customers[0]["name"] == ALGERIAN_RIDER["name"]
    assert chargily.customers[0]["phone"].startswith("+213")
    # **ولا بريدٌ يُخترع** — الحسابُ بلا بريد
    assert "email" not in chargily.customers[0]
    assert [page.get("customer_id") for page in chargily.created] == ["cus_0001", "cus_0001"]
    assert await _customers(session_factory) == 1


async def test_no_customer_is_sent_while_the_contract_switch_is_off(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**سياسةُ الخصوصية المنشورة تقول إنّا لا نرسل الاسمَ والهاتف** — فالمفتاحُ مطفأٌ ابتداءً ولا يُرسل شيء."""
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    assert (await _checkout(client, rider["headers"], method_id)).status_code == 201
    assert chargily.customers == []
    assert "customer_id" not in chargily.created[0]
    assert await _customers(session_factory) == 0


async def test_a_customer_the_gateway_rejects_is_forgotten_and_the_payment_still_opens(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily", send_customer=True)
    rider = await rider_session(client, ALGERIAN_RIDER)
    assert (await _checkout(client, rider["headers"], method_id)).status_code == 201

    chargily.dead_customers.add("cus_0001")
    second = await _checkout(client, rider["headers"], method_id)
    assert second.status_code == 201, second.text
    assert "customer_id" not in chargily.created[-1]
    assert await _customers(session_factory) == 0

    third = await _checkout(client, rider["headers"], method_id)
    assert third.status_code == 201
    assert chargily.created[-1]["customer_id"] == "cus_0002"


# ------------------------------------------------------------------ لغةُ الصفحة ولغةُ الخادم


async def test_the_page_language_follows_the_app(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    await _checkout(client, rider["headers"], method_id)
    await _checkout(client, rider["headers"] | FRENCH, method_id)
    assert [page["locale"] for page in chargily.created] == ["ar", "fr"]


async def test_reasons_and_names_are_french_for_a_french_app_and_arabic_unchanged(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    async with session_factory() as session:
        await session.execute(update(PayMethod).where(PayMethod.id == method_id).values(name="البطاقة الذهبية وCIB"))
        await session.commit()
    rider = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await _checkout(client, rider["headers"], method_id)).json()["request"]["id"]
    chargily.status["chk_0001"] = "failed"
    assert (await client.post(f"/payment-requests/{request_id}/refresh", headers=rider["headers"])).json()["status"] == "rejected"

    arabic = (await client.get("/payment-requests/me", headers=rider["headers"])).json()[0]
    french = (await client.get("/payment-requests/me", headers=rider["headers"] | FRENCH)).json()[0]
    assert arabic["rejection_reason"] == "رفض الوسيطُ الدفع"
    assert french["rejection_reason"] == "Le paiement a été refusé"
    assert (arabic["provider_name"], french["provider_name"]) == ("البطاقة الذهبية وCIB", "Edahabia et CIB")
    assert french["gateway"] is True and french["gateway_name"] == "Chargily"
    assert french["provider_id"] == str(method_id)
    listed = (await client.get("/payment-requests/methods", headers=rider["headers"] | FRENCH)).json()
    shown = next(row for row in listed["methods"] if row["id"] == str(method_id))
    assert shown["name"] == "Edahabia et CIB" and shown["gateway_name"] == "Chargily"
    # **والعملةُ بلغة الطلب** — «DA» للفرنسيّة و«د.ج» كما كانت
    def label(body: dict) -> str:
        return next(row["currency_label"] for row in body["countries"] if row["country_code"] == "DZ")

    assert label((await client.get("/config")).json()) == "د.ج"
    assert label((await client.get("/config", headers=FRENCH)).json()) == "DA"


async def test_plan_names_are_french_and_their_prices_have_no_fraction(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    install_transport(monkeypatch)
    captain = await _algerian_captain(client, session_factory)
    await ensure_plan(session_factory, country="DZ", name="TAXO X1 — يومي", price="200")
    french = (await client.get("/subscriptions/me", headers=captain["headers"] | FRENCH)).json()
    arabic = (await client.get("/subscriptions/me", headers=captain["headers"])).json()
    assert [plan["name"] for plan in french["plans"]] == ["TAXO X1 — Journalier"]
    assert [plan["name"] for plan in arabic["plans"]] == ["TAXO X1 — يومي"]
    assert arabic["plans"][0]["price_to_pay"] == "200"


# ------------------------------------------------------------------ «أكمل الدفع»


async def test_continue_payment_reopens_the_same_page_and_writes_nothing(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    other = await rider_session(client, SECOND_ALGERIAN)
    request_id = (await _checkout(client, rider["headers"], method_id)).json()["request"]["id"]

    resumed = await client.post(f"/payment-requests/{request_id}/resume", headers=rider["headers"])
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["checkout_url"].endswith("/chk_0001/pay")
    assert resumed.json()["request"]["id"] == request_id
    assert len(chargily.created) == 1  # **لا صفحةَ ثانية**

    assert (await client.post(f"/payment-requests/{request_id}/resume", headers=other["headers"])).status_code == 404

    # **صفحةٌ بدأت معالجتُها لا تُفتح** — ولا يتغيّر الطلب
    chargily.status["chk_0001"] = "processing"
    refused = await client.post(f"/payment-requests/{request_id}/resume", headers=rider["headers"])
    assert refused.status_code == 409
    async with session_factory() as session:
        assert (await session.get(PaymentRequest, uuid.UUID(request_id))).status.value == "pending"


# ------------------------------------------------------------------ المهلةُ وصفحةٌ قيد المعالجة


async def test_an_expired_page_chargily_is_still_processing_does_not_say_nothing_was_paid(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await _checkout(client, rider["headers"], method_id)).json()["request"]["id"]
    chargily.status["chk_0001"] = "processing"
    async with session_factory() as session:
        await session.execute(
            update(PaymentRequest)
            .where(PaymentRequest.id == uuid.UUID(request_id))
            .values(created_at=datetime.now(UTC) - timedelta(hours=payment_requests.CHECKOUT_TTL_HOURS + 1))
        )
        await session.commit()
    async with session_factory() as session:
        assert await payment_requests.expire_stale(session) == 1
    async with session_factory() as session:
        row = await session.get(PaymentRequest, uuid.UUID(request_id))
    assert row.status.value == "cancelled"
    assert row.cancel_reason == payment_requests.EXPIRED_PROCESSING_REASON.format("Chargily")
    assert "لم يُدفع شيء" not in row.cancel_reason

    # **ودفعٌ يكتمل بعدها يُقيَّد بإشعاره** كما كان
    chargily.status["chk_0001"] = "paid"
    body, headers = ChargilyFake.signed("chk_0001")
    assert (await client.post("/payment-requests/webhook/chargily", content=body, headers=headers)).json()["applied"] == 1


# ------------------------------------------------------------------ مبالغُ الجزائر على السلك


async def test_algerian_amounts_have_no_fraction_where_they_had_three(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**المسحُ الذي وجدها** (٢٠٢٦-١٠-١٧): صافي اليوم وأخواتُه «0.000»، وثمنُ الخطّة «200.000»، وقيودُ المحفظة «20000.000» بلا عملة."""
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    captain = await _algerian_captain(client, session_factory)
    await ensure_plan(session_factory, country="DZ", name="TAXO X1 — يومي", price="200")
    opened = await _checkout(client, captain["headers"], method_id, wallet="driver")
    assert opened.status_code == 201, opened.text
    chargily.status["chk_0001"] = "paid"
    body, headers = ChargilyFake.signed("chk_0001")
    assert (await client.post("/payment-requests/webhook/chargily", content=body, headers=headers)).json()["applied"] == 1

    for path in (
        "/drivers/me/earnings",
        "/subscriptions/me",
        "/wallet/me?wallet=driver",
        "/wallet/me/transactions?wallet=driver",
        "/drivers/me/debt",
        "/me/referrals",
    ):
        response = await client.get(path, headers=captain["headers"])
        assert response.status_code == 200, (path, response.text)
        assert _three_places(response.json()) == [], path
    entries = (await client.get("/wallet/me/transactions?wallet=driver", headers=captain["headers"])).json()
    assert entries[0]["currency"] == "DZD" and entries[0]["amount"] == "3000"
