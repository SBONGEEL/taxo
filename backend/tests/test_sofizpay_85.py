"""SofizPay وسيطاً ثانياً بقواعد Chargily (SPEC §٨٥) — بصيغ الوثائق المرسومة (`docs.sofizpay.com`، قُرئت ٢٠٢٦-١٠-٢٧).

ما يُقاس: الانقطاعُ يوقف قبل الصفحة (`503` باسمه) · «غيرُ موجودة» ليست رفضاً · الإشعارُ لا يقيّد إلا بفحصٍ مقبول · التأكيدُ المكرَّر يقيّد مرّةً ·
النقرُ المزدوج صفحةٌ واحدة · «بديلٌ حين يتوقّف Chargily» يُخفيه وChargily قائم · عقدُه للمالك وحدَه.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.redis_client import get_redis_client
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.services import payment_gateways, payment_requests
from tests.helpers import _enable_provider, rider_session
from tests.payment_fakes import SOFIZPAY_ACCOUNT, add_gateway_method, install_transport, sofizpay_signed
from tests.test_dz_payments_82 import _owner
from tests.test_payment_requests import ALGERIAN_RIDER, algeria_market, balance


@pytest.fixture(autouse=True)
def _no_double_tap_window(monkeypatch: pytest.MonkeyPatch) -> None:
    # **نافذةُ النقر المزدوج** تُقاس في اختبارها وحدَه — وما سواه يفتح صفحتين بقصد
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)


async def _rider_with_email(client: AsyncClient, session_factory) -> dict:
    rider = await rider_session(client, ALGERIAN_RIDER)
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(rider["user"]["id"]))
        user.email = "rider@example.dz"
        await session.commit()
    return rider


async def _open(client: AsyncClient, headers: dict, method_id: uuid.UUID, amount: str = "1500") -> httpx.Response:
    return await client.post(
        "/payment-requests/checkout",
        json={"provider_id": str(method_id), "purpose": "wallet_topup", "amount": amount},
        headers=headers,
    )


async def _entries(session_factory) -> int:
    async with session_factory() as session:
        return int(await session.scalar(select(func.count()).select_from(WalletTransaction)) or 0)


async def test_an_outage_stops_before_the_page_and_says_so(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    _, sofizpay = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    rider = await _rider_with_email(client, session_factory)
    sofizpay.down = True
    opened = await _open(client, rider["headers"], method_id)
    assert opened.status_code == 503 and opened.json()["code"] == "payment_gateway_down"
    assert sofizpay.created == []  # **لا صفحةَ فُتحت** والوسيطُ متوقّف
    assert await get_redis_client().exists("gateway:down:sofizpay:DZ")
    # **عاد** ⇐ الفحصُ التالي يمحو الحالَ ويفتح الصفحة
    sofizpay.down = False
    assert (await _open(client, rider["headers"], method_id)).status_code == 201
    assert not await get_redis_client().exists("gateway:down:sofizpay:DZ")


async def test_a_return_without_result_stays_pending_and_a_missing_order_is_not_a_refusal(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    _, sofizpay = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    rider = await _rider_with_email(client, session_factory)
    opened = (await _open(client, rider["headers"], method_id)).json()
    request_id, cib_id = opened["request"]["id"], opened["request"]["reference"]
    refreshed = await client.post(f"/payment-requests/{request_id}/refresh", headers=rider["headers"])
    assert refreshed.json()["status"] == "pending"
    # **«غيرُ موجودة» عند الوسيط** (صفحةٌ لم يبدأها الدافع) — تبقى معلّقةً لا «مرفوضة»
    sofizpay.check.pop(cib_id)
    refreshed = await client.post(f"/payment-requests/{request_id}/refresh", headers=rider["headers"])
    assert refreshed.json()["status"] == "pending" and await balance(client, rider["headers"]) == "0"


async def test_a_late_and_repeated_confirmation_credits_exactly_once(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    _, sofizpay = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    rider = await _rider_with_email(client, session_factory)
    opened = (await _open(client, rider["headers"], method_id)).json()
    cib_id = opened["request"]["reference"]
    before = await _entries(session_factory)
    sofizpay.check[cib_id] |= {"orderStatus": 2, "respCode": "00"}
    notice = sofizpay_signed({"event": "cib.payment.updated", "payment_status": "success", "cib_transaction_id": cib_id, "amount": 150000})
    first = await client.post("/payment-requests/webhook/sofizpay", json=notice)
    again = await client.post("/payment-requests/webhook/sofizpay", json=notice)
    refreshed = await client.post(f"/payment-requests/{opened['request']['id']}/refresh", headers=rider["headers"])
    assert first.json()["applied"] == 1 and again.json()["applied"] == 0
    assert refreshed.json()["status"] == "approved"
    assert await _entries(session_factory) == before + 1 and await balance(client, rider["headers"]) == "1500"


async def test_a_double_tap_opens_one_page(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 5)
    await algeria_market(session_factory)
    _, sofizpay = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    rider = await _rider_with_email(client, session_factory)
    first = await _open(client, rider["headers"], method_id)
    second = await _open(client, rider["headers"], method_id)
    assert first.status_code == 201
    assert second.status_code in (201, 409)
    assert len(sofizpay.created) == 1


async def test_fallback_only_is_shown_when_chargily_is_down_and_hidden_otherwise(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    install_transport(monkeypatch)
    await add_gateway_method(session_factory, "chargily")
    await add_gateway_method(session_factory, "sofizpay")
    await _enable_provider(session_factory, "sofizpay", {"account": SOFIZPAY_ACCOUNT, "fallback_only": True}, country="DZ")
    rider = await _rider_with_email(client, session_factory)

    async def shown() -> set[str]:
        body = (await client.get("/payment-requests/methods", headers=rider["headers"])).json()
        return {row["code"] for row in body["methods"] if row.get("gateway")}

    assert await shown() == {"chargily"}
    await get_redis_client().set("gateway:down:chargily:DZ", "now")
    assert await shown() == {"chargily", "sofizpay"}
    await get_redis_client().delete("gateway:down:chargily:DZ")
    # **مطفأً ⇐ يُعرضان معاً**
    await _enable_provider(session_factory, "sofizpay", {"account": SOFIZPAY_ACCOUNT, "fallback_only": False}, country="DZ")
    assert await shown() == {"chargily", "sofizpay"}


async def test_the_sofizpay_contract_is_the_owners_alone(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    body = {"country_code": "DZ", "values": {"account": SOFIZPAY_ACCOUNT, "sandbox": True}, "is_active": False}
    refused = await client.put("/admin/providers/sofizpay", json=body, headers=admin_headers)
    assert refused.status_code == 403
    owner = await _owner(session_factory)
    saved = await client.put("/admin/providers/sofizpay", json=body, headers=owner)
    assert saved.status_code == 200, saved.text
    credential_id = saved.json()["id"]
    assert (await client.post(f"/admin/providers/{credential_id}/activate", headers=admin_headers)).status_code == 403
    assert (await client.post(f"/admin/providers/{credential_id}/activate", headers=owner)).status_code == 200


async def test_the_health_probe_reads_a_missing_order_as_up(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.payment_gateways.sofizpay import SofizPayGateway

    _, sofizpay = install_transport(monkeypatch)
    gateway = SofizPayGateway(account=SOFIZPAY_ACCOUNT, sandbox=True)
    await gateway.health()
    assert sofizpay.paths[-1] == "/sandbox/cib-transaction-check/"
    sofizpay.down = True
    with pytest.raises(payment_gateways.GatewayDown):
        await gateway.health()
