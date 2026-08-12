"""ملخّصُ أرباح الكبتن، وشارةُ النزاع، وتعديلُ المركبة
(`FUTURE-FEATURES` بنود 17 و19 و43).

**وأهمُّ ما يُختبر في الأرباح أن الكاش يظهر ولا يُجمَع**: القسم 9 يوجب إظهاره
موسوماً «مُحصَّل مباشرة» ولا يجعله رصيداً — فرقمان لا واحد، وخلطُهما يجعل
الكبتن يظن أن في محفظته ما ليس فيها.
"""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient

from app.models.enums import DriverStatus
from tests.helpers import (
    DRIVER,
    approved_driver,
    bring_online,
    completed_ride,
    pay_ride,
    rider_session,
)


async def _earnings(client: AsyncClient, driver: dict, period: str = "today") -> dict:
    response = await client.get(
        "/drivers/me/earnings", headers=driver["headers"], params={"period": period}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_cash_shows_as_collected_directly_and_never_as_balance(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """رحلةٌ نقدية: تظهر في «مُحصَّل مباشرة» وحدها — ولا `ride_earning` لها.

    وبجمع القناتين في رقمٍ واحد يسقط هذا الاختبار: المحفظةُ تصير غير صفر.
    """
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)

    paid = await pay_ride(client, rider["headers"], ride["id"], "cash")
    payment = paid.json()["payments"][0]
    confirmed = await client.post(
        f"/payments/{payment['id']}/confirm", headers=driver["headers"]
    )
    assert confirmed.status_code == 200, confirmed.text

    body = await _earnings(client, driver)
    fare = Decimal(ride["final_fare"] or ride["estimated_fare"])

    assert Decimal(body["directly_collected"]) == fare
    # **لم يمرّ بالمحفظة**: القسم 9 ينفي أثر الكاش على الرصيد
    assert Decimal(body["wallet_earnings"]) == Decimal("0.000")
    assert body["completed_rides"] == 1


async def test_wallet_ride_credits_earnings(
    client: AsyncClient,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
    admin_headers: dict,
) -> None:
    """رحلةٌ من المحفظة: تُقيَّد `ride_earning` — والمُحصَّل مباشرةً صفر."""
    from tests.helpers import topup_wallet

    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)

    me = await client.get("/auth/me", headers=rider["headers"])
    await topup_wallet(client, admin_headers, me.json()["id"], "50.000")

    paid = await pay_ride(client, rider["headers"], ride["id"], "wallet")
    assert paid.status_code == 201, paid.text

    body = await _earnings(client, driver)
    fare = Decimal(ride["final_fare"] or ride["estimated_fare"])
    assert Decimal(body["wallet_earnings"]) == fare
    assert Decimal(body["directly_collected"]) == Decimal("0.000")
    assert Decimal(body["net"]) == fare  # لا عمولة مفعّلة


async def test_earnings_are_empty_without_rides(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    driver = await approved_driver(client, session_factory, DRIVER)
    body = await _earnings(client, driver)

    assert Decimal(body["wallet_earnings"]) == Decimal("0.000")
    assert Decimal(body["commission"]) == Decimal("0.000")
    assert Decimal(body["net"]) == Decimal("0.000")
    assert body["completed_rides"] == 0
    assert body["currency"] == "JOD"


async def test_a_rider_has_no_earnings_door(
    client: AsyncClient, jordan_settings: None
) -> None:
    rider = await rider_session(client)
    response = await client.get("/drivers/me/earnings", headers=rider["headers"])
    assert response.status_code == 403


# ------------------------------------------------ شارةُ النزاع (بند 19)


async def test_the_ride_list_carries_its_payment_state(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """صفُّ الرحلة يحمل حالَ دفعها — وبها تُرسم شارةُ «نزاع» بلا نداءٍ ثانٍ."""
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)

    paid = await pay_ride(client, rider["headers"], ride["id"], "cash")
    payment = paid.json()["payments"][0]

    listed = await client.get("/rides/me", headers=driver["headers"])
    assert listed.status_code == 200, listed.text
    row = listed.json()[0]
    assert row["ride"]["id"] == ride["id"]
    assert row["payment_methods"] == ["cash"]
    assert row["has_open_dispute"] is False

    # ينازع الكبتنُ دفعةً... الكاش لا يُنازَع، فالاختبار يفصل نزاعاً إدارياً
    async with session_factory() as session:
        from app.models.enums import PaymentStatus
        from app.models.payment import Payment
        import uuid as _uuid

        row_payment = await session.get(Payment, _uuid.UUID(payment["id"]))
        row_payment.status = PaymentStatus.DISPUTED
        await session.commit()

    again = await client.get("/rides/me", headers=driver["headers"])
    assert again.json()[0]["has_open_dispute"] is True


# --------------------------------------------- تعديلُ المركبة (بند 43)


async def _vehicle_of(client: AsyncClient, driver: dict) -> dict:
    response = await client.get("/drivers/me/vehicles", headers=driver["headers"])
    assert response.status_code == 200, response.text
    return response.json()[0]


async def test_changing_the_colour_keeps_the_approval(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """اللونُ يصف المظهر لا الهوية — وإسقاطُ اعتمادٍ لتصحيح «أبيض» عقابٌ بلا ذنب."""
    driver = await approved_driver(client, session_factory, DRIVER)
    vehicle = await _vehicle_of(client, driver)

    response = await client.patch(
        f"/drivers/me/vehicles/{vehicle['id']}",
        json={"color": "أسود"},
        headers=driver["headers"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["vehicle"]["color"] == "أسود"
    assert response.json()["approval_reverted"] is False
    assert response.json()["driver_status"] == DriverStatus.APPROVED.value


async def test_changing_the_plate_sends_the_driver_back_to_review(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**نفس سياسة استبدال المستند** (9-ب): اعتمادٌ صدر لمركبةٍ لا يُشغَّل به غيرُها.

    وبحذف القاعدة يبقى `approved` — فيعمل بمركبةٍ لم تُراجع أوراقُها.
    """
    driver = await approved_driver(client, session_factory, DRIVER)
    vehicle = await _vehicle_of(client, driver)

    response = await client.patch(
        f"/drivers/me/vehicles/{vehicle['id']}",
        json={"plate_number": "AMM-7777"},
        headers=driver["headers"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["approval_reverted"] is True
    assert response.json()["driver_status"] == DriverStatus.PENDING.value

    # والجوابُ يقولها صراحةً — بغيره يكتشفها حين لا تصله طلبات
    profile = await client.get("/drivers/me", headers=driver["headers"])
    assert profile.json()["driver"]["status"] == DriverStatus.PENDING.value


async def test_resending_the_same_values_changes_nothing(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """التطبيق يرسل النموذج كاملاً — وإرسالُ نفس اللوحة ليس تغييراً."""
    driver = await approved_driver(client, session_factory, DRIVER)
    vehicle = await _vehicle_of(client, driver)

    response = await client.patch(
        f"/drivers/me/vehicles/{vehicle['id']}",
        json={
            "plate_number": vehicle["plate_number"],
            "make": vehicle["make"],
            "color": vehicle["color"],
        },
        headers=driver["headers"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["approval_reverted"] is False
    assert response.json()["driver_status"] == DriverStatus.APPROVED.value


async def test_the_edit_is_refused_during_an_active_ride(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """إسقاطُ الاعتماد وسط رحلةٍ يوقظ تنبيه «انقطع الكبتن» على من لم ينقطع."""
    from tests.helpers import started_ride

    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    await started_ride(client, rider["headers"], driver)
    vehicle = await _vehicle_of(client, driver)

    blocked = await client.patch(
        f"/drivers/me/vehicles/{vehicle['id']}",
        json={"plate_number": "AMM-8888"},
        headers=driver["headers"],
    )
    assert blocked.status_code == 409, blocked.text

    # واللونُ يمرّ: لا يمسّ الاعتماد فلا يمسّ الرحلة
    allowed = await client.patch(
        f"/drivers/me/vehicles/{vehicle['id']}",
        json={"color": "فضي"},
        headers=driver["headers"],
    )
    assert allowed.status_code == 200, allowed.text


async def test_another_driver_cannot_edit_it(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    from tests.helpers import SECOND_DRIVER

    owner = await approved_driver(client, session_factory, DRIVER)
    other = await approved_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-3131"
    )
    vehicle = await _vehicle_of(client, owner)

    response = await client.patch(
        f"/drivers/me/vehicles/{vehicle['id']}",
        json={"color": "أحمر"},
        headers=other["headers"],
    )
    assert response.status_code == 404, response.text


async def test_a_duplicate_plate_is_refused(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    from tests.helpers import SECOND_DRIVER

    owner = await approved_driver(client, session_factory, DRIVER)
    await approved_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-5151"
    )
    vehicle = await _vehicle_of(client, owner)

    response = await client.patch(
        f"/drivers/me/vehicles/{vehicle['id']}",
        json={"plate_number": "AMM-5151"},
        headers=owner["headers"],
    )
    assert response.status_code == 409, response.text
