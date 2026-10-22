"""دفعُ الجزائر بأمر المالك ٢٠٢٦-١٠-٢٢ (SPEC §٨٢) — **ما يُقاس هنا شروطُه بلفظها**.

**أ) Chargily بأمان**: الانقطاعُ (مهلة · `502` · `504`) يُقال للدافع ولا يُرسل إلى صفحةٍ معطوبة · العودةُ بلا نتيجة · النقرتان · الإشعارُ
المتأخّر · التسويةُ تجد صفحةً دُفعت · كلُّ طورٍ من أطوار §٨٢-أ/٢ · «دفع مرّتين للغرض نفسِه ⇐ الزائدُ في المحفظة».

**ب) BaridiMob بمراجعة**: اعتمادُ المراجع · اعتمادُ المالك · الرفض · رقمُ تحويلٍ مكرَّر · اعتمادان معاً · الحدّان · الطريقةُ مخفيّةٌ حتى
تُضبط · المراجعُ لا يفتح صفحةً ولا سوقاً غيرَ صفحته · الهاتفُ المقنَّع.

**والمحوِّلُ الحقيقيُّ هو المُختبَر** — الشبكةُ وحدَها مزيّفة (`tests/payment_fakes.py`).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.core.crypto import get_cipher
from app.core.redis_client import get_redis_client
from app.models.enums import CountryCode, PaymentRequestStatus, UserRole
from app.models.payment_request import PaymentRequest, PayMethod
from app.models.subscription import DriverSubscription
from app.models.totp import UserTotp
from app.models.user import User
from app.models.user_role_grant import UserRoleGrant
from app.models.wallet import WalletTransaction
from app.services import alert_capture, payment_gateways, payment_requests, token_service
from tests.helpers import ensure_plan, rider_session
from tests.payment_fakes import ChargilyFake, add_gateway_method, install_transport
from tests.test_payment_requests import (
    ALGERIAN_RIDER,
    PNG,
    _algerian_captain,
    algeria_market,
    balance,
    submit,
)

pytestmark = pytest.mark.asyncio

#: **RIP اختبارٍ مولَّدٌ لا حسابُ أحد** — عشرون رقماً بشكل بريد الجزائر
TEST_RIP = "00799999" + "0" * 12


# ------------------------------------------------------------------ أدوات


async def _queued() -> list[dict]:
    """**ما سُلِّم لإشعارات المالك** — ثمّ يُمحى، فيقيس ما بعده جديدَه وحدَه."""
    await alert_capture.settle()
    redis = get_redis_client()
    raw = await redis.lrange(alert_capture.QUEUE_KEY, 0, -1)
    await redis.delete(alert_capture.QUEUE_KEY)
    return [json.loads(item) for item in raw]


def _kinds(events: list[dict]) -> list[str]:
    return [event["k"] for event in events]


async def _staff(session_factory, *, roles: list[UserRole], name: str, factor: bool = True) -> tuple[dict, uuid.UUID]:
    """**مالكٌ أو مراجعٌ بعاملٍ ثانٍ مؤكَّد** — كلاهما مُلزَمٌ به (§٨٢-ب/٥)؛ و`factor=False` لقياس الإلزام نفسِه."""
    async with session_factory() as session:
        user = User(
            phone=None, name=name, role=roles[0], country_code=CountryCode.DZ,
            role_grants=[UserRoleGrant(role=role) for role in roles],
        )
        session.add(user)
        await session.flush()
        if factor:
            session.add(UserTotp(
                user_id=user.id, secret_encrypted=get_cipher().encrypt({"secret": "JBSWY3DPEHPK3PXP"}),
                confirmed_at=datetime.now(UTC),
            ))
        await session.commit()
        tokens = await token_service.issue_token_pair(session, user)
        return {"Authorization": f"Bearer {tokens.access_token}"}, user.id


async def _owner(session_factory) -> dict:
    return (await _staff(session_factory, roles=[UserRole.ADMIN, UserRole.OWNER], name="مالك الاختبار"))[0]


async def _reviewer(session_factory, *, factor: bool = True) -> dict:
    return (await _staff(session_factory, roles=[UserRole.PAYMENT_REVIEWER], name="مراجع الاختبار", factor=factor))[0]


async def _checkout(client: AsyncClient, headers: dict, method_id: uuid.UUID, **body):
    return await client.post(
        "/payment-requests/checkout",
        json={"provider_id": str(method_id), "purpose": "wallet_topup", "amount": "3000"} | body,
        headers=headers,
    )


async def _deliver(client: AsyncClient, checkout_id: str) -> None:
    body, headers = ChargilyFake.signed(checkout_id)
    assert (await client.post("/payment-requests/webhook/chargily", content=body, headers=headers)).status_code == 200


async def _row(session_factory, request_id: str) -> PaymentRequest:
    async with session_factory() as session:
        return await session.get(PaymentRequest, uuid.UUID(request_id))


async def _reconcile(session_factory, *, after_seconds: int = 0) -> int:
    async with session_factory() as session:
        return await payment_requests.reconcile_gateway(
            session, now=datetime.now(UTC) + timedelta(seconds=after_seconds)
        )


async def _ledger(session_factory) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(WalletTransaction).where(
            WalletTransaction.idempotency_key.like("payment_request:%")))


def _down_transport(monkeypatch: pytest.MonkeyPatch, chargily: ChargilyFake, *, mode: str) -> None:
    """**Chargily متوقّف** — مهلةٌ أو `502`/`504` منه — لكلِّ نداء."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host != "pay.chargily.net":
            return httpx.Response(599)
        if mode == "timeout":
            raise httpx.ConnectTimeout("timed out", request=request)
        return httpx.Response(int(mode), text="<html>Bad Gateway</html>")

    monkeypatch.setattr(payment_gateways, "http_transport", httpx.MockTransport(handler))


# ================================================================== أ) Chargily


@pytest.mark.parametrize("mode", ["timeout", "502", "504"])
async def test_an_outage_is_said_in_the_payers_language_and_opens_no_page(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    await _queued()

    _down_transport(monkeypatch, chargily, mode=mode)
    first = await _checkout(client, rider["headers"], method_id)
    assert first.status_code == 503 and first.json()["code"] == "payment_gateway_down"
    assert "متوقّفٌ مؤقّتاً" in first.json()["message"]
    # **والفرنسيّةُ من التطبيق برمزه** (`payment_gateway_down`) — الرمزُ نفسُه بأيِّ لغة
    french = await _checkout(client, rider["headers"] | {"Accept-Language": "fr"}, method_id)
    assert french.status_code == 503 and french.json()["code"] == "payment_gateway_down"
    # **لا صفحةَ ولا طلب** — ولا يُرسل الدافعُ إلى ما لا يُفتح
    assert chargily.created == []
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(PaymentRequest)) == 0
    # **إشعارٌ واحدٌ للمالك** ولو اصطدم بالانقطاع دافعان، **والقائمةُ تقول «متوقّف»**
    assert _kinds(await _queued()).count("gateway_down") == 1
    methods = (await client.get("/payment-requests/methods", headers=rider["headers"])).json()["methods"]
    assert next(m for m in methods if m["gateway"])["down"] is True

    # **وعاد** ⇐ إشعارُ العودة مرّةً، والصفحةُ تُفتح
    install_transport(monkeypatch)
    assert (await _checkout(client, rider["headers"], method_id)).status_code == 201
    assert _kinds(await _queued()).count("gateway_up") == 1


async def test_the_background_probe_notices_the_outage_and_the_return(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import gateway_health

    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    await add_gateway_method(session_factory, "chargily")
    await _queued()
    _down_transport(monkeypatch, chargily, mode="504")
    async with session_factory() as session:
        assert await gateway_health.probe_all(session) == 1
    install_transport(monkeypatch)
    async with session_factory() as session:
        assert await gateway_health.probe_all(session) == 0
    assert _kinds(await _queued()) == ["gateway_down", "gateway_up"]


async def test_coming_back_without_paying_is_not_pending_and_pays_again_at_once(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    install_transport(monkeypatch)
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await _checkout(client, rider["headers"], method_id)).json()["request"]["id"]

    # **عاد والصفحةُ «معلّقة» عند Chargily** — لم يُكمل البطاقة: ملغاةٌ بسببها، لا «تنتظر»
    returned = (await client.post(f"/payment-requests/{request_id}/refresh", headers=rider["headers"])).json()
    assert returned["status"] == "cancelled" and returned["phase"] == "cancelled"
    assert "لم يكتمل الدفع" in returned["cancel_reason"]
    # **ويدفع من جديد فوراً**
    again = await _checkout(client, rider["headers"], method_id)
    assert again.status_code == 201 and again.json()["request"]["id"] != request_id


async def test_an_unreachable_gateway_on_return_is_unknown_not_blocking(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await _checkout(client, rider["headers"], method_id)).json()["request"]["id"]
    _down_transport(monkeypatch, chargily, mode="timeout")
    returned = await client.post(f"/payment-requests/{request_id}/refresh", headers=rider["headers"])
    # **لا خطأ ولا «قيد المعالجة»** — لا نعرف: يبقى بلا حجب، والتسويةُ تسأل في الخلفية
    assert returned.status_code == 200 and returned.json()["phase"] == "unconfirmed"


async def test_paid_is_processing_on_return_and_the_reconciliation_credits_it_once(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await _checkout(client, rider["headers"], method_id)).json()["request"]["id"]
    chargily.status["chk_0001"] = "paid"

    returned = (await client.post(f"/payment-requests/{request_id}/refresh", headers=rider["headers"])).json()
    # **«وصل دفعُك ويُعالَج»** — ولا يُقيَّد من العودة (§٧٤-ط/٥)
    assert returned["status"] == "pending" and returned["phase"] == "processing"
    assert await balance(client, rider["headers"]) == "0"
    # **ولا يلغيه صاحبُه** — المالُ وصل
    cancelled = await client.post(f"/payment-requests/{request_id}/cancel", json={}, headers=rider["headers"])
    assert cancelled.status_code == 409

    # **الإشعارُ ضاع** ⇐ التسويةُ تقيِّده بعد مهلته، مرّةً واحدة
    assert await _reconcile(session_factory) == 0
    assert await _reconcile(session_factory, after_seconds=payment_requests.WEBHOOK_GRACE_SECONDS + 1) == 1
    assert await _reconcile(session_factory, after_seconds=600) == 0
    await _deliver(client, "chk_0001")
    assert await balance(client, rider["headers"]) == "3000"
    assert await _ledger(session_factory) == 1


async def test_two_quick_taps_open_one_checkout(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    first, second = await asyncio.gather(
        _checkout(client, rider["headers"], method_id), _checkout(client, rider["headers"], method_id)
    )
    assert {first.status_code, second.status_code} <= {200, 201}
    assert first.json()["request"]["id"] == second.json()["request"]["id"]
    assert first.json()["checkout_url"] == second.json()["checkout_url"]
    assert len(chargily.created) == 1


async def test_a_late_webhook_after_the_page_was_closed_still_credits_once(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await _checkout(client, rider["headers"], method_id)).json()["request"]["id"]
    await client.post(f"/payment-requests/{request_id}/refresh", headers=rider["headers"])
    assert (await _row(session_factory, request_id)).status is PaymentRequestStatus.CANCELLED

    # **ثمّ أكمل البطاقة في الصفحة نفسِها** ⇐ الإشعارُ الموقَّعُ يقيِّده، ومكرَّرُه لا يقيِّد ثانية
    chargily.status["chk_0001"] = "paid"
    await _deliver(client, "chk_0001")
    await _deliver(client, "chk_0001")
    assert (await _row(session_factory, request_id)).status is PaymentRequestStatus.APPROVED
    assert await balance(client, rider["headers"]) == "3000"


async def test_the_reconciliation_finds_a_paid_page_that_was_closed_here(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await _checkout(client, rider["headers"], method_id)).json()["request"]["id"]
    await client.post(f"/payment-requests/{request_id}/refresh", headers=rider["headers"])
    chargily.status["chk_0001"] = "paid"
    # **لا إشعار** — التسويةُ تعيده «قيد المعالجة» ثمّ تقيِّده بعد مهلة الإشعار، مرّةً واحدة
    await _reconcile(session_factory)
    row = await _row(session_factory, request_id)
    assert row.status is PaymentRequestStatus.PENDING and row.gateway_paid_at is not None
    await _reconcile(session_factory, after_seconds=payment_requests.WEBHOOK_GRACE_SECONDS + 1)
    await _reconcile(session_factory, after_seconds=600)
    assert (await _row(session_factory, request_id)).status is PaymentRequestStatus.APPROVED
    assert await balance(client, rider["headers"]) == "3000" and await _ledger(session_factory) == 1


async def test_failed_and_cancelled_at_the_gateway_are_final_and_never_pending(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    for status, phase in (("failed", "rejected"), ("canceled", "cancelled")):
        request_id = (await _checkout(client, rider["headers"], method_id)).json()["request"]["id"]
        chargily.status[f"chk_{len(chargily.created):04d}"] = status
        body = (await client.post(f"/payment-requests/{request_id}/refresh", headers=rider["headers"])).json()
        assert body["phase"] == phase
    assert await balance(client, rider["headers"]) == "0"


async def test_paid_but_not_activated_stays_in_processing_and_the_owner_is_told_once(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await _checkout(client, rider["headers"], method_id)).json()["request"]["id"]
    chargily.status["chk_0001"] = "paid"
    chargily.amount["chk_0001"] = 2000  # **مبلغٌ لا يطابق** — لا يُقيَّد بتخمين
    await _deliver(client, "chk_0001")
    mine = (await client.get("/payment-requests/me", headers=rider["headers"])).json()[0]
    assert mine["phase"] == "processing" and mine["status"] == "pending"
    await _queued()
    late = payment_requests.REVIEW_ALERT_MINUTES * 60 + 5
    await _reconcile(session_factory, after_seconds=late)
    await _reconcile(session_factory, after_seconds=late + 120)
    assert _kinds(await _queued()).count("payment_stuck") == 1
    assert await balance(client, rider["headers"]) == "0"
    # **والمالكُ يحسمه من طابور الماليّة** بمبلغ ما وصل
    owner = await _owner(session_factory)
    approved = await client.post(f"/admin/payment-requests/{request_id}/approve", json={"credited_amount": "2000"}, headers=owner)
    assert approved.status_code == 200 and await balance(client, rider["headers"]) == "2000"


async def test_paying_twice_for_one_subscription_activates_once_and_the_extra_goes_to_the_wallet(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await add_gateway_method(session_factory, "chargily")
    captain = await _algerian_captain(client, session_factory)
    plan_id = str(await ensure_plan(session_factory, country="DZ", name="خطةُ الجزائر", price="1500"))
    body = {"purpose": "subscription", "plan_id": plan_id, "amount": None}
    # **الأولى لا نعرف حالَها** (Chargily لا يجيب) — فدفع ثانيةً
    first = (await _checkout(client, captain["headers"], method_id, **body)).json()["request"]["id"]
    second = (await _checkout(client, captain["headers"], method_id, **body)).json()["request"]["id"]
    chargily.status["chk_0002"] = "paid"
    await _deliver(client, "chk_0002")
    assert (await _row(session_factory, second)).subscription_id is not None
    await _queued()

    # **ثمّ ظهر أن الأولى دُفعت أيضاً** ⇐ مبلغُها في المحفظة، والاشتراكُ لا يُفعَّل ثانية، والمالكُ يُشعَر
    chargily.status["chk_0001"] = "paid"
    await _deliver(client, "chk_0001")
    late = await _row(session_factory, first)
    assert late.status is PaymentRequestStatus.APPROVED and late.subscription_id is None
    assert late.outcome_note == payment_reasons_paid_twice()
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(DriverSubscription)) == 1
    wallet = await client.get("/wallet/me?wallet=driver", headers=captain["headers"])
    assert wallet.json()["balance"] == "1500"
    assert "payment_extra" in _kinds(await _queued())


def payment_reasons_paid_twice() -> str:
    from app.services import payment_reasons

    return payment_reasons.PAID_TWICE


# ================================================================== ب) BaridiMob


async def _configure(client: AsyncClient, owner: dict, **override) -> httpx.Response:
    body = {
        "account_number": TEST_RIP, "account_holder": "صاحبُ الحساب", "account_holder_latin": "ACCOUNT HOLDER",
        "min_amount": "500", "max_amount": "20000", "enabled": True,
    } | override
    return await client.put("/admin/transfers/settings", json=body, headers=owner)


async def _baridimob_id(session_factory) -> uuid.UUID:
    async with session_factory() as session:
        return await session.scalar(select(PayMethod.id).where(PayMethod.code == "baridimob", PayMethod.country_code == CountryCode.DZ))


async def _hide_fixture_baridimob(session_factory) -> None:
    """**طريقةُ الاختبار القائمة تُطفأ وتُفرَّغ** — فيبدأ القياسُ من «لم تُضبط» كما في الإنتاج."""
    async with session_factory() as session:
        await session.execute(update(PayMethod).where(PayMethod.code == "baridimob").values(
            enabled=False, account_number=None, account_holder=None))
        await session.commit()


async def test_the_method_is_hidden_until_the_owner_fills_it_and_turns_it_on(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await algeria_market(session_factory)
    await _hide_fixture_baridimob(session_factory)
    rider = await rider_session(client, ALGERIAN_RIDER)
    owner = await _owner(session_factory)

    def listed(body: dict) -> list[str]:
        return [m["code"] for m in body["methods"]]

    assert "baridimob" not in listed((await client.get("/payment-requests/methods", headers=rider["headers"])).json())
    # **لا تُشعل ناقصة** — ولا RIP بغير عشرين رقماً
    assert (await _configure(client, owner, account_holder_latin=None)).status_code == 422
    assert (await _configure(client, owner, account_number="0079999900089356624")).json()["field"] == "account_number"
    assert (await _configure(client, owner, min_amount="30000")).status_code == 422
    # **والمشرفُ لا يقرؤها ولا يكتبها** — المالكُ وحدَه
    assert (await client.get("/admin/transfers/settings", headers=admin_headers)).status_code == 403
    assert (await _configure(client, admin_headers)).status_code == 403

    saved = await _configure(client, owner, account_number="0079 9999 0000 0000 0000")
    assert saved.status_code == 200 and saved.json()["enabled"] is True and saved.json()["account_number"] == TEST_RIP
    method = next(m for m in (await client.get("/payment-requests/methods", headers=rider["headers"])).json()["methods"]
                  if m["code"] == "baridimob")
    assert method["account_number"] == TEST_RIP and method["account_holder_latin"] == "ACCOUNT HOLDER"
    assert method["min_amount"] == "500" and method["max_amount"] == "20000" and method["requires_receipt"] is True


async def test_amounts_outside_the_limits_are_refused_and_the_date_is_required(
    client: AsyncClient, session_factory
) -> None:
    await algeria_market(session_factory)
    await _configure(client, await _owner(session_factory))
    rider = await rider_session(client, ALGERIAN_RIDER)
    method = await _baridimob_id(session_factory)
    assert (await submit(client, rider["headers"], method, "400")).json()["field"] == "amount"
    assert (await submit(client, rider["headers"], method, "25000")).json()["field"] == "amount"
    assert (await submit(client, rider["headers"], method, "1500", transfer_date=None)).json()["field"] == "transfer_date"
    future = (date.today() + timedelta(days=5)).isoformat()
    assert (await submit(client, rider["headers"], method, "1500", transfer_date=future)).json()["field"] == "transfer_date"
    created = await submit(client, rider["headers"], method, "1500", reference="BM-77001")
    assert created.status_code == 201 and created.json()["phase"] == "in_review"
    assert created.json()["public_ref"].startswith("TX-")


async def _pending_transfer(client, session_factory, *, reference: str = "BM-90001", amount: str = "1500") -> tuple[dict, str]:
    await algeria_market(session_factory)
    owner = await _owner(session_factory)
    await _configure(client, owner)
    rider = await rider_session(client, ALGERIAN_RIDER)
    client_id = str(uuid.uuid4())
    created = await submit(client, rider["headers"], await _baridimob_id(session_factory), amount, reference=reference,
                           client_id=client_id)
    assert created.status_code == 201, created.text
    assert created.json()["id"] == client_id
    return rider, client_id


async def test_the_reviewer_approves_once_and_the_owner_is_told(client: AsyncClient, session_factory) -> None:
    rider, request_id = await _pending_transfer(client, session_factory)
    reviewer = await _reviewer(session_factory)
    queued = _kinds(await _queued())
    assert "topup_requested" in queued  # **كلُّ طلبٍ جديدٍ يصل المالك**

    listed = (await client.get("/admin/transfers", headers=reviewer)).json()
    row = next(item for item in listed if item["id"] == request_id)
    # **اسمٌ أوّلُ وهاتفٌ مقنَّع** — ولا شيءَ غيرُهما من صاحبه
    assert row["first_name"] == ALGERIAN_RIDER["name"].split()[0]
    assert row["masked_phone"].startswith("+213 ") and "••" in row["masked_phone"]
    assert row["masked_phone"].endswith(ALGERIAN_RIDER["phone"][-3:])
    assert not {"user_id", "phone", "email", "user_phone", "user_name"} & set(row)
    assert row["reference"] == "BM-90001" and row["transfer_date"] == date.today().isoformat()
    receipt = await client.get(f"/admin/transfers/{request_id}/receipt", headers=reviewer)
    assert receipt.status_code == 200 and receipt.content == PNG and "no-store" in receipt.headers["cache-control"]

    approved = await client.post(f"/admin/transfers/{request_id}/approve", headers=reviewer)
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    assert approved.json()["reviewed_by"] == "reviewer"
    again = await client.post(f"/admin/transfers/{request_id}/approve", headers=reviewer)
    assert again.status_code == 409
    assert await balance(client, rider["headers"]) == "1500" and await _ledger(session_factory) == 1
    events = await _queued()
    decision = next(event for event in events if event["k"] == "transfer_approved")
    assert decision["x"]["by"] == "reviewer"
    # **ونقرُ الإشعار يفتح صفحةَ المراجعة** — سجلُّه «تحويل» لا «طلبُ دفعٍ» عامّ
    from app.services import admin_alerts

    async with session_factory() as session:
        drafts = await admin_alerts.resolve_all(session, events)
    approved = next(draft for draft in drafts if draft.kind == "transfer_approved")
    assert approved.record_type == "transfer" and approved.data["by"] == "reviewer"


async def test_the_owner_approves_from_the_same_page(client: AsyncClient, session_factory) -> None:
    rider, request_id = await _pending_transfer(client, session_factory)
    owner = await _owner(session_factory)
    approved = await client.post(f"/admin/transfers/{request_id}/approve", headers=owner)
    assert approved.status_code == 200 and approved.json()["reviewed_by"] == "owner"
    assert await balance(client, rider["headers"]) == "1500"


async def test_a_rejection_carries_its_reason_and_moves_no_money(client: AsyncClient, session_factory) -> None:
    rider, request_id = await _pending_transfer(client, session_factory)
    reviewer = await _reviewer(session_factory)
    await _queued()
    assert (await client.post(f"/admin/transfers/{request_id}/reject", json={"reason": "x"}, headers=reviewer)).status_code == 422
    rejected = await client.post(
        f"/admin/transfers/{request_id}/reject", json={"reason": "لم يصل المبلغ إلى الحساب"}, headers=reviewer
    )
    assert rejected.status_code == 200 and rejected.json()["rejection_reason"] == "لم يصل المبلغ إلى الحساب"
    mine = (await client.get("/payment-requests/me", headers=rider["headers"])).json()[0]
    assert mine["status"] == "rejected" and mine["rejection_reason"] == "لم يصل المبلغ إلى الحساب"
    assert await balance(client, rider["headers"]) == "0"
    # **كما يحلّها العامل** — «دفعةٌ فشلت» لقرار إنسانٍ تُسقط، و«تحويلٌ رُفض» يبقى باسمه
    from app.services import admin_alerts

    async with session_factory() as session:
        kinds = [draft.kind for draft in await admin_alerts.resolve_all(session, await _queued())]
    assert "transfer_rejected" in kinds and "payment_failed" not in kinds


async def test_a_transaction_number_is_never_accepted_twice_and_is_flagged(client: AsyncClient, session_factory) -> None:
    rider, request_id = await _pending_transfer(client, session_factory, reference="BM-55555")
    await _queued()
    twin = await submit(client, rider["headers"], await _baridimob_id(session_factory), "1500", reference="bm-55555",
                        receipt=PNG + b"x")
    assert twin.status_code == 409 and twin.json()["code"] == "payment_already_submitted"
    assert "transfer_duplicate" in _kinds(await _queued())
    # **وإرسالُ الطلب نفسِه مرّتين** طلبٌ واحد
    same = await submit(client, rider["headers"], await _baridimob_id(session_factory), "1500", reference="BM-55555",
                        client_id=request_id)
    assert same.status_code in (200, 201) and same.json()["id"] == request_id


async def test_two_approvals_at_the_same_time_credit_once(client: AsyncClient, session_factory) -> None:
    rider, request_id = await _pending_transfer(client, session_factory)
    reviewer, owner = await _reviewer(session_factory), await _owner(session_factory)
    results = await asyncio.wait_for(
        asyncio.gather(
            client.post(f"/admin/transfers/{request_id}/approve", headers=reviewer),
            client.post(f"/admin/transfers/{request_id}/approve", headers=owner),
        ),
        timeout=30,
    )
    assert Counter(result.status_code for result in results) == Counter({200: 1, 409: 1})
    assert await balance(client, rider["headers"]) == "1500" and await _ledger(session_factory) == 1


async def test_the_reviewer_opens_no_other_page_and_no_other_market(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    from app.main import app

    _, request_id = await _pending_transfer(client, session_factory)
    reviewer = await _reviewer(session_factory)
    allowed = {
        "/admin/transfers", "/admin/transfers/{request_id}/receipt", "/admin/transfers/{request_id}/approve",
        "/admin/transfers/{request_id}/reject",
    }
    owner_only = {"/admin/transfers/settings", "/admin/transfers/reviewers"}
    opened: list[str] = []
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api/v1/admin"):
            continue
        short = path.removeprefix("/api/v1")
        if short in allowed:
            continue
        url = short
        for name in getattr(route, "param_convertors", {}):
            url = url.replace("{" + name + "}", str(uuid.uuid4()))
        for method in route.methods - {"HEAD", "OPTIONS"}:
            response = await client.request(method, url, headers=reviewer, json={})
            if response.status_code not in (401, 403):
                opened.append(f"{method} {short} → {response.status_code}")
    # **ولا صفحةَ المالك نفسِها** — الإعدادُ وحسابُ المراجع
    assert opened == [], opened
    for path in owner_only:
        assert (await client.get(path, headers=reviewer)).status_code == 403

    # **ولا سوقاً غيرَ الجزائر ولا طريقةً غيرَ BaridiMob** — ٤٠٤ لا ٤٠٣
    async with session_factory() as session:
        await session.execute(update(PaymentRequest).where(PaymentRequest.id == uuid.UUID(request_id)).values(
            country_code=CountryCode.JO))
        await session.commit()
    assert (await client.post(f"/admin/transfers/{request_id}/approve", headers=reviewer)).status_code == 404
    assert (await client.get("/admin/transfers", headers=reviewer)).json() == []


async def test_the_reviewer_must_enrol_a_second_factor_first(client: AsyncClient, session_factory) -> None:
    await algeria_market(session_factory)
    reviewer = await _reviewer(session_factory, factor=False)
    refused = await client.get("/admin/transfers", headers=reviewer)
    assert refused.status_code == 403 and refused.json()["code"] == "totp_enrollment_required"


async def test_the_owner_creates_the_reviewer_who_changes_the_password_first(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    owner = await _owner(session_factory)
    body = {"name": "صديق المالك", "username": "baridi.review1", "password": "Temp-Pass-2026!x"}
    assert (await client.post("/admin/transfers/reviewers", json=body, headers=admin_headers)).status_code == 403
    created = await client.post("/admin/transfers/reviewers", json=body, headers=owner)
    assert created.status_code == 201, created.text
    assert created.json()["must_change_password"] is True and created.json()["has_factor"] is False
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(created.json()["id"]))
        assert set(user.roles) == {UserRole.PAYMENT_REVIEWER} and user.phone is None
        assert user.country_code is CountryCode.DZ
    listed = (await client.get("/admin/transfers/reviewers", headers=owner)).json()
    assert [row["username"] for row in listed] == ["baridi.review1"]
    # **يدخل اللوحة** — ولا يدخل تطبيقَ الراكب
    login = await client.post("/auth/login", json={"username": "baridi.review1", "password": body["password"], "app": "panel"})
    assert login.status_code == 200, login.text
    rider_app = await client.post("/auth/login", json={"username": "baridi.review1", "password": body["password"], "app": "rider"})
    assert rider_app.status_code == 403
