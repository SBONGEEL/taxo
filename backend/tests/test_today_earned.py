"""**«صافي اليوم» = ما كسبه الكبتنُ فعلاً** (أمرُ المالك ٢٠٢٦-١١-٠٦) — `earned` في `/drivers/me/earnings`.

المحصَّلُ كلُّه (كاشٌ وكليكٌ بيده · بطاقةٌ ومحفظةٌ في محفظته · بقشيش) **ناقصاً العمولةَ الفعليّةَ وكلَّ اقتطاع**. رحلةُ كاشٍ بـ٢٫٠٠٠
وعمولتُها ٠٫٠٩٠ ⇐ ١٫٩١٠ لا −٠٫٠٩٠. **و`net` (صافي المحفظة) باقٍ كما هو** — يُقاس هنا أيضاً فلا يُعاد تعريفُه بصمت.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from httpx import AsyncClient

from app.models.debt import DriverDebt
from app.models.driver import Driver
from app.models.enums import (
    CountryCode,
    DriverDebtSource,
    PaymentConfirmedBy,
    PaymentMethod,
    PaymentStatus,
    RideStatus,
)
from app.models.payment import Payment
from app.models.ride import Ride
from tests.helpers import (
    DRIVER,
    approved_driver,
    bring_online,
    completed_ride,
    pay_ride,
    rider_session,
    topup_wallet,
)
from tests.test_payment_requests import ALGERIAN_DRIVER, ALGERIAN_RIDER

PERCENT = Decimal("4.5")


async def _earnings(client: AsyncClient, driver: dict) -> dict:
    response = await client.get("/drivers/me/earnings", headers=driver["headers"], params={"period": "today"})
    assert response.status_code == 200, response.text
    return response.json()


async def _commission_on(client: AsyncClient, admin_headers: dict) -> None:
    response = await client.patch(
        "/admin/settings/commission/JO",
        json={"commission_enabled": True, "commission_percent": str(PERCENT), "applies_to": "all_rides"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text


async def _cash_ride(client: AsyncClient, rider: dict, driver: dict) -> Decimal:
    ride = await completed_ride(client, rider["headers"], driver)
    paid = await pay_ride(client, rider["headers"], ride["id"], "cash", key=f"cash-{uuid.uuid4().hex[:8]}")
    assert paid.status_code == 201, paid.text
    confirmed = await client.post(f"/payments/{paid.json()['payments'][0]['id']}/confirm", headers=driver["headers"])
    assert confirmed.status_code == 200, confirmed.text
    return Decimal(ride["final_fare"] or ride["estimated_fare"])


async def _wallet_ride(client: AsyncClient, rider: dict, driver: dict, admin_headers: dict) -> Decimal:
    ride = await completed_ride(client, rider["headers"], driver)
    me = await client.get("/auth/me", headers=rider["headers"])
    await topup_wallet(client, admin_headers, me.json()["id"], "50.000")
    paid = await pay_ride(client, rider["headers"], ride["id"], "wallet", key=f"wal-{uuid.uuid4().hex[:8]}")
    assert paid.status_code == 201, paid.text
    return Decimal(ride["final_fare"] or ride["estimated_fare"])


def _commission(fare: Decimal) -> Decimal:
    return (fare * PERCENT / 100).quantize(Decimal("0.001"))


async def test_a_jordan_cash_ride_is_the_fare_less_its_commission(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    await _commission_on(client, admin_headers)
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    fare = await _cash_ride(client, rider, driver)

    body = await _earnings(client, driver)
    commission = _commission(fare)
    assert commission > 0
    # **ورصيدُه صفرٌ فالعمولةُ دَينٌ لا قيد** — المحفظةُ لم تتحرّك، **و«صافي اليوم» يطرحها مع ذلك**
    assert Decimal(body["commission"]) == 0 and Decimal(body["net"]) == 0
    assert Decimal(body["earned"]) == fare - commission  # ٢٫٠٠٠ − ٠٫٠٩٠ = ١٫٩١٠ لا −٠٫٠٩٠
    assert Decimal(body["directly_collected"]) == fare


async def test_a_cash_commission_collected_from_the_balance_is_not_counted_twice(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory, admin_headers: dict
) -> None:
    """**كبتنٌ في رصيده ما يغطّي** — دَينُ الكاش يُحصَّل من رصيده قيدَ عمولة: «صافي المحفظة» ينقص به، و«صافي اليوم» **يطرحه
    مرّةً واحدة** (الدَّينُ نشأ اليوم، وقيدُ تحصيله لا يُعدّ ثانيةً)."""
    await _commission_on(client, admin_headers)
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    wallet = await _wallet_ride(client, rider, driver, admin_headers)
    cash = await _cash_ride(client, rider, driver)

    body = await _earnings(client, driver)
    commission = _commission(cash) + _commission(wallet)
    assert Decimal(body["earned"]) == cash + wallet - commission


async def test_a_wallet_ride_is_the_fare_less_its_commission(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory, admin_headers: dict
) -> None:
    """**بلا كاش** (المحفظةُ والبطاقةُ بابُهما في الدفتر واحد: `ride_earning`) — المحصَّلُ في المحفظة لا في اليد."""
    await _commission_on(client, admin_headers)
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    fare = await _wallet_ride(client, rider, driver, admin_headers)

    body = await _earnings(client, driver)
    assert Decimal(body["directly_collected"]) == 0
    assert Decimal(body["earned"]) == Decimal(body["net"]) == fare - _commission(fare)


async def test_a_mixed_day_adds_every_channel_and_subtracts_every_commission(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory, admin_headers: dict
) -> None:
    await _commission_on(client, admin_headers)
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    cash = await _cash_ride(client, rider, driver)
    wallet = await _wallet_ride(client, rider, driver, admin_headers)

    body = await _earnings(client, driver)
    commission = _commission(cash) + _commission(wallet)
    assert Decimal(body["earned"]) == cash + wallet - commission
    assert body["completed_rides"] == 2


async def test_a_day_with_no_rides_is_zero(client: AsyncClient, jordan_settings: None, session_factory) -> None:
    driver = await approved_driver(client, session_factory, DRIVER)
    body = await _earnings(client, driver)
    assert body["earned"] == "0.000" and body["currency"] == "JOD"


async def test_a_free_first_week_driver_keeps_the_whole_fare(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """**«الأسبوعُ الأوّل مجّاناً بلا عمولة»** يُجمِّد صفراً على الكبتن (`commission_percent_from_subscription`) والسوقُ بعمولة —
    فالمحصَّلُ كلُّه له."""
    await _commission_on(client, admin_headers)
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    async with session_factory() as session:
        row = await session.get(Driver, uuid.UUID(str(driver["driver_id"])))
        row.commission_percent_from_subscription = Decimal("0")
        await session.commit()
    await bring_online(client, driver)
    fare = await _cash_ride(client, rider, driver)

    body = await _earnings(client, driver)
    assert Decimal(body["commission"]) == 0
    assert Decimal(body["earned"]) == fare


async def test_an_algeria_cash_ride_is_the_fare_less_its_commission(
    client: AsyncClient, session_factory
) -> None:
    """**رحلةُ كاشٍ في الجزائر بالدينار** — تُكتب صفوفُها مباشرةً (الاختبارُ عن الرقم المعروض لا عن مسار الدفع): ٢٩٠ د.ج وعمولةٌ ١٥ (دَينٌ كعمولة كلِّ كاش، والدينارُ بلا كسور)
    ⇐ **٢٧٥**، والعملةُ `DZD` فتُرسم بلا كسورٍ في التطبيق (`formatAmount` بخانات الدولة)."""
    rider = await rider_session(client, ALGERIAN_RIDER)
    driver = await approved_driver(client, session_factory, ALGERIAN_DRIVER, plate_number="ALG-2900")
    fare, commission = Decimal("290.000"), Decimal("15.000")
    async with session_factory() as session:
        driver_row = await session.get(Driver, uuid.UUID(str(driver["driver_id"])))
        ride = Ride(
            rider_id=uuid.UUID(str(rider["user"]["id"])),
            driver_id=driver_row.id,
            country_code=CountryCode.DZ,
            status=RideStatus.COMPLETED,
            completed_at=datetime.now(UTC),
            vehicle_category="economy",
            pickup_point="SRID=4326;POINT(3.05 36.75)",
            dropoff_point="SRID=4326;POINT(3.08 36.77)",
            distance_km=Decimal("2.988"),
            duration_min=8,
            estimated_fare=fare,
            final_fare=fare,
            currency="DZD",
            commission_percent_at_ride=Decimal("5"),
        )
        session.add(ride)
        await session.flush()
        session.add(
            Payment(
                ride_id=ride.id,
                method=PaymentMethod.CASH,
                amount=fare,
                currency="DZD",
                status=PaymentStatus.CONFIRMED,
                confirmed_by=PaymentConfirmedBy.DRIVER,
                confirmed_at=datetime.now(UTC),
            )
        )
        # **عمولةُ الكاش دَينٌ** كما يكتبها `debts.record_from_ride` على الإنتاج
        session.add(
            DriverDebt(
                driver_id=driver_row.id,
                country_code=CountryCode.DZ,
                source=DriverDebtSource.RIDE_COMMISSION,
                amount=commission,
                currency="DZD",
                ride_id=ride.id,
            )
        )
        await session.commit()

    body = await _earnings(client, driver)
    assert body["currency"] == "DZD"
    assert Decimal(body["earned"]) == fare - commission
    assert Decimal(body["net"]) == 0 and Decimal(body["directly_collected"]) == fare
