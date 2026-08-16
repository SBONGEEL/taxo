"""إعادةُ توجيه المسار وسقفُها (البند ١٧-٤، `FUTURE-FEATURES` 17).

**والسقفُ هو الاختبارُ الذي يستحقّ أن يُقرأ**: إعادةُ التوجيه **هي الشيءُ الوحيد
الذي يعاود نداءَ Directions**، فسقفٌ لا يحرس هو فاتورةٌ بلا حدّ. وحسابُ المالك:
ألفُ رحلةٍ يومياً بأربعة نداءاتٍ → ١٢٠ ألفاً شهرياً، وبثلاثِ إعاداتٍ → ٢٧٠ ألفاً،
وبلا سقفٍ → ما لا يُحسب سلفاً.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.models.ride import Ride
from app.services import route_line
from tests.helpers import (
    DRIVER,
    accepted_ride,
    approved_driver,
    bring_online,
    rider_session,
    started_ride,
)


async def test_the_reroute_cap_is_enforced_in_the_backend(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**السقفُ في الخلفية لا في التطبيق**: عميلٌ يعدّ لنفسه عميلٌ يوجّه إنفاقاً.

    ويُتحقَّق منه برفع `MAX_REROUTES`: عندها يمرّ نداءٌ رابعٌ فيفشل هذا الاختبار.
    """
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await started_ride(client, rider["headers"], driver)

    seen = []
    for _ in range(route_line.MAX_REROUTES + 2):
        response = await client.post(
            f"/rides/{ride['id']}/reroute", headers=driver["headers"]
        )
        assert response.status_code == 200, response.text
        seen.append(response.json()["reroutes_left"])

    # ثلاثُ إعاداتٍ ثم صفرٌ يبقى صفراً — **ولا خطأ**: الكفُّ راحةٌ لا رفض
    assert seen[: route_line.MAX_REROUTES] == [2, 1, 0]
    assert all(value == 0 for value in seen[route_line.MAX_REROUTES :])

    async with session_factory() as session:
        row = await session.scalar(
            select(Ride).where(Ride.id == __import__("uuid").UUID(ride["id"]))
        )
    assert row.reroute_count == route_line.MAX_REROUTES


async def test_a_rider_cannot_spend_a_rides_reroutes(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**للكبتن وحدَه**: هو من انحرف وهو من يقود.

    ولو فُتح للراكب لصار لكلِّ رحلةٍ طالبان لنداءٍ واحدٍ مدفوع — وللراكب خطُّه
    المجمَّد على رحلته أصلاً.
    """
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await started_ride(client, rider["headers"], driver)

    refused = await client.post(
        f"/rides/{ride['id']}/reroute", headers=rider["headers"]
    )
    assert refused.status_code in (403, 404)


async def test_a_failed_provider_call_keeps_the_old_line_and_costs_no_quota(
    client: AsyncClient, session_factory, monkeypatch, jordan_settings: None
) -> None:
    """**خطٌّ قديمٌ أنفعُ من لا خطّ**، والسقفُ يُستهلك بالنجاح وحدَه.

    ونداءٌ سقط لم يكلّف شيئاً، وخصمُه من رصيدِ كبتنٍ انحرف مرةً يجعل العطبَ
    عقوبةً عليه.
    """
    from app.core.exceptions import AppError
    from app.services import directions

    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await started_ride(client, rider["headers"], driver)

    class Boom(AppError):
        status_code = 502
        code = "provider_unavailable"
        message = "المزود لا يستجيب"

    async def _boom(*args, **kwargs):
        raise Boom()

    monkeypatch.setattr(directions, "route_between", _boom)
    response = await client.post(
        f"/rides/{ride['id']}/reroute", headers=driver["headers"]
    )
    assert response.status_code == 200
    # لم يُستهلك شيءٌ من السقف
    assert response.json()["reroutes_left"] == route_line.MAX_REROUTES

    async with session_factory() as session:
        row = await session.scalar(
            select(Ride).where(Ride.id == __import__("uuid").UUID(ride["id"]))
        )
    assert row.reroute_count == 0
    # **والخطُّ القديم باقٍ** لا مُمحى
    assert row.route_polyline is not None
