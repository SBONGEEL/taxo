"""رحلةٌ لشخصٍ آخر (SPEC §٦٣-ج/١، قرارُ المالك ٢٠٢٦-١٠-٠٧) — **مطفأةٌ لكلِّ سوقٍ حتى يُشعلها المالك**.

ما يحرسه هذا الملف، كلٌّ بقرارٍ مكتوب:

- **مطفأةً تُرفض** ولا يُترك صفّ — والإشعالُ لكلِّ سوق.
- **الكبتنُ يرى الراكبَ الفعليَّ بعد القبول وحدَه**، ويُطوى اسمُه ورقمُه بعد الانتهاء — العرضُ يمرّ على كباتن يرفضونه.
- **من يدفع يحكم القناة**: الراكبُ نقداً ⇒ **دفعةُ نقدٍ يفتحها الإنهاء** ويؤكّدها الكبتن؛ والطالبُ ⇒ محفظةٌ أو بطاقةٌ **بلا باقٍ نقديّ**.
- **رسمُ الإلغاء على الطالب** ولو كان الراكبُ يدفع نقداً.
- **رابطُ التتبّع للطالب وحدَه، والرمزُ نفسُه في كلِّ ضغطة** (ومعاً)، **ويتوقّف بانتهاء الرحلة**، ولا يحمل رقماً.
- **الاسمُ والرقمُ يُمحيان بعد ٣٠ يوماً** من الانتهاء، والرحلةُ تبقى «لغير صاحبها».
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.cancellation import RideCancellationCharge
from app.models.enums import FeatureKey
from app.models.payment import Payment
from app.models.ride import Ride
from app.models.ride_track import RideTrackToken
from app.services import ride_for_other
from tests.helpers import (
    DRIVER,
    DROPOFF,
    OTHER_RIDER,
    PICKUP,
    RIDER,
    approved_driver,
    auth,
    bring_online,
    broadcast_location,
    enable_features,
    payments_of,
    pay_ride,
    register,
    rider_session,
    topup_wallet,
    wait_for_offer,
)

FLAG = FeatureKey.RIDE_FOR_OTHER_ENABLED.value
PASSENGER = {"name": "أم محمد", "phone": "0791112222"}
FAR_AWAY = {"lat": 32.0060, "lng": 35.9106}


def _body(payer: str = "passenger_cash", **passenger) -> dict:
    return {
        "pickup": PICKUP,
        "dropoff": DROPOFF,
        "vehicle_category": "economy",
        "for_other": PASSENGER | passenger | {"payer": payer},
    }


async def _captain(client: AsyncClient, session_factory) -> dict:
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    return driver


async def _accepted(client: AsyncClient, rider: dict, driver: dict, payer: str = "passenger_cash") -> dict:
    """**كمساعد `accepted_ride`** بإعادة المحاولة عند انقضاء العرض تحت الحمل — وبحمولةِ رحلةٍ لغيره."""
    response = await client.post("/rides", json=_body(payer), headers=rider)
    assert response.status_code == 201, response.text
    ride = response.json()
    for attempt in range(3):
        await wait_for_offer(ride["id"], driver["driver_id"])
        accepted = await client.post(f"/rides/{ride['id']}/accept", headers=driver["headers"])
        if accepted.status_code == 200:
            return accepted.json()
        if accepted.json().get("code") != "ride_offer_expired" or attempt == 2:
            break
    assert accepted.status_code == 200, accepted.text
    return accepted.json()


async def _complete(client: AsyncClient, ride_id: str, driver: dict) -> dict:
    for step in ("arrive", "start", "complete"):
        response = await client.post(f"/rides/{ride_id}/{step}", headers=driver["headers"])
        assert response.status_code == 200, response.text
    return response.json()


async def test_switched_off_a_ride_for_another_is_refused_and_leaves_no_row(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**مطفأةٌ بالافتراض** — ورفضٌ قبل أن يُضاف صفّ: لا رحلةَ تُطلب لغيره ولا رحلةَ له تُنشأ بدلها."""
    await _captain(client, session_factory)
    rider = (await rider_session(client))["headers"]
    refused = await client.post("/rides", json=_body(), headers=rider)
    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "ride_for_other_unavailable"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Ride)) == 0


async def test_the_captain_sees_the_passenger_only_between_acceptance_and_the_end(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**قبل القبول لا اسمَ ولا رقم** (العرضُ يمرّ على من يرفض) — **وبعده الاسمُ والرقمُ مطبَّعاً**، ثمّ يُطويان بالانتهاء.
    و`for_other` و`payer` منشوران في كلِّ طور: من قَبِل يعرف أنه يقبض من غير صاحب الطلب."""
    driver = await _captain(client, session_factory)
    await enable_features(session_factory, FLAG)
    rider = (await rider_session(client))["headers"]

    created = await client.post("/rides", json=_body(), headers=rider)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["for_other"] is True and body["payer"] == "passenger_cash"
    assert body["passenger_name"] is None and body["passenger_phone"] is None
    await client.post(f"/rides/{body['id']}/cancel", json={"reason": "تجربة"}, headers=rider)

    ride = await _accepted(client, rider, driver)
    assert ride["passenger_name"] == "أم محمد"
    assert ride["passenger_phone"] == "+962791112222"
    assert ride["payer"] == "passenger_cash"

    done = await _complete(client, ride["id"], driver)
    assert done["for_other"] is True
    assert done["passenger_name"] is None and done["passenger_phone"] is None


async def test_the_passenger_pays_cash_through_a_payment_the_completion_opens(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**صاحبُ الدفعة لا يحمل التطبيق** — فالإنهاءُ يفتح دفعةَ النقد بالأجرة كلِّها، والكبتنُ يؤكّدها بمساره القائم.
    **والطالبُ لا يدفع عنه**: أيُّ قناةٍ منه تُرفض، فلا تُحصَّل الأجرةُ مرّتين."""
    driver = await _captain(client, session_factory)
    await enable_features(session_factory, FLAG)
    rider = (await rider_session(client))["headers"]
    ride = await _accepted(client, rider, driver)
    done = await _complete(client, ride["id"], driver)

    payments = (await payments_of(client, rider, ride["id"]))["payments"]
    assert [(p["method"], p["status"], p["amount"]) for p in payments] == [
        ("cash", "pending", done["final_fare"])
    ]
    assert (await pay_ride(client, rider, ride["id"], "wallet")).status_code == 409

    confirmed = await client.post(f"/payments/{payments[0]['id']}/confirm", headers=driver["headers"])
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"


async def test_the_requester_pays_by_wallet_or_card_and_never_leaves_cash_behind(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """**الطالبُ ليس عند السيارة**: لا نقدَ ولا كليك منه، **ورصيدٌ لا يغطّي الأجرةَ يُرفض** بدل أن يترك باقياً نقدياً لا يدفعه أحد."""
    driver = await _captain(client, session_factory)
    await enable_features(session_factory, FLAG)
    session = await rider_session(client)
    rider = session["headers"]
    ride = await _accepted(client, rider, driver, payer="requester")
    done = await _complete(client, ride["id"], driver)
    assert (await payments_of(client, rider, ride["id"]))["payments"] == []

    cash = await pay_ride(client, rider, ride["id"], "cash", key="pay-cash-1")
    assert cash.status_code == 409 and cash.json()["code"] == "payer_method_mismatch"

    await topup_wallet(client, admin_headers, session["user"]["id"], "1.000")
    short = await pay_ride(client, rider, ride["id"], "wallet", key="pay-wallet-1")
    assert short.status_code == 409 and short.json()["code"] == "insufficient_balance"
    assert (await payments_of(client, rider, ride["id"]))["payments"] == []

    await topup_wallet(client, admin_headers, session["user"]["id"], "50.000")
    paid = await pay_ride(client, rider, ride["id"], "wallet", key="pay-wallet-2")
    assert paid.status_code == 201, paid.text
    rows = (await payments_of(client, rider, ride["id"]))["payments"]
    assert [(p["method"], p["status"], p["amount"]) for p in rows] == [
        ("wallet", "confirmed", done["final_fare"])
    ]


async def test_the_cancellation_fee_falls_on_the_requester_even_when_the_passenger_pays_cash(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """**قرارُ المالك بلفظه** — والطالبُ صاحبُ الحساب الوحيد في الرحلة، فالرسمُ عليه بالبناء."""
    driver = await _captain(client, session_factory)
    await enable_features(session_factory, FLAG)
    session = await rider_session(client)
    await topup_wallet(client, admin_headers, session["user"]["id"], "20.000")
    ride = await _accepted(client, session["headers"], driver)
    await broadcast_location(client, driver, **FAR_AWAY)

    cancelled = await client.post(
        f"/rides/{ride['id']}/cancel", json={"reason": "غيّرت رأيي"}, headers=session["headers"]
    )
    assert cancelled.status_code == 200, cancelled.text
    async with session_factory() as db:
        charge = await db.scalar(
            select(RideCancellationCharge).where(RideCancellationCharge.ride_id == uuid.UUID(ride["id"]))
        )
    assert charge is not None and charge.amount > 0
    assert str(charge.payer_user_id) == session["user"]["id"]


async def test_own_number_is_not_another_person_and_a_bad_number_is_refused(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    rider = (await rider_session(client))["headers"]
    mine = await client.post("/rides", json=_body(phone=RIDER["phone"]), headers=rider)
    assert mine.status_code == 422 and mine.json()["code"] == "invalid_input"
    bad = await client.post("/rides", json=_body(phone="12345678"), headers=rider)
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_input"


async def test_the_track_link_is_the_requesters_shows_the_captain_and_stops_at_the_end(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**للطالب وحدَه** (٤٠٤ لغيره) · **الرمزُ نفسُه في كلِّ ضغطة** · **بلا دخولٍ يُرى الكبتنُ وسيارتُه ولوحتُه وموقعُه** — ولا
    رقمَ في الجواب — **ثمّ «انتهت» وحدَها**."""
    driver = await _captain(client, session_factory)
    await enable_features(session_factory, FLAG)
    rider = (await rider_session(client))["headers"]
    ride = await _accepted(client, rider, driver)

    other = auth(await register(client, OTHER_RIDER))
    assert (await client.post(f"/rides/{ride['id']}/track-link", headers=other)).status_code == 404

    first = await client.post(f"/rides/{ride['id']}/track-link", headers=rider)
    assert first.status_code == 200, first.text
    token = first.json()["token"]
    assert len(token) >= 20
    again = await client.post(f"/rides/{ride['id']}/track-link", headers=rider)
    assert again.json()["token"] == token

    await broadcast_location(client, driver, lat=31.9600, lng=35.9106)
    seen = await client.get(f"/public/track/{token}")
    assert seen.status_code == 200, seen.text
    view = seen.json()
    assert view["state"] == "coming"
    assert view["captain_name"] == DRIVER["name"]
    assert view["vehicle"]["plate_number"]
    # **Redis GEO يخزّن بدقّةِ ~٠٫٦ م** فيعود الموقعُ مقرَّباً — يُقارن بما دون المتر لا حرفاً
    assert abs(view["position"]["lat"] - 31.96) < 1e-5 and abs(view["position"]["lng"] - 35.9106) < 1e-5
    for secret in ("+962", "0791112222", RIDER["phone"], ride["id"]):
        assert secret not in seen.text

    assert (await client.get("/public/track/not-a-real-token")).status_code == 404

    await _complete(client, ride["id"], driver)
    ended = (await client.get(f"/public/track/{token}")).json()
    assert ended == {"state": "ended", "captain_name": None, "vehicle": None, "position": None}
    late = await client.post(f"/rides/{ride['id']}/track-link", headers=rider)
    assert late.status_code == 409 and late.json()["code"] == "track_link_unavailable"


async def test_two_presses_at_once_make_one_link(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**ضغطتان معاً ⇒ رمزٌ واحد** — القيدُ الفريدُ على الرحلة هو الحارس، والخاسرُ يقرأ رمزَ الفائز ولا يسقط."""
    driver = await _captain(client, session_factory)
    await enable_features(session_factory, FLAG)
    rider = (await rider_session(client))["headers"]
    ride = await _accepted(client, rider, driver)

    responses = await asyncio.wait_for(
        asyncio.gather(
            *(client.post(f"/rides/{ride['id']}/track-link", headers=rider) for _ in range(3))
        ),
        timeout=20,
    )
    assert Counter(r.status_code for r in responses) == Counter({200: 3})
    assert len({r.json()["token"] for r in responses}) == 1
    async with session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(RideTrackToken).where(
                RideTrackToken.ride_id == uuid.UUID(ride["id"])
            )
        )
    assert count == 1


async def test_two_completions_at_once_open_one_cash_payment(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**القفلُ على صفِّ الرحلة يملك هذا**: إنهاءان معاً ⇒ إنهاءٌ واحدٌ ودفعةُ نقدٍ واحدة — لا دفعتان بأجرتين."""
    driver = await _captain(client, session_factory)
    await enable_features(session_factory, FLAG)
    rider = (await rider_session(client))["headers"]
    ride = await _accepted(client, rider, driver)
    for step in ("arrive", "start"):
        assert (await client.post(f"/rides/{ride['id']}/{step}", headers=driver["headers"])).status_code == 200

    responses = await asyncio.wait_for(
        asyncio.gather(
            *(client.post(f"/rides/{ride['id']}/complete", headers=driver["headers"]) for _ in range(2))
        ),
        timeout=20,
    )
    assert sorted(r.status_code for r in responses) == [200, 409]
    async with session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(Payment).where(Payment.ride_id == uuid.UUID(ride["id"]))
        )
    assert count == 1


async def test_the_passenger_is_erased_thirty_days_after_the_ride_and_the_ride_remembers(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**ثلاثون يوماً من الانتهاء لا من الطلب** — يومٌ قبلها لا يُمحى شيء، وبعدها يُمحى الاسمُ والرقمُ ورابطُها،
    **ويبقى `for_other`** فالسجلُّ يقول ما كانت الرحلةُ لا من كان فيها."""
    driver = await _captain(client, session_factory)
    await enable_features(session_factory, FLAG)
    rider = (await rider_session(client))["headers"]
    ride = await _accepted(client, rider, driver)
    await client.post(f"/rides/{ride['id']}/track-link", headers=rider)
    await _complete(client, ride["id"], driver)

    async with session_factory() as session:
        row = await session.get(Ride, uuid.UUID(ride["id"]))
        ended = row.completed_at
    async with session_factory() as session:
        assert await ride_for_other.purge_passengers(session, now=ended + timedelta(days=29)) == 0
        await session.commit()
    async with session_factory() as session:
        assert await ride_for_other.purge_passengers(session, now=ended + timedelta(days=31)) == 1
        await session.commit()
    async with session_factory() as session:
        row = await session.get(Ride, uuid.UUID(ride["id"]))
        assert row.for_other is True
        assert row.passenger_name is None and row.passenger_phone is None
        assert row.passenger_erased_at is not None
        assert await session.scalar(select(func.count()).select_from(RideTrackToken)) == 0
        # ومرّةٌ ثانيةٌ لا تمسّ ما مُحي
        assert await ride_for_other.purge_passengers(session, now=ended + timedelta(days=60)) == 0
