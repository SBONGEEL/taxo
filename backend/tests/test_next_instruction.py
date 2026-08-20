"""«التعليمةُ التالية» — البند ٧، وقرارُ المالك 2026-08-20 (SPEC §26).

**والقرارُ الذي يحكم كلَّ ما هنا**: الشريطُ يظهر ما دام الكبتن على الخط
المجمَّد، **ويختفي صامتاً** عند الانحراف — بلا رسالةٍ وبلا «يُعاد الحساب…».
فما يقيسه هذا الملفُّ أن **الغيابَ سلوكٌ صحيحٌ لا عطب**.
"""

from __future__ import annotations

import json
import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import CountryCode, FeatureKey
from app.models.feature_flag import FeatureFlag
from app.models.ride import Ride
from tests.helpers import (
    RIDER,
    approved_driver,
    auth,
    bring_online,
    register,
    started_ride,
)


async def _route(client: AsyncClient, headers: dict, ride_id: str) -> dict:
    response = await client.get(f"/rides/{ride_id}/route-line", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def test_the_flag_off_stores_no_steps_and_the_strip_stays_silent(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**مطفأٌ افتراضاً** — ولا خطواتٍ تُطلب ولا تُخزَّن، والجوابُ قائمةٌ فارغة."""
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = auth(await register(client, RIDER))
    ride = await started_ride(client, rider, driver)

    body = await _route(client, driver["headers"], ride["id"])
    assert body["steps"] == [], body
    async with session_factory() as session:
        stored = await session.scalar(
            select(Ride.route_steps).where(Ride.id == uuid.UUID(ride["id"]))
        )
    assert stored is None


async def test_the_flag_on_stores_the_steps_with_the_line(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**من النداء نفسِه** — فلا يفترق سهمٌ عن خط."""
    async with session_factory() as session:
        session.add(
            FeatureFlag(
                country_code=CountryCode.JO,
                feature_key=FeatureKey.NEXT_INSTRUCTION_ENABLED.value,
                enabled=True,
            )
        )
        await session.commit()

    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = auth(await register(client, RIDER))
    ride = await started_ride(client, rider, driver)

    body = await _route(client, driver["headers"], ride["id"])
    assert body["steps"], body
    step = body["steps"][0]
    assert step["text"]
    assert len(step["shape"]) >= 2

    async with session_factory() as session:
        stored = await session.scalar(
            select(Ride.route_steps).where(Ride.id == uuid.UUID(ride["id"]))
        )
    assert stored is not None
    assert json.loads(stored)[0]["text"] == step["text"]


async def test_the_rider_never_receives_the_steps(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**الراكبُ لا يقودها** — وحمولتُها ثلاثةَ عشرَ ضعفَ الخط (مقيس).

    ولا يُقاس هذا بدور الحساب بل **بالرحلة نفسِها** (§22): الحسابُ قد يحمل
    الدورين، والرحلةُ تسمّي كبتنَها بيقين.
    """
    async with session_factory() as session:
        session.add(
            FeatureFlag(
                country_code=CountryCode.JO,
                feature_key=FeatureKey.NEXT_INSTRUCTION_ENABLED.value,
                enabled=True,
            )
        )
        await session.commit()

    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = auth(await register(client, RIDER))
    ride = await started_ride(client, rider, driver)

    mine = await _route(client, driver["headers"], ride["id"])
    theirs = await _route(client, rider, ride["id"])
    assert mine["steps"], "الكبتنُ يجب أن يراها"
    assert theirs["steps"] == [], "والراكبُ لا"
    # والخطُّ نفسُه يصل الاثنين — فما اختلف هو الحمولةُ الزائدة وحدَها
    assert theirs["points"] == mine["points"]


async def test_the_published_threshold_is_the_measured_one(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**العتبةُ تُنشر ولا تُكتب في التطبيق** (§17.3)، وقيمتُها مقيسة.

    ثمانون متراً: هندسةُ الخطوة خطؤها **٤٫٨ م** في أسوأ رأسٍ قِيس على مسارٍ
    حقيقيٍّ في عمّان — فهي نحوُ ستةَ عشرَ ضعفَه. **وهي عتبةُ إعادة التوجيه
    نفسُها** (البند ١٧-٤)، ورقمان لمفهومٍ واحدٍ يفترقان.
    """
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = auth(await register(client, RIDER))
    ride = await started_ride(client, rider, driver)

    body = await _route(client, driver["headers"], ride["id"])
    assert body["deviation_threshold_m"] == 80
