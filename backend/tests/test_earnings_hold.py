"""«قيد التحويل» (SPEC §٧٤-ط/٦، §٧٤-ي) — **الوضعان مقيسان**: «فوري» كما كان حرفاً، و«بعد مدّة» يُري الأجرةَ ولا يُسحبها حتى تكمل.

**والبابان بقاعدةٍ واحدة**: بطاقةُ محفظة الكبتن (`earnings_hold.in_transit`) والملخّصُ الماليُّ في SQL (`finance_summary._transit`) —
**ويُقارَن الملخّصُ بقرينه الخام** في المطابقة (`assert_reconciled`).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit import AdminAuditLog
from app.services import earnings_hold
from tests.helpers import (
    DRIVER,
    approved_driver,
    bring_online,
    completed_ride,
    pay_ride,
    rider_session,
    set_commission,
    topup_wallet,
)
from tests.test_driver_debt import _cash_ride_settled
from tests.test_finance_summary import amount, assert_reconciled, finance_reader, summary

pytestmark = pytest.mark.asyncio

#: أجرةُ الرحلة ٨٫٠٠٠ وعمولتُها ١٠٪ ⇒ ما يدخل محفظةَ الكبتن صافياً
NET = Decimal("7.200")


async def _set_hold(client: AsyncClient, admin_headers: dict, days: int, country: str = "JO"):
    return await client.patch(f"/admin/settings/wallet/{country}", json={"earnings_hold_days": days}, headers=admin_headers)


async def _wallet_ride(client: AsyncClient, admin_headers: dict, session_factory) -> dict:
    """رحلةٌ يدفعها الراكبُ من محفظته — **فأجرتُها تمرّ بالمنصّة إلى محفظة الكبتن** (`payments._distribute`)."""
    await set_commission(session_factory, "10")
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "20.000")
    ride = await completed_ride(client, rider["headers"], driver)
    paid = await pay_ride(client, rider["headers"], ride["id"], "wallet")
    assert paid.status_code == 201, paid.text
    return driver


async def _captain_wallet(client: AsyncClient, driver: dict) -> dict:
    response = await client.get("/wallet/me/driver", headers=driver["headers"])
    assert response.status_code == 200, response.text
    return response.json()


def _advance_clock(monkeypatch: pytest.MonkeyPatch, by: timedelta) -> None:
    """**يمرّ الزمن** — والدفترُ لا يُعدَّل (`wallet_transactions` لا يقبل `UPDATE` حتى هنا)، فتُقدَّم ساعةُ الحساب لا تاريخُ القيد."""
    later = datetime.now(UTC) + by
    monkeypatch.setattr(earnings_hold, "_now", lambda: later)


async def test_instant_is_exactly_what_it_was(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings: None, jordan_wallet: None
) -> None:
    driver = await _wallet_ride(client, admin_headers, session_factory)
    wallet = await _captain_wallet(client, driver)
    assert wallet["earnings_hold_days"] == 0
    assert wallet["in_transit"] == "0.000" and wallet["in_transit_releases"] == []
    assert Decimal(wallet["balance"]) == NET


async def test_after_days_the_fare_is_seen_at_once_and_withdrawn_when_due(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings: None, jordan_wallet: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert (await _set_hold(client, admin_headers, 3)).status_code == 200
    before = datetime.now(UTC)
    driver = await _wallet_ride(client, admin_headers, session_factory)

    wallet = await _captain_wallet(client, driver)
    # **في رصيده فوراً**، و«قيد التحويل» كلُّه، **ولا يُسحب منه شيء**
    assert Decimal(wallet["balance"]) == NET
    assert Decimal(wallet["in_transit"]) == NET
    assert Decimal(wallet["available_for_withdrawal"]) == Decimal("0")
    assert wallet["earnings_hold_days"] == 3
    [release] = wallet["in_transit_releases"]
    assert Decimal(release["amount"]) == NET
    when = datetime.fromisoformat(release["available_at"])
    assert before + timedelta(days=3) <= when <= before + timedelta(days=3, hours=1, minutes=5)

    refused = await client.post(
        "/wallet/me/withdrawals", json={"amount": "5.000", "method": "bank"}, headers=driver["headers"]
    )
    assert refused.status_code in (400, 409, 422), refused.text

    # **تكمل المدّة** ⇒ يصير متاحاً كما في «فوري» حرفاً
    _advance_clock(monkeypatch, timedelta(days=3, hours=1, minutes=5))
    released = await _captain_wallet(client, driver)
    assert released["in_transit"] == "0.000" and released["in_transit_releases"] == []
    monkeypatch.undo()
    assert (await _set_hold(client, admin_headers, 0)).status_code == 200
    instant = await _captain_wallet(client, driver)
    assert released["available_for_withdrawal"] == instant["available_for_withdrawal"]
    assert Decimal(instant["available_for_withdrawal"]) > 0


async def test_a_cash_ride_is_never_in_transit(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings: None, jordan_wallet: None
) -> None:
    assert (await _set_hold(client, admin_headers, 3)).status_code == 200
    driver, _payment = await _cash_ride_settled(client, session_factory)
    wallet = await _captain_wallet(client, driver)
    assert wallet["in_transit"] == "0.000" and wallet["in_transit_releases"] == []


async def test_the_finance_summary_shows_in_transit_and_reconciles(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings: None, jordan_wallet: None
) -> None:
    reader = await finance_reader(client, admin_headers)
    assert (await _set_hold(client, admin_headers, 3)).status_code == 200
    driver = await _wallet_ride(client, admin_headers, session_factory)

    body = await summary(client, reader)
    assert amount(body, "captain_balances") == NET
    assert amount(body, "captain_in_transit") == NET
    assert amount(body, "captain_payable_now") == Decimal("0.000")
    assert amount(body, "captain_not_due") == NET
    assert_reconciled(body)
    # **والبابان يقولان رقماً واحداً**
    assert Decimal((await _captain_wallet(client, driver))["in_transit"]) == amount(body, "captain_in_transit")

    # **والمدّةُ تُقرأ الآن** (§٧٤-ي/٣): «فوري» يُطلقه كلَّه في اللحظة، والصفحةُ تطابق
    assert (await _set_hold(client, admin_headers, 0)).status_code == 200
    body = await summary(client, reader)
    assert amount(body, "captain_in_transit") == Decimal("0.000")
    assert amount(body, "captain_payable_now") == NET
    assert_reconciled(body)


async def test_the_setting_is_bounded_and_every_change_is_audited(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_wallet: None
) -> None:
    assert (await _set_hold(client, admin_headers, 31)).status_code == 422
    assert (await _set_hold(client, admin_headers, -1)).status_code == 422
    changed = await _set_hold(client, admin_headers, 3)
    assert changed.status_code == 200 and changed.json()["earnings_hold_days"] == 3
    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(AdminAuditLog).where(AdminAuditLog.entity_type == "wallet_setting").order_by(AdminAuditLog.created_at)
            )
        ).all()
    assert rows[-1].details["changes"]["earnings_hold_days"] == {"before": 0, "after": 3}

    choices = await client.patch(
        "/admin/settings/wallet/JO", json={"topup_choices": ["5", "1", "5"]}, headers=admin_headers
    )
    assert choices.status_code == 200, choices.text
    assert choices.json()["topup_choices"] == ["1.000", "5.000"]
    zero = await client.patch("/admin/settings/wallet/JO", json={"topup_choices": ["0"]}, headers=admin_headers)
    assert zero.status_code == 422 and zero.json()["field"] == "topup_choices"
