"""الحجزُ المضمون (SPEC §٦٣-ج/٣، قرارُ المالك ٢٠٢٦-١٠-٠٧) — **مطفأٌ لكلِّ سوقٍ حتى يُشعله المالك**.

ما يحرسه هذا الملف:

- **مطفأً يُرفض**، **والرسمُ يُحفظ من المحفظة لحظةَ الحجز** ويُرفض الحجزُ إن لم يكفِ الرصيد.
- **كبتنٌ واحدٌ يقبله** (اثنان معاً ⇒ واحد)، **و«نعم» قبل نافذتها تُرفض**، **وبعدها تُنشأ الرحلةُ مسنَدةً إليه**.
- **تمامُ الرحلة معه في وقته ⇒ الرسمُ له كاملاً بلا عمولة**؛ **وتأخّرُه ⇒ يُردّ، وللراكب إلغاءٌ مجّانيّ**.
- **اعتذارُه قبل التأكيد بلا أثر؛ وبعده غرامةٌ بقدر رصيده وإنذار، واعتذاران يحجبانه.**
- **لا كبتنَ عند التنفيذ ⇒ يُردّ الرسم**؛ **وإلغاءُ الراكب ⇒ يُردّ** (لم يُقل غيرُه).
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.booking import RideBooking
from app.models.driver import Driver
from app.models.driver_warning import DriverWarning
from app.models.enums import FeatureKey, WalletTransactionType
from app.models.wallet import WalletTransaction
from app.services import guarantees
from tests.helpers import (
    DRIVER,
    DROPOFF,
    PICKUP,
    SECOND_DRIVER,
    approved_driver,
    bring_online,
    enable_features,
    rider_session,
    topup_wallet,
    wallet_of,
)

FLAG = FeatureKey.GUARANTEED_BOOKING_ENABLED.value
BOOKINGS = FeatureKey.SCHEDULED_RIDES_ENABLED.value
WALLET = FeatureKey.WALLET_ENABLED.value
FEE = Decimal("1.000")


@pytest.fixture(autouse=True)
async def _service_settings(_clean_state, session_factory) -> None:
    """**صفُّ الإعدادات كما تبذره الترحيلة `0092`** — والاختباراتُ تفرّغ الجداولَ قبل كلٍّ منها."""
    from app.models.service_setting import ServiceSetting

    async with session_factory() as session:
        session.add_all(
            [ServiceSetting(country_code="JO", guarantee_fee=FEE), ServiceSetting(country_code="LY")]
        )
        await session.commit()


async def _ledger(session_factory, tx_type: WalletTransactionType) -> Decimal:
    async with session_factory() as session:
        return await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(WalletTransaction.type == tx_type)
        )


async def _setup(client, admin_headers, session_factory, *, balance: str = "20.000"):
    await enable_features(session_factory, FLAG, BOOKINGS)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    if balance != "0":
        await topup_wallet(client, admin_headers, rider["user"]["id"], balance)
    return rider, driver


async def _book(client, rider, *, hours: float = 3, guaranteed: bool = True):
    at = (datetime.now(UTC) + timedelta(hours=hours)).isoformat()
    return await client.post(
        "/me/bookings",
        json={
            "pickup": PICKUP,
            "dropoff": DROPOFF,
            "vehicle_category": "economy",
            "scheduled_at": at,
            "guaranteed": guaranteed,
        },
        headers=rider["headers"],
    )


async def _move_to(session_factory, booking_id: str, *, minutes_from_now: float) -> None:
    """**يقرّب الموعدَ بدل انتظاره** — الساعةُ في القاعدة لا في الاختبار."""
    async with session_factory() as session:
        row = await session.get(RideBooking, uuid.UUID(booking_id))
        row.scheduled_at = datetime.now(UTC) + timedelta(minutes=minutes_from_now)
        await session.commit()


async def test_switched_off_a_guaranteed_booking_is_refused(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    await enable_features(session_factory, BOOKINGS)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "20.000")
    refused = await _book(client, rider)
    assert refused.status_code == 403 and refused.json()["code"] == "guaranteed_booking_unavailable"


async def test_the_fee_is_held_from_the_wallet_and_an_empty_wallet_is_refused(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    rider, _ = await _setup(client, admin_headers, session_factory, balance="0")
    empty = await _book(client, rider)
    assert empty.status_code == 409 and empty.json()["code"] == "insufficient_balance"

    await topup_wallet(client, admin_headers, rider["user"]["id"], "5.000")
    booked = await _book(client, rider)
    assert booked.status_code == 201, booked.text
    assert booked.json()["guaranteed"] is True and booked.json()["guarantee_fee"] == "1.000"
    assert (await wallet_of(client, rider["headers"]))["balance"] == "4.000"
    too_soon = await _book(client, rider, hours=1)
    assert too_soon.status_code == 409


async def test_two_captains_accept_at_once_and_one_wins(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory, monkeypatch
) -> None:
    """**القفلُ وحدَه يملك هذا** — وتداخلٌ مقصود: الأولُ يتمهّل بعد قراءة الحجز فيبدأ الثاني والأولُ ممسكٌ به. **وبحذف القفل يقبلانه معاً**
    (قِيس: كان يمرّ بلا القفل قبل التمهّل — الطلبان لم يتداخلا أصلاً، فلم يكن يقيس شيئاً)."""
    original = guarantees._locked

    async def slow_locked(session, booking_id):
        row = await original(session, booking_id)
        await asyncio.sleep(0.5)
        return row

    monkeypatch.setattr(guarantees, "_locked", slow_locked)
    rider, first = await _setup(client, admin_headers, session_factory)
    second = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-22")
    booking = (await _book(client, rider)).json()

    offers = await client.get("/drivers/me/guarantee-offers", headers=first["headers"])
    assert [row["id"] for row in offers.json()] == [booking["id"]]

    responses = await asyncio.wait_for(
        asyncio.gather(
            client.post(f"/drivers/me/guarantees/{booking['id']}/accept", headers=first["headers"]),
            client.post(f"/drivers/me/guarantees/{booking['id']}/accept", headers=second["headers"]),
        ),
        timeout=20,
    )
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    loser = next(r for r in responses if r.status_code == 409)
    assert loser.json()["code"] == "guarantee_taken"


async def test_confirming_creates_the_ride_and_a_timely_ride_pays_the_captain_the_whole_fee(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    rider, driver = await _setup(client, admin_headers, session_factory)
    booking = (await _book(client, rider)).json()
    assert (await client.post(f"/drivers/me/guarantees/{booking['id']}/accept", headers=driver["headers"])).status_code == 200

    early = await client.post(f"/drivers/me/guarantees/{booking['id']}/confirm", headers=driver["headers"])
    assert early.status_code == 409

    await _move_to(session_factory, booking["id"], minutes_from_now=50)
    confirmed = await client.post(f"/drivers/me/guarantees/{booking['id']}/confirm", headers=driver["headers"])
    assert confirmed.status_code == 200, confirmed.text
    ride = confirmed.json()
    assert ride["status"] == "accepted" and ride["driver"]["id"] == str(driver["driver_id"])

    for step in ("arrive", "start", "complete"):
        assert (await client.post(f"/rides/{ride['id']}/{step}", headers=driver["headers"])).status_code == 200
    assert await _ledger(session_factory, WalletTransactionType.GUARANTEE_FEE) == FEE
    assert await _ledger(session_factory, WalletTransactionType.GUARANTEE_REFUND) == 0


async def test_a_late_captain_loses_the_fee_and_the_rider_cancels_free(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    rider, driver = await _setup(client, admin_headers, session_factory)
    booking = (await _book(client, rider)).json()
    await client.post(f"/drivers/me/guarantees/{booking['id']}/accept", headers=driver["headers"])
    await _move_to(session_factory, booking["id"], minutes_from_now=50)
    ride = (await client.post(f"/drivers/me/guarantees/{booking['id']}/confirm", headers=driver["headers"])).json()

    # الموعدُ مضى منذ ربع ساعة ولم يصل
    await _move_to(session_factory, booking["id"], minutes_from_now=-15)
    cancelled = await client.post(f"/rides/{ride['id']}/cancel", json={"reason": "تأخّر"}, headers=rider["headers"])
    assert cancelled.status_code == 200, cancelled.text
    assert Decimal(cancelled.json()["cancellation_fee"] or "0") == 0
    assert await _ledger(session_factory, WalletTransactionType.GUARANTEE_REFUND) == FEE
    assert await _ledger(session_factory, WalletTransactionType.GUARANTEE_FEE) == 0


async def test_withdrawing_before_confirming_costs_nothing_and_after_costs_the_fee_and_a_warning(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    rider, driver = await _setup(client, admin_headers, session_factory)
    booking = (await _book(client, rider)).json()
    await client.post(f"/drivers/me/guarantees/{booking['id']}/accept", headers=driver["headers"])
    free = await client.post(f"/drivers/me/guarantees/{booking['id']}/withdraw", headers=driver["headers"])
    assert free.status_code == 200, free.text
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(DriverWarning)) == 0

    # **بعد التأكيد**: الكبتنُ يلغي الرحلةَ المسنَدة — ورصيدُه ٠٫٤٠٠ فلا ينتقل إلا هو، والباقي يُسجَّل
    await _credit_driver(session_factory, driver, "0.400")
    await client.post(f"/drivers/me/guarantees/{booking['id']}/accept", headers=driver["headers"])
    await _move_to(session_factory, booking["id"], minutes_from_now=50)
    ride = (await client.post(f"/drivers/me/guarantees/{booking['id']}/confirm", headers=driver["headers"])).json()
    gone = await client.post(f"/rides/{ride['id']}/cancel", json={"reason": "طرأ أمر"}, headers=driver["headers"])
    assert gone.status_code == 200, gone.text

    async with session_factory() as session:
        warning = await session.scalar(select(DriverWarning))
        assert warning.penalty_amount == Decimal("0.400") and warning.penalty_shortfall == Decimal("0.600")
        row = await session.get(RideBooking, uuid.UUID(booking["id"]))
        assert row.status.value == "pending" and row.driver_id is None and row.guarantee_state == "held"
    assert await _ledger(session_factory, WalletTransactionType.GUARANTEE_COMPENSATION) == Decimal("0.400")

    # **ويُنقَص تقييمُه من المرّة الأولى** (§٦٤-د): بلا تقييمٍ سابقٍ صار متوسّطُه نجمةَ الاعتذار وحدَها
    async with session_factory() as session:
        assert (await session.get(Driver, driver["driver_id"])).rating_avg == Decimal("1.00")


async def test_the_cancel_sheet_states_the_penalty_before_the_captain_confirms(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**الشكلُ الثالثَ عشر**: غرامةُ الاعتذار مالٌ يخرج من جيب الكبتن — **فتُقال في ورقة الإلغاء قبل أن يؤكّد**، ولا تُقال حيث لا
    غرامة، **ورحلةُ غيره ٤٠٤**."""
    rider, driver = await _setup(client, admin_headers, session_factory)
    booking = (await _book(client, rider)).json()
    await client.post(f"/drivers/me/guarantees/{booking['id']}/accept", headers=driver["headers"])
    await _move_to(session_factory, booking["id"], minutes_from_now=50)
    ride = (await client.post(f"/drivers/me/guarantees/{booking['id']}/confirm", headers=driver["headers"])).json()

    cost = await client.get(f"/drivers/me/rides/{ride['id']}/guarantee-cost", headers=driver["headers"])
    assert cost.status_code == 200, cost.text
    assert cost.json() == {"cancel_penalty": "1.000", "currency": "JOD", "ban_threshold": 2, "ban_days": 30}

    other = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-22")
    stranger = await client.get(f"/drivers/me/rides/{ride['id']}/guarantee-cost", headers=other["headers"])
    assert stranger.status_code == 404, stranger.text

    # **بعد الإلغاء لا غرامةَ تُقال** — الحجزُ عاد مفتوحاً ولم يعد على الرحلة
    await client.post(f"/rides/{ride['id']}/cancel", json={"reason": "طرأ أمر"}, headers=driver["headers"])
    after = await client.get(f"/drivers/me/rides/{ride['id']}/guarantee-cost", headers=driver["headers"])
    assert after.status_code == 200 and after.json()["cancel_penalty"] is None, after.text


async def _credit_driver(session_factory, driver: dict, amount: str) -> None:
    """رصيدٌ في محفظة الكبتن بقيد تصحيحٍ إداريّ — **شحنُ محفظة الكبتن أُلغي** (قرارُ المالك)، والتصحيحُ بابُها الوحيد."""
    from app.models.enums import WalletOwnerType
    from app.models.user import User
    from app.services import wallet

    async with session_factory() as session:
        user = await session.get(User, await _user_of(session_factory, driver))
        await wallet.lock_wallet(session, user.id)
        await wallet.record(
            session,
            owner=user,
            owner_type=WalletOwnerType.DRIVER,
            tx_type=WalletTransactionType.ADJUSTMENT,
            amount=Decimal(amount),
            created_by=None,
            idempotency_key=f"test-credit:{user.id}",
        )
        await session.commit()


async def _user_of(session_factory, driver: dict) -> uuid.UUID:
    async with session_factory() as session:
        return (await session.get(Driver, driver["driver_id"])).user_id


async def test_two_withdrawals_after_confirming_ban_the_captain_for_a_month(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    rider, driver = await _setup(client, admin_headers, session_factory, balance="40.000")
    for _ in range(2):
        booking = (await _book(client, rider)).json()
        await client.post(f"/drivers/me/guarantees/{booking['id']}/accept", headers=driver["headers"])
        await _move_to(session_factory, booking["id"], minutes_from_now=50)
        ride = (await client.post(f"/drivers/me/guarantees/{booking['id']}/confirm", headers=driver["headers"])).json()
        await client.post(f"/rides/{ride['id']}/cancel", json={"reason": "طرأ أمر"}, headers=driver["headers"])
        # الحجزُ عاد مفتوحاً — يُلغيه الراكبُ فيُردّ رسمُه ويبقى ما بعده نظيفاً
        await client.delete(f"/me/bookings/{booking['id']}", headers=rider["headers"])

    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        assert row.guarantee_banned_until is not None
        assert row.guarantee_banned_until > datetime.now(UTC) + timedelta(days=29)
    booking = (await _book(client, rider)).json()
    banned = await client.post(f"/drivers/me/guarantees/{booking['id']}/accept", headers=driver["headers"])
    assert banned.status_code == 403 and banned.json()["code"] == "guarantee_banned"
    assert (await client.get("/drivers/me/guarantee-offers", headers=driver["headers"])).json() == []


async def test_no_captain_at_execution_refunds_and_a_rider_cancellation_refunds(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    from app.core.redis_client import get_redis_client
    from app.services import bookings

    rider, _ = await _setup(client, admin_headers, session_factory)
    first = (await _book(client, rider)).json()
    await _move_to(session_factory, first["id"], minutes_from_now=5)
    async with session_factory() as session:
        await bookings.run_due(session, get_redis_client())
    assert await _ledger(session_factory, WalletTransactionType.GUARANTEE_REFUND) == FEE

    second = (await _book(client, rider)).json()
    assert (await client.delete(f"/me/bookings/{second['id']}", headers=rider["headers"])).status_code == 200
    assert await _ledger(session_factory, WalletTransactionType.GUARANTEE_REFUND) == FEE * 2
    # والدفترُ متوازن: حُفظ رسمان ورُدّا
    assert await _ledger(session_factory, WalletTransactionType.GUARANTEE_HOLD) == -FEE * 2


async def test_an_unanswered_confirmation_drops_the_captain_without_penalty(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    from app.core.redis_client import get_redis_client

    rider, driver = await _setup(client, admin_headers, session_factory)
    booking = (await _book(client, rider)).json()
    await client.post(f"/drivers/me/guarantees/{booking['id']}/accept", headers=driver["headers"])
    await _move_to(session_factory, booking["id"], minutes_from_now=55)
    async with session_factory() as session:
        result = await guarantees.sweep(session, get_redis_client())
        assert result["asked"] == 1
    async with session_factory() as session:
        row = await session.get(RideBooking, uuid.UUID(booking["id"]))
        row.confirm_requested_at = datetime.now(UTC) - timedelta(minutes=11)
        await session.commit()
    async with session_factory() as session:
        result = await guarantees.sweep(session, get_redis_client())
        assert result["dropped"] == 1
    async with session_factory() as session:
        row = await session.get(RideBooking, uuid.UUID(booking["id"]))
        assert row.driver_id is None and row.guarantee_state == "held"
        assert await session.scalar(select(func.count()).select_from(DriverWarning)) == 0


async def test_the_owner_sets_the_guarantee_amounts_from_the_panel(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**كلُّ مبلغٍ يُضبط من اللوحة** — والسوقُ بلا رسمٍ يُعرض صفراً لا يختفي."""
    listed = await client.get("/admin/settings/services", headers=admin_headers)
    assert listed.status_code == 200, listed.text
    rows = {row["country_code"]: row for row in listed.json()}
    assert rows["JO"]["guarantee_fee"] == "1.000" and rows["LY"]["guarantee_fee"] == "0.000"
    patched = await client.patch(
        "/admin/settings/services/JO", json={"guarantee_fee": "1.500", "guarantee_ban_days": 15}, headers=admin_headers
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["guarantee_fee"] == "1.500" and patched.json()["guarantee_ban_days"] == 15
    bad = await client.patch("/admin/settings/services/JO", json={"guarantee_fee": "-1"}, headers=admin_headers)
    assert bad.status_code == 422
