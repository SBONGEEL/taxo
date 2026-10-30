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
from tests.helpers import _enable_provider, enable_push_provider, pushes_to, register_device, rider_session
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


@pytest.mark.parametrize(
    ("answer", "status", "reason"),
    [
        # **بأجوبة وضع التجربة حرفاً** (قِيست ٢٠٢٦-١٠-٢٩ ببطاقات الوثائق): الرفضُ · زرُّ «إلغاء» · بطاقةُ المهلة
        ({"orderStatus": 6, "respCode": "05", "respCode_desc": "Refusée"}, "rejected", "رفض الوسيطُ الدفع"),
        ({"orderStatus": 3, "respCode": "17", "respCode_desc": "Annulée par l'utilisateur"}, "cancelled", "أُلغي الدفعُ عند الوسيط"),
        ({"orderStatus": 3, "respCode": "68", "respCode_desc": "Délai dépassé"}, "cancelled", "انتهت مهلة الدفع، أعد المحاولة"),
    ],
)
async def test_a_refusal_a_cancel_and_a_timeout_settle_with_our_words_and_credit_nothing(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, answer: dict, status: str, reason: str
) -> None:
    await algeria_market(session_factory)
    _, sofizpay = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    rider = await _rider_with_email(client, session_factory)
    opened = (await _open(client, rider["headers"], method_id)).json()
    before = await _entries(session_factory)
    sofizpay.check[opened["request"]["reference"]] |= answer
    refreshed = (await client.post(f"/payment-requests/{opened['request']['id']}/refresh", headers=rider["headers"])).json()
    assert refreshed["status"] == status
    # **بلغة الطلب لا بفرنسيّة البنك** — والسببُ في أيِّ حقلٍ كُتب
    said = refreshed.get("rejection_reason") or refreshed.get("cancel_reason") or refreshed.get("outcome_note")
    assert said == reason, refreshed
    assert await _entries(session_factory) == before and await balance(client, rider["headers"]) == "0"


async def test_an_allowlist_shows_and_opens_sofizpay_for_its_numbers_alone(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**التشغيلُ الأوّلُ لقائمة** (أمرُ المالك ٢٠٢٦-١٠-٢٩): خارجُها لا يراها ولا يفتحها بمعرّفها؛ وفيها يفتحها؛ وفارغةٌ للجميع."""
    from app.models.enums import CountryCode, ProviderKey
    from app.services.providers import credentials as credentials_service

    await algeria_market(session_factory)
    install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    rider = await _rider_with_email(client, session_factory)

    async def allow(numbers: str) -> None:
        async with session_factory() as session:
            await credentials_service.upsert(
                session, provider_key=ProviderKey.SOFIZPAY, country_code=CountryCode.DZ, values={"allowlist": numbers}
            )
            await session.commit()

    async def shown() -> bool:
        methods = (await client.get("/payment-requests/methods", headers=rider["headers"])).json()["methods"]
        return any(m["id"] == str(method_id) for m in methods)

    await allow("+213500000001, +213500000002")
    assert not await shown()
    refused = await _open(client, rider["headers"], method_id)
    assert refused.status_code == 503 and refused.json()["code"] == "payment_gateway_unavailable"
    await allow("+213500000001,+213551234567")
    assert await shown() and (await _open(client, rider["headers"], method_id)).status_code == 201
    await allow("")
    assert await shown()


async def test_no_email_asks_for_it_once_writes_nothing_and_then_pays(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**البريدُ شرطُ SofizPay** (قِيس ٢٠٢٦-١٠-٢٩): بلا بريدٍ ⇒ `422 payment_email_required` ولا طلبَ ولا صفحة؛ ويضعه صاحبُه
    (`PATCH /auth/me`، غيرَ مُثبَت) ⇒ تُفتح الصفحةُ ويصل البريدُ إلى الوسيط."""
    from app.models.payment_request import PaymentRequest

    await algeria_market(session_factory)
    _, sofizpay = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    rider = await rider_session(client, ALGERIAN_RIDER)
    asked = await _open(client, rider["headers"], method_id)
    assert asked.status_code == 422 and asked.json()["code"] == "payment_email_required"
    assert asked.json()["field"] == "email" and sofizpay.created == []
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(PaymentRequest)) == 0
    bad = await client.patch("/auth/me", json={"email": "not-an-email"}, headers=rider["headers"])
    assert bad.status_code == 422
    saved = await client.patch("/auth/me", json={"email": " Rider@Example.DZ "}, headers=rider["headers"])
    assert saved.status_code == 200
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(rider["user"]["id"]))
        assert user.email == "rider@example.dz" and user.email_verified_at is None
    assert (await _open(client, rider["headers"], method_id)).status_code == 201
    assert len(sofizpay.created) == 1


async def test_the_memo_reaches_sofizpay_in_latin_letters(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**إيصالُ SofizPay الحقيقيّ** (٢٠٢٦-١٠-٣٠، طلبُ اشتراكٍ 200 دج) طبع «TAXO اشتراك» رموزاً مكسورة — خطُّ PDF عندهم بلا عربيّة.
    فالمذكّرةُ التي تصله لاتينيّةٌ بالفرنسيّة وتحت ٢٨ بايتاً، والوصفُ العربيُّ يبقى لغيره."""
    from app.services.payment_gateways.sofizpay import latin_memo

    await algeria_market(session_factory)
    _, sofizpay = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    rider = await _rider_with_email(client, session_factory)
    assert (await _open(client, rider["headers"], method_id)).status_code == 201
    memo = sofizpay.created[-1]["memo"]
    assert memo == "TAXO recharge" and memo.isascii() and len(memo.encode()) <= 28
    assert latin_memo("TAXO اشتراك") == "TAXO abonnement"
    assert latin_memo("شحن") == "TAXO"
    assert len(latin_memo("TAXO " + "x" * 60).encode()) <= 28


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        # **الرفضُ الحقيقيُّ الأوّل** (٢٠٢٦-١٠-٣٠، الطلب 77137267): SATIM بالعربيّة ورمزُه AB — والدافعُ كان يقرأ «رفض الوسيطُ الدفع» وحدَها
        ({"orderStatus": 6, "respCode": "AB", "respCode_desc": "تم رفض المعاملة : رمز التحقّق (CVV) غير صحيح. يُرجى التحقّق والمحاولة مجدّدًا   Error Code:AB",
          "actionCodeDescription": "تم رفض المعاملة : رمز التحقق (CVV) غير صحيح. Error Code:140"}, "رمز التحقّق (CVV) غير صحيح، أعد المحاولة"),
        # sandbox ٢٠٢٦-١٠-٣٠: بطاقةُ «رصيدٌ لا يكفي»
        ({"orderStatus": 6, "respCode": "51", "respCode_desc": "Fonds insuffisants", "actionCodeDescription": "Insufficient funds"}, "الرصيد غير كافٍ"),
        # رمزٌ لا نعرفه ورسالةٌ فرنسيّةٌ معروفةُ الكلمات ⇐ الكلماتُ تمسكها
        ({"orderStatus": 6, "respCode": "ZZ", "respCode_desc": "Carte expirée"}, "البطاقة منتهية الصلاحية"),
        ({"orderStatus": 6, "respCode": "ZZ", "respCode_desc": "Limit exceeded"}, "تجاوزت الحدّ المسموح"),
        # ولا رمزَ ولا كلمةَ نعرفها ⇐ العامُّ كما كان، **ونصُّ البنك لا يصل**
        ({"orderStatus": 6, "respCode": "ZZ", "respCode_desc": "Something the bank said"}, "رفض الوسيطُ الدفع"),
    ],
)
async def test_a_bank_refusal_reaches_the_payer_in_our_words_and_its_raw_code_reaches_the_panel_alone(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, answer: dict, reason: str
) -> None:
    """SPEC §٨٥/٩ — سببٌ عربيٌّ ثابتٌ على شاشة الدافع بأيِّ لغةٍ جاء البنك، ورمزُه ورسالتُه الخامّةُ في اللوحة وحدَها، وإشعارٌ لصاحبه."""
    await algeria_market(session_factory)
    await enable_push_provider(session_factory)
    _, sofizpay = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    rider = await _rider_with_email(client, session_factory)
    await register_device(client, rider["headers"], token="fcm-rejected-1")
    opened = (await _open(client, rider["headers"], method_id)).json()
    before = await _entries(session_factory)
    sofizpay.check[opened["request"]["reference"]] |= answer
    refreshed = (await client.post(f"/payment-requests/{opened['request']['id']}/refresh", headers=rider["headers"])).json()
    assert refreshed["status"] == "rejected" and refreshed["rejection_reason"] == reason, refreshed
    # **نصُّ البنك لا يصل المستخدمَ** — لا في السبب ولا في حقلٍ آخر من حمولته
    assert "gateway_code" not in refreshed and answer["respCode_desc"] not in str(refreshed)
    assert await _entries(session_factory) == before
    # **واللوحةُ ترى الرمزَ والرسالةَ الخامّة** للدعم
    owner = await _owner(session_factory)
    rows = (await client.get("/admin/payment-requests", params={"country": "DZ"}, headers=owner)).json()
    row = next(r for r in rows if r["id"] == opened["request"]["id"])
    assert row["rejection_reason"] == reason and row["gateway_code"] == answer["respCode"]
    assert answer["respCode_desc"] in row["gateway_message"]
    # **وصاحبُه يُبلَغ** بكلماتنا — إشعارٌ واحدٌ بنوعه ومعرّفِ طلبه، والنصُّ الخامُّ ليس فيه
    pushes = [p for p in await pushes_to("fcm-rejected-1") if p.get("data", {}).get("type") == "payment_request_rejected"]
    assert len(pushes) == 1 and pushes[0]["body"] == reason and pushes[0]["data"]["request_id"] == opened["request"]["id"], pushes
    assert answer["respCode_desc"] not in str(pushes[0])
