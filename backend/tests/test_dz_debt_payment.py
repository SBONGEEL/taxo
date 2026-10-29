"""سدادُ دَين الكبتن في الجزائر بـSofizPay (أمرُ المالك ٢٠٢٦-١٠-٢٩، SPEC §٨٥/٨).

**قِيس على الإنتاج قبله**: شاشةُ الدَّين كليك أردنيّ، والشحنُ لا يحصّل الدَّين إلا في الرحلة التالية — **ومن بلغ سقفَ ٦٥٠ دج لا يأخذ رحلةً**،
فلا رحلةَ تالية: منعٌ بلا مخرج. **والآن**: شحنُ الكبتن المؤكَّدُ من SofizPay يسدّد دَينَه **في المعاملة نفسِها**، مرّةً، وجزئيّاً إن قلّ،
ويُرفع المنعُ عند الصفر.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.debt import DriverDebt
from app.models.driver import Driver
from app.models.enums import CountryCode, Currency, DriverDebtSource, DriverDebtStatus, WalletTransactionType
from app.models.payment_setting import PaymentSetting
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.services import payment_requests
from tests.payment_fakes import add_gateway_method, install_transport, sofizpay_signed
from tests.test_payment_requests import _algerian_captain, algeria_market, balance

CEILING = Decimal("650.000")


@pytest.fixture(autouse=True)
def _no_double_tap_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)


async def _captain_in_debt(client: AsyncClient, session_factory, *amounts: str, blocked: bool = False) -> dict:
    """كبتنٌ جزائريٌّ ببريدٍ (SofizPay يشترطه) وعليه عمولاتُ كاشٍ لم تُحصَّل — **الأقدمُ أوّلاً** بترتيب الإدراج."""
    captain = await _algerian_captain(client, session_factory)
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(captain["user_id"]))
        user.email = "captain@example.dz"
        setting = await session.scalar(select(PaymentSetting).where(PaymentSetting.country_code == CountryCode.DZ))
        if setting is None:
            session.add(PaymentSetting(country_code=CountryCode.DZ, driver_debt_ceiling=CEILING))
        else:
            setting.driver_debt_ceiling = CEILING
        for amount in amounts:
            session.add(DriverDebt(
                driver_id=captain["driver_id"], country_code=CountryCode.DZ, source=DriverDebtSource.RIDE_COMMISSION,
                amount=Decimal(amount), collected=Decimal("0"), currency=Currency.DZD, status=DriverDebtStatus.OUTSTANDING,
            ))
            await session.flush()
        driver = await session.get(Driver, captain["driver_id"])
        driver.debt_blocked = blocked
        await session.commit()
    return captain


async def _pay(client: AsyncClient, captain: dict, method_id: uuid.UUID, amount: str, sofizpay) -> tuple[dict, str]:
    opened = await client.post(
        "/payment-requests/checkout",
        json={"provider_id": str(method_id), "purpose": "wallet_topup", "amount": amount},
        headers=captain["headers"],
    )
    assert opened.status_code == 201, opened.text
    request = opened.json()["request"]
    return request, request["reference"]


def _notice(cib_id: str, amount: str) -> dict:
    return sofizpay_signed({"event": "cib.payment.updated", "payment_status": "success", "cib_transaction_id": cib_id,
                            "amount": int(Decimal(amount) * 100)})


async def _state(session_factory, captain: dict) -> tuple[Decimal, bool, list[str]]:
    async with session_factory() as session:
        rows = (await session.scalars(
            select(DriverDebt).where(DriverDebt.driver_id == captain["driver_id"]).order_by(DriverDebt.created_at)
        )).all()
        driver = await session.get(Driver, captain["driver_id"])
        left = sum((r.amount - r.collected for r in rows if r.status is DriverDebtStatus.OUTSTANDING), Decimal("0"))
        return left, driver.debt_blocked, [r.status.value for r in rows]


async def _collections(session_factory) -> int:
    async with session_factory() as session:
        return int(await session.scalar(
            select(func.count()).select_from(WalletTransaction).where(
                WalletTransaction.type == WalletTransactionType.COMMISSION)
        ) or 0)


async def test_a_full_payment_clears_the_debt_at_once_and_lifts_the_block_at_the_cap(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**بلغ السقفَ فمُنع** ⇒ يدفع دَينَه كاملاً بـSofizPay ⇒ صفرٌ ومرفوعُ المنع **في الإشعار نفسِه** لا في رحلةٍ لن تأتيه."""
    await algeria_market(session_factory)
    _, sofizpay = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    captain = await _captain_in_debt(client, session_factory, "400", "300", blocked=True)
    assert (await _state(session_factory, captain))[:2] == (Decimal("700.000"), True)

    request, cib_id = await _pay(client, captain, method_id, "700", sofizpay)
    sofizpay.check[cib_id] |= {"orderStatus": 2, "respCode": "00"}
    applied = await client.post("/payment-requests/webhook/sofizpay", json=_notice(cib_id, "700"))
    assert applied.json()["applied"] == 1, applied.text

    left, blocked, statuses = await _state(session_factory, captain)
    assert left == 0 and blocked is False and statuses == ["settled", "settled"]
    assert await balance(client, captain["headers"]) == "0"


async def test_a_partial_payment_reduces_the_oldest_row_and_keeps_the_block_until_zero(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**«الجزئيُّ يُقبل ويُنقص»** (قرارُ المالك) — والمنعُ يُرفع عند الصفر لا قبله."""
    await algeria_market(session_factory)
    _, sofizpay = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    captain = await _captain_in_debt(client, session_factory, "400", "300", blocked=True)

    _, cib_id = await _pay(client, captain, method_id, "500", sofizpay)
    sofizpay.check[cib_id] |= {"orderStatus": 2, "respCode": "00"}
    await client.post("/payment-requests/webhook/sofizpay", json=_notice(cib_id, "500"))

    left, blocked, statuses = await _state(session_factory, captain)
    # ٤٠٠ كاملةً ثمّ ١٠٠ من الثانية ⇒ يبقى ٢٠٠، **وكلُّ ما دفعه ذهب إلى الدَّين**
    assert left == Decimal("200.000") and blocked is True and statuses == ["settled", "outstanding"]
    assert await balance(client, captain["headers"]) == "0"

    # **ثمّ يكمل** ⇒ صفرٌ ويُرفع المنع
    _, second = await _pay(client, captain, method_id, "200", sofizpay)
    sofizpay.check[second] |= {"orderStatus": 2, "respCode": "00"}
    await client.post("/payment-requests/webhook/sofizpay", json=_notice(second, "200"))
    assert (await _state(session_factory, captain))[:2] == (Decimal("0"), False)


async def test_a_payment_above_the_debt_keeps_the_rest_in_the_wallet(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    _, sofizpay = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    captain = await _captain_in_debt(client, session_factory, "300")
    _, cib_id = await _pay(client, captain, method_id, "1000", sofizpay)
    sofizpay.check[cib_id] |= {"orderStatus": 2, "respCode": "00"}
    await client.post("/payment-requests/webhook/sofizpay", json=_notice(cib_id, "1000"))
    assert (await _state(session_factory, captain))[0] == 0
    assert await balance(client, captain["headers"]) == "700"


async def test_a_repeated_signed_webhook_collects_the_debt_exactly_once(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    _, sofizpay = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    captain = await _captain_in_debt(client, session_factory, "400", "300")
    request, cib_id = await _pay(client, captain, method_id, "500", sofizpay)
    before = await _collections(session_factory)
    sofizpay.check[cib_id] |= {"orderStatus": 2, "respCode": "00"}
    notice = _notice(cib_id, "500")
    first = await client.post("/payment-requests/webhook/sofizpay", json=notice)
    again = await client.post("/payment-requests/webhook/sofizpay", json=notice)
    refreshed = await client.post(f"/payment-requests/{request['id']}/refresh", headers=captain["headers"])
    assert first.json()["applied"] == 1 and again.json()["applied"] == 0
    assert refreshed.json()["status"] == "approved"
    # **قيدان لا أربعة**: الصفُّ الكاملُ وجزءُ الثاني
    assert await _collections(session_factory) == before + 2
    assert (await _state(session_factory, captain))[0] == Decimal("200.000")


@pytest.mark.parametrize(
    ("answer", "status"),
    [
        ({"orderStatus": 6, "respCode": "05", "respCode_desc": "Refusée"}, "rejected"),
        ({"orderStatus": 3, "respCode": "17", "respCode_desc": "Annulée par l'utilisateur"}, "cancelled"),
    ],
)
async def test_a_refused_or_cancelled_payment_leaves_the_debt_and_the_block_as_they_were(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, answer: dict, status: str
) -> None:
    await algeria_market(session_factory)
    _, sofizpay = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    captain = await _captain_in_debt(client, session_factory, "700", blocked=True)
    request, cib_id = await _pay(client, captain, method_id, "700", sofizpay)
    before = await _collections(session_factory)
    sofizpay.check[cib_id] |= answer
    refreshed = await client.post(f"/payment-requests/{request['id']}/refresh", headers=captain["headers"])
    assert refreshed.json()["status"] == status
    assert await _state(session_factory, captain) == (Decimal("700.000"), True, ["outstanding"])
    assert await _collections(session_factory) == before
    assert await balance(client, captain["headers"]) == "0"


async def test_an_unsigned_webhook_collects_nothing(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    _, sofizpay = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    captain = await _captain_in_debt(client, session_factory, "700", blocked=True)
    _, cib_id = await _pay(client, captain, method_id, "700", sofizpay)
    forged = {"event": "cib.payment.updated", "payment_status": "success", "cib_transaction_id": cib_id, "amount": 70000}
    assert (await client.post("/payment-requests/webhook/sofizpay", json=forged)).status_code == 401
    assert (await _state(session_factory, captain))[:2] == (Decimal("700.000"), True)


async def test_a_subscription_payment_does_not_take_the_debt_first(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**مالُ الاشتراك لشراءٍ بعينه** — اقتطاعُ الدَّين قبله يُسقط الشراء ويترك الكبتنَ بلا اشتراكٍ دفع ثمنه."""
    from tests.helpers import ensure_plan

    await algeria_market(session_factory)
    _, sofizpay = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    captain = await _captain_in_debt(client, session_factory, "300")
    plan_id = await ensure_plan(session_factory, country="DZ", name="خطةُ دَينٍ جزائريّة", price="1500")
    opened = await client.post(
        "/payment-requests/checkout",
        json={"provider_id": str(method_id), "purpose": "subscription", "amount": "1500", "plan_id": str(plan_id)},
        headers=captain["headers"],
    )
    assert opened.status_code == 201, opened.text
    cib_id = opened.json()["request"]["reference"]
    sofizpay.check[cib_id] |= {"orderStatus": 2, "respCode": "00"}
    await client.post("/payment-requests/webhook/sofizpay", json=_notice(cib_id, "1500"))
    refreshed = await client.post(f"/payment-requests/{opened.json()['request']['id']}/refresh", headers=captain["headers"])
    assert refreshed.json()["status"] == "approved"
    from app.models.payment_request import PaymentRequest

    async with session_factory() as session:
        row = await session.get(PaymentRequest, uuid.UUID(opened.json()["request"]["id"]))
        assert row.subscription_id is not None and row.outcome_note is None
    assert (await _state(session_factory, captain))[0] == Decimal("300.000")


async def test_the_algerian_debt_screen_pays_through_the_payment_page_and_never_cliq(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**كليكُ أردنيّ** — في الجزائر تقول الحالُ `topup` (صفحةُ الدفع: SofizPay ثمّ BaridiMob)، وبابُ كليك يرفض."""
    await algeria_market(session_factory)
    install_transport(monkeypatch)
    await add_gateway_method(session_factory, "sofizpay")
    captain = await _captain_in_debt(client, session_factory, "700", blocked=True)
    state = (await client.get("/drivers/me/debt", headers=captain["headers"])).json()
    assert state["pay_via"] == "topup" and state["blocked"] is True and state["ceiling"] == "650"
    refused = await client.post("/drivers/me/debt/cliq", json={"amount": "700"}, headers=captain["headers"])
    assert refused.status_code == 422, refused.text
    methods = (await client.get("/payment-requests/methods", headers=captain["headers"])).json()["methods"]
    assert "sofizpay" in [m["code"] for m in methods]


async def test_two_payments_confirmed_at_once_collect_the_debt_once_without_deadlock(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**دفعتان لكبتنٍ واحدٍ تُؤكَّدان معاً** — صفُّه يُقفل قبل المحفظة في كلتيهما، فالتحصيلُ مرّةً لكلِّ صفّ: لا رصيدَ سالب، ولا صفَّ
    يُحصَّل مرّتين، ولا تعليق (`wait_for` — القفلُ المتبادلُ يعلق ولا يرمي).

    **وحدُّه مكتوب** (قِيس ٢٠٢٦-١٠-٢٩): حذفُ قفل صفِّ الكبتن في `approve` **يُبقيه أخضر** — ما يملك الثابتَ هنا قفلُ صفوف الدَّين
    (`outstanding_rows(for_update=True)`) وقفلُ المحفظة. **وقفلُ الكبتن لترتيب الأقفال** مع تسوية رحلةٍ تأخذه قبل المحفظة — ولم يُقَس."""
    import asyncio

    await algeria_market(session_factory)
    _, sofizpay = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    captain = await _captain_in_debt(client, session_factory, "400", "300", blocked=True)
    _, first = await _pay(client, captain, method_id, "400", sofizpay)
    _, second = await _pay(client, captain, method_id, "500", sofizpay)
    for cib_id in (first, second):
        sofizpay.check[cib_id] |= {"orderStatus": 2, "respCode": "00"}
    before = await _collections(session_factory)
    answers = await asyncio.wait_for(asyncio.gather(
        client.post("/payment-requests/webhook/sofizpay", json=_notice(first, "400")),
        client.post("/payment-requests/webhook/sofizpay", json=_notice(second, "500")),
    ), timeout=30)
    assert [a.status_code for a in answers] == [200, 200]
    left, blocked, statuses = await _state(session_factory, captain)
    assert left == 0 and blocked is False and statuses == ["settled", "settled"]
    # ٩٠٠ دخلت، ٧٠٠ دَين ⇒ ٢٠٠ في المحفظة
    assert await balance(client, captain["headers"]) == "200"
    async with session_factory() as session:
        negative = await session.scalar(
            select(func.count()).select_from(WalletTransaction).where(WalletTransaction.balance_after < 0)
        )
    assert negative == 0
    assert await _collections(session_factory) - before in (2, 3)
