"""مسار الرحلة الفعلي وأثره في السعر النهائي (SPEC القسم 5.7/5.8).

المسار هنا شيئان يُختبران منفصلين: **الالتقاط** من بثّ الكبتن بنافذة أخذ
عيّنة، و**الحساب** الذي يبني عليه `final_fare`. خلطهما يعني اختباراً يسابق
مؤقتاً كي يتحقق من حسابٍ لا علاقة له بالوقت.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.ride import RideRoutePoint
from app.services import route
from tests.helpers import (
    NEAR_PICKUP,
    PICKUP,
    RIDER,
    add_route_points,
    approved_driver,
    auth,
    bring_online,
    broadcast_location,
    completed_ride,
    register,
    started_ride,
)

# درجة عرضٍ واحدة ≈ 111.195 كم على خط الطول نفسه — منها تُشتق مساراتٌ
# معلومة الطول بلا اعتماد على حساب PostGIS الذي نختبره
_KM_PER_DEGREE = Decimal("111.195")

# المقدَّر في كل هذه الاختبارات 10 كم (STUB_ROUTE)، وعتبة إعادة الحساب 20%
_LONG_ROUTE_KM = Decimal("15")  # انحراف 50% — يعيد الحساب
_CLOSE_ROUTE_KM = Decimal("10.5")  # انحراف 5% — لا يعيده


def _points_spanning(km: Decimal) -> list[tuple[float, float]]:
    """نقطتان على نفس خط الطول بينهما المسافة المطلوبة."""
    delta = float(km / _KM_PER_DEGREE)
    return [
        (PICKUP["lat"], PICKUP["lng"]),
        (PICKUP["lat"] + delta, PICKUP["lng"]),
    ]


async def _rider(client: AsyncClient, payload: dict = RIDER) -> dict:
    return auth(await register(client, payload))


async def _online_driver(client: AsyncClient, session_factory) -> dict:
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    return driver


async def _point_count(session_factory, ride_id: str) -> int:
    async with session_factory() as session:
        return await session.scalar(
            select(func.count(RideRoutePoint.id)).where(
                RideRoutePoint.ride_id == uuid.UUID(ride_id)
            )
        )


# ------------------------------------------------------------------ الالتقاط


@pytest.fixture
def fast_sampling(monkeypatch: pytest.MonkeyPatch) -> None:
    """يضغط نافذة أخذ العيّنة إلى ثانية — أقصر ما يقبله عمر مفتاح Redis.

    العشرون ثانية الحقيقية داخل نافذة SPEC وصحيحة في التشغيل ومستحيلة في
    اختبار. الاختبار المعنيّ بالنافذة نفسها لا يستعمل هذه.
    """
    monkeypatch.setattr(route, "SAMPLE_INTERVAL_SECONDS", 1)


async def test_broadcasts_during_the_ride_become_route_points(
    client: AsyncClient,
    jordan_settings: None,
    session_factory,
    fast_sampling: None,
) -> None:
    """بثّ الكبتن أثناء `in_progress` يُخزَّن نقاطاً في القاعدة."""
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await started_ride(client, rider, driver)

    for step in range(3):
        await broadcast_location(
            client, driver, NEAR_PICKUP["lat"] + step * 0.001, NEAR_PICKUP["lng"]
        )
        # **١٫٣ لا ١٫٠٥** (قِيس ٢٠٢٦-٠٩-٠٥): النافذةُ **مفتاحُ Redis بعمر
        # ثانية**، **وRedis يُنهي المفاتيحَ كسولاً لا في اللحظة** — فمفتاحٌ
        # عمرُه ثانيةٌ قد يعيش بعدها أجزاءَ من ثانية. **وهامشُ ٥٪ ليس هامشاً**:
        # سقط الاختبارُ مرّتين في مجموعةٍ كاملةٍ على جهازٍ محمَّل (`2 == 3`)
        # **ومرّ وحدَه في كلِّ مرّة** — وهو حدُّ التوقيت لا عطبٌ في الشيفرة.
        # **والثمنُ ٠٫٧٥ ثانيةٍ في الاختبار كلِّه**، وهو أرخصُ من مجموعةٍ
        # حمراءَ تُقرأ عطباً فيُبحث عمّا ليس موجوداً.
        await asyncio.sleep(1.3)  # تنقضي النافذة فتُقبل العيّنة التالية

    assert await _point_count(session_factory, ride["id"]) == 3


async def test_sampling_window_drops_broadcasts_that_come_too_soon(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """البثّ كل ثلاث ثوانٍ والعيّنة كل عشرين — فثلاث بثّاتٍ متلاحقة نقطةٌ واحدة."""
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await started_ride(client, rider, driver)

    for step in range(3):
        await broadcast_location(
            client, driver, NEAR_PICKUP["lat"] + step * 0.001, NEAR_PICKUP["lng"]
        )

    assert await _point_count(session_factory, ride["id"]) == 1


async def test_no_points_before_start_or_after_complete(
    client: AsyncClient,
    jordan_settings: None,
    session_factory,
    fast_sampling: None,
) -> None:
    """المسار هو ما بين `in_progress` والإنهاء — لا ما قبله ولا ما بعده.

    ما قبل البدء طريقُ الكبتن إلى الراكب لا مسار الرحلة، وما بعد الإنهاء
    نقطةٌ تُضاف لمسارٍ حُسبت مسافته وثُبّت سعره بالفعل.
    """
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)

    from tests.helpers import accepted_ride

    ride = await accepted_ride(client, rider, driver)
    await asyncio.sleep(1.05)
    await broadcast_location(client, driver, NEAR_PICKUP["lat"], NEAR_PICKUP["lng"])
    assert await _point_count(session_factory, ride["id"]) == 0

    for step in ("arrive", "start", "complete"):
        response = await client.post(
            f"/rides/{ride['id']}/{step}", headers=driver["headers"]
        )
        assert response.status_code == 200, response.text

    after_complete = await _point_count(session_factory, ride["id"])
    await asyncio.sleep(1.05)
    await broadcast_location(client, driver, NEAR_PICKUP["lat"], NEAR_PICKUP["lng"])
    assert await _point_count(session_factory, ride["id"]) == after_complete


# -------------------------------------------------------------- المسافة والسعر


async def test_large_deviation_recalculates_the_final_fare(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """مسارٌ فعليّ 15 كم مقابل 10 مقدَّرة — يُعاد حساب السعر عليه (القسم 5.7)."""
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await started_ride(client, rider, driver)
    await add_route_points(
        session_factory, ride["id"], _points_spanning(_LONG_ROUTE_KM)
    )

    completed = (
        await client.post(f"/rides/{ride['id']}/complete", headers=driver["headers"])
    ).json()

    actual = Decimal(completed["actual_distance_km"])
    assert actual == pytest.approx(_LONG_ROUTE_KM, abs=Decimal("0.05"))
    # 1.000 + (actual × 0.500) + (20 × 0.100) — نفس تسعيرة الأردن في الاختبارات
    expected = (Decimal("1.000") + actual * Decimal("0.5") + Decimal("2.000")).quantize(
        Decimal("0.001")
    )
    assert Decimal(completed["final_fare"]) == expected
    assert completed["final_fare"] != completed["estimated_fare"]


async def test_small_deviation_keeps_the_estimated_fare(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """انحراف 5% لا يُحرّك السعر: المقدَّر هو ما وافق عليه الراكب."""
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await started_ride(client, rider, driver)
    await add_route_points(
        session_factory, ride["id"], _points_spanning(_CLOSE_ROUTE_KM)
    )

    completed = (
        await client.post(f"/rides/{ride['id']}/complete", headers=driver["headers"])
    ).json()

    assert Decimal(completed["actual_distance_km"]) == pytest.approx(
        _CLOSE_ROUTE_KM, abs=Decimal("0.05")
    )
    assert completed["final_fare"] == completed["estimated_fare"]


async def test_a_single_point_is_not_a_distance(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """نقطةٌ واحدة ليست مساراً: تبقى المسافة الفعلية فارغة والسعر المقدَّر.

    الفراغ هنا ليس صفراً عمداً — صفرٌ يعني «سارت صفر كيلومتر» فيهبط السعر
    إلى الحد الأدنى ظلماً بسبب تطبيقٍ صمت.
    """
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await started_ride(client, rider, driver)
    await add_route_points(session_factory, ride["id"], [(PICKUP["lat"], PICKUP["lng"])])

    completed = (
        await client.post(f"/rides/{ride['id']}/complete", headers=driver["headers"])
    ).json()

    assert completed["actual_distance_km"] is None
    assert completed["final_fare"] == completed["estimated_fare"]


async def test_ride_without_any_points_keeps_the_estimate(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    completed = await completed_ride(client, rider, driver)

    assert completed["actual_distance_km"] is None
    assert completed["final_fare"] == completed["estimated_fare"]


def test_deviation_threshold_is_symmetric() -> None:
    """الانحراف في الاتجاهين: أطولُ يُنصف الكبتن وأقصرُ يُنصف الراكب."""
    assert route.deviates(Decimal("10"), Decimal("13"))
    assert route.deviates(Decimal("10"), Decimal("7"))
    assert not route.deviates(Decimal("10"), Decimal("12"))
    assert not route.deviates(Decimal("10"), Decimal("8"))
