"""«تعديل الوجهة» (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-أ).

**ما طلبه المالكُ اختباراً اختباراً**: المفتاحُ مطفأٌ ومشتعل · التعديلُ أثناء البحث · وأثناء الرحلة · رفضُ الراكب · الكبتنُ غيرُ متّصل ·
انقطاعُ الشبكة (تأكيدٌ يُعاد). **ومعها**: الأجرةُ بالمعادلة نفسِها (تساوي تقديرَ الطلب للوجهة الجديدة) · الأجرةُ النهائيّةُ = ما أكّده
الراكبُ ولو انحرف الطريق · عرضٌ انقضى لا يُطبَّق · الكبتنُ لا يغيّر · ما لا يُعدَّل بنوعه · **والتزامن**: تأكيدان في لحظةٍ واحدةٍ
يطبّقان مرّةً واحدة — **في `test_destination_change_concurrency.py`** (حارسُ الأقفال يقرأ ملفّاتِ التزامن بأسمائها).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.audit import AdminAuditLog
from app.models.destination_change import RideDestinationChange
from app.models.enums import FeatureKey
from app.models.notification import UserNotification
from tests.helpers import (
    DRIVER,
    NEAR_PICKUP,
    PICKUP,
    RIDER,
    accepted_ride,
    add_route_points,
    approved_driver,
    auth,
    bring_online,
    broadcast_location,
    enable_features,
    register,
    request_ride,
    started_ride,
)

SEARCHING = "destination_change_searching"
IN_RIDE = "destination_change_in_ride"
NEW_TARGET = {"lat": 31.9700, "lng": 35.8700, "address": "دوار الداخلية"}


async def _driver(client, session_factory) -> dict:
    driver = await approved_driver(client, session_factory, DRIVER, plate_number="12-34567", category="economy")
    await bring_online(client, driver, NEAR_PICKUP)
    return driver


async def _quote(client: AsyncClient, headers: dict, ride_id: str, target: dict = NEW_TARGET):
    return await client.post(f"/rides/{ride_id}/destination/quote", json=target, headers=headers)


async def _confirm(client: AsyncClient, headers: dict, ride_id: str, change_id: str):
    return await client.post(f"/rides/{ride_id}/destination/{change_id}/confirm", headers=headers)


async def _audits(session_factory, ride_id: str) -> int:
    async with session_factory() as session:
        return await session.scalar(
            select(func.count()).select_from(AdminAuditLog).where(
                AdminAuditLog.entity_type == "ride", AdminAuditLog.entity_id == uuid.UUID(ride_id)
            )
        )


# ------------------------------------------------------------- المفتاحُ مطفأٌ ومشتعل


async def test_switches_off_refuse_and_change_nothing(client: AsyncClient, jordan_settings: None, session_factory) -> None:
    """**مطفأٌ ⇒ ٤٠٣ ولا شيءَ يتغيّر** — ومفتاحُ البحث لا يفتح ما بعد القبول، فهما مفتاحان لا واحد."""
    rider = auth(await register(client, RIDER))
    ride = await request_ride(client, rider)
    refused = await _quote(client, rider, ride["id"])
    assert refused.status_code == 403 and refused.json()["code"] == "feature_disabled"

    driver = await _driver(client, session_factory)
    await client.post(f"/rides/{ride['id']}/cancel", json={}, headers=rider)
    await enable_features(session_factory, SEARCHING)
    accepted = await accepted_ride(client, rider, driver)
    refused = await _quote(client, rider, accepted["id"])
    assert refused.status_code == 403 and refused.json()["code"] == "feature_disabled"

    unchanged = (await client.get(f"/rides/{accepted['id']}", headers=rider)).json()
    assert unchanged["dropoff"] == accepted["dropoff"] and unchanged["estimated_fare"] == accepted["estimated_fare"]
    assert unchanged["destination_editable"] is True


# ------------------------------------------------------------- أثناء البحث


async def test_change_while_searching_prices_like_a_new_request(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**العرضُ لا يغيّر شيئاً، والتأكيدُ يغيّر الوجهةَ والأجرةَ معاً** — والأجرةُ تساوي تقديرَ الطلب للوجهة الجديدة حرفاً."""
    await enable_features(session_factory, SEARCHING)
    rider = auth(await register(client, RIDER))
    ride = await request_ride(client, rider)

    quoted = await _quote(client, rider, ride["id"])
    assert quoted.status_code == 201, quoted.text
    quote = quoted.json()
    assert quote["phase"] == "searching" and quote["status"] == "quoted"
    assert 0 < quote["expires_in_seconds"] <= 120

    estimate = await client.post(
        "/rides/estimate",
        json={"pickup": PICKUP, "dropoff": {"lat": NEW_TARGET["lat"], "lng": NEW_TARGET["lng"]}, "vehicle_category": "economy"},
        headers=rider,
    )
    assert Decimal(quote["fare"]) == Decimal(estimate.json()["estimated_fare"])

    before = (await client.get(f"/rides/{ride['id']}", headers=rider)).json()
    assert before["dropoff"] == ride["dropoff"], "العرضُ وحدَه غيّر الرحلة"

    confirmed = await _confirm(client, rider, ride["id"], quote["id"])
    assert confirmed.status_code == 200, confirmed.text
    after = confirmed.json()
    assert after["dropoff"]["lat"] == NEW_TARGET["lat"] and after["dropoff"]["lng"] == NEW_TARGET["lng"]
    assert after["dropoff_address"] == "دوار الداخلية"
    assert Decimal(after["estimated_fare"]) == Decimal(quote["fare"])
    assert sum(Decimal(line["amount"]) for line in after["fare_lines"]) == Decimal(after["estimated_fare"])
    assert await _audits(session_factory, ride["id"]) == 1

    history = (await client.get(f"/rides/{ride['id']}/destination/changes", headers=rider)).json()
    assert [row["status"] for row in history] == ["confirmed"]


# ------------------------------------------------------------- أثناء الرحلة


async def test_change_after_acceptance_tells_the_driver(client: AsyncClient, jordan_settings: None, session_factory) -> None:
    """**الكبتنُ يُخبَر بالوجهة والأجرة**، ويقرأ الرحلةَ بقيمها الجديدة — والكبتنُ نفسُه لا يغيّرها."""
    await enable_features(session_factory, IN_RIDE)
    rider = auth(await register(client, RIDER))
    driver = await _driver(client, session_factory)
    ride = await accepted_ride(client, rider, driver)

    by_driver = await _quote(client, driver["headers"], ride["id"])
    assert by_driver.status_code == 403

    quote = (await _quote(client, rider, ride["id"])).json()
    assert quote["phase"] == "in_ride"
    assert (await _confirm(client, rider, ride["id"], quote["id"])).status_code == 200

    seen = (await client.get(f"/rides/{ride['id']}", headers=driver["headers"])).json()
    assert seen["dropoff_address"] == "دوار الداخلية"
    assert Decimal(seen["estimated_fare"]) == Decimal(quote["fare"])

    async with session_factory() as session:
        notice = await session.scalar(
            select(UserNotification).where(
                UserNotification.user_id == uuid.UUID(driver["user_id"]),
                UserNotification.kind == "ride_destination_changed",
            )
        )
    assert notice is not None and "دوار الداخلية" in notice.body


async def test_in_progress_fare_is_travelled_plus_remaining_and_final_is_what_was_confirmed(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**أثناء الرحلة**: المقطوعُ + من موضع الكبتن إلى الوجهة الجديدة بالمعادلة نفسِها، **والأجرةُ النهائيّةُ ما أكّده الراكب** ولو
    سجّل المسارُ طريقاً ينحرف كثيراً — فالمؤكَّدُ لا يُعاد حسابُه."""
    await enable_features(session_factory, IN_RIDE)
    rider = auth(await register(client, RIDER))
    driver = await _driver(client, session_factory)
    ride = await started_ride(client, rider, driver)
    await broadcast_location(client, driver, 31.9650, 35.9000)

    quote = (await _quote(client, rider, ride["id"])).json()
    # المقطوعُ (طريقُ الانطلاق إلى موضعه: ١٠ كم في المحاكي) + الباقي (١٠ كم) ⇒ أكثرُ من أجرة الطلب على ١٠ كم
    assert Decimal(quote["fare"]) > Decimal(ride["estimated_fare"])
    assert (await _confirm(client, rider, ride["id"], quote["id"])).status_code == 200

    # مسارٌ مسجَّلٌ يبلغ عشرات الكيلومترات — بلا التجميد يُعاد السعرُ على المسافة الفعليّة
    await add_route_points(session_factory, ride["id"], [(31.95 + i * 0.02, 35.91) for i in range(40)])
    completed = await client.post(f"/rides/{ride['id']}/complete", headers=driver["headers"])
    assert completed.status_code == 200, completed.text
    assert Decimal(completed.json()["final_fare"]) == Decimal(quote["fare"])


async def test_unknown_driver_position_mid_ride_is_not_guessed(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**موضعٌ مجهولٌ لا يُخمَّن** — ٤٠٩ «حاول بعد لحظات»، ولا عرضَ يُحفظ."""
    from app.core.redis_client import get_redis_client
    from app.services import geo

    await enable_features(session_factory, IN_RIDE)
    rider = auth(await register(client, RIDER))
    driver = await _driver(client, session_factory)
    ride = await started_ride(client, rider, driver)
    await get_redis_client().delete(geo.presence_key(driver["driver_id"]))

    refused = await _quote(client, rider, ride["id"])
    assert refused.status_code == 409 and refused.json()["code"] == "driver_position_unknown"


# ------------------------------------------------------------- الرفضُ والانقضاء


async def test_rider_declines_and_nothing_changes(client: AsyncClient, jordan_settings: None, session_factory) -> None:
    await enable_features(session_factory, SEARCHING)
    rider = auth(await register(client, RIDER))
    ride = await request_ride(client, rider)
    quote = (await _quote(client, rider, ride["id"])).json()

    declined = await client.post(f"/rides/{ride['id']}/destination/{quote['id']}/decline", headers=rider)
    assert declined.status_code == 200 and declined.json()["status"] == "declined"
    late = await _confirm(client, rider, ride["id"], quote["id"])
    assert late.status_code == 409 and late.json()["code"] == "destination_quote_expired"

    after = (await client.get(f"/rides/{ride['id']}", headers=rider)).json()
    assert after["dropoff"] == ride["dropoff"] and after["estimated_fare"] == ride["estimated_fare"]
    assert await _audits(session_factory, ride["id"]) == 0


async def test_an_expired_quote_is_not_applied(client: AsyncClient, jordan_settings: None, session_factory) -> None:
    """**تركُه حتى ينقضي رفض** — «إن لم يؤكّد لا يتغيّر شيء»."""
    await enable_features(session_factory, SEARCHING)
    rider = auth(await register(client, RIDER))
    ride = await request_ride(client, rider)
    quote = (await _quote(client, rider, ride["id"])).json()
    async with session_factory() as session:
        row = await session.get(RideDestinationChange, uuid.UUID(quote["id"]))
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()

    late = await _confirm(client, rider, ride["id"], quote["id"])
    assert late.status_code == 409 and late.json()["code"] == "destination_quote_expired"
    after = (await client.get(f"/rides/{ride['id']}", headers=rider)).json()
    assert after["dropoff"] == ride["dropoff"]


# ------------------------------------------------------------- الكبتنُ غيرُ متّصل · انقطاعُ الشبكة


async def test_driver_offline_still_finds_the_new_destination(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**كبتنٌ غيرُ متّصلٍ لا يُفقد عليه شيء** — الإشعارُ في صندوقه، والوجهةُ الجديدةُ في الرحلة حين يفتحها."""
    await enable_features(session_factory, IN_RIDE)
    rider = auth(await register(client, RIDER))
    driver = await _driver(client, session_factory)
    ride = await accepted_ride(client, rider, driver)
    await client.post("/drivers/me/offline", headers=driver["headers"])

    quote = (await _quote(client, rider, ride["id"])).json()
    assert (await _confirm(client, rider, ride["id"], quote["id"])).status_code == 200
    seen = (await client.get(f"/rides/{ride['id']}", headers=driver["headers"])).json()
    assert seen["dropoff_address"] == "دوار الداخلية"


async def test_confirm_resent_after_network_loss_applies_once(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**تأكيدٌ يُعاد** (انقطعت الشبكةُ بعد الإرسال) يردّ الرحلةَ نفسَها ولا يطبّق مرّتين — ولا إشعارَ ثانٍ."""
    await enable_features(session_factory, IN_RIDE)
    rider = auth(await register(client, RIDER))
    driver = await _driver(client, session_factory)
    ride = await accepted_ride(client, rider, driver)
    quote = (await _quote(client, rider, ride["id"])).json()

    first = await _confirm(client, rider, ride["id"], quote["id"])
    again = await _confirm(client, rider, ride["id"], quote["id"])
    assert first.status_code == again.status_code == 200
    assert first.json()["estimated_fare"] == again.json()["estimated_fare"]
    assert await _audits(session_factory, ride["id"]) == 1
    async with session_factory() as session:
        notices = await session.scalar(
            select(func.count()).select_from(UserNotification).where(
                UserNotification.user_id == uuid.UUID(driver["user_id"]),
                UserNotification.kind == "ride_destination_changed",
            )
        )
    assert notices == 1


# ------------------------------------------------------------- ما لا يُعدَّل بنوعه


async def test_a_ride_with_stops_is_not_editable(client: AsyncClient, jordan_settings: None, session_factory) -> None:
    await enable_features(session_factory, SEARCHING, FeatureKey.MULTI_STOP_ENABLED.value)
    rider = auth(await register(client, RIDER))
    ride = await request_ride(client, rider, stops=[{"lat": 31.9650, "lng": 35.9000}])
    assert ride["destination_editable"] is False
    refused = await _quote(client, rider, ride["id"])
    assert refused.status_code == 409 and refused.json()["code"] == "destination_change_not_allowed"
