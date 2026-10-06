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


# --------------------------------------------- سهمُ المناورة (§٦٢-ج/٤٢)


def test_each_step_keeps_its_maneuver_word_and_nothing_foreign() -> None:
    """**النوعُ والاتجاهُ بكلمة Mapbox كما هي — أو لا شيء**.

    والسهمُ يُرسم منهما لا من النصّ؛ فكلمةٌ غريبةٌ (وسمٌ، أو نصٌّ طويل) تُسقَط
    ولا تُسقِط الخطوة: خطوةٌ بلا سهمٍ خيرٌ من خطوةٍ ضائعة أو سهمٍ مخمَّن.
    """
    from app.services.directions import _collect_steps

    line = {"coordinates": [[35.90, 31.95], [35.91, 31.951]]}
    steps = _collect_steps(
        {
            "legs": [
                {
                    "steps": [
                        {"maneuver": {"instruction": "انعطف يميناً إلى شارع الملكة رانيا", "type": "turn", "modifier": "right"}, "distance": 200.4, "geometry": line},
                        {"maneuver": {"instruction": "اسلك المنحدر", "type": "off ramp", "modifier": "slight left"}, "distance": 90, "geometry": line},
                        {"maneuver": {"instruction": "وصلت إلى وجهتك", "type": "arrive"}, "distance": 0, "geometry": line},
                        {"maneuver": {"instruction": "تابع", "type": "<b>turn</b>", "modifier": "x" * 40}, "distance": 10, "geometry": line},
                        # بلا نصٍّ لا خطوة — القاعدةُ القائمةُ كما هي
                        {"maneuver": {"type": "turn", "modifier": "left"}, "distance": 10, "geometry": line},
                    ]
                }
            ]
        }
    )
    assert steps is not None
    assert [(s["maneuver"], s["modifier"]) for s in steps] == [
        ("turn", "right"),
        ("off ramp", "slight left"),
        ("arrive", None),
        (None, None),
    ]
    assert steps[0]["distance_m"] == 200 and steps[0]["text"].startswith("انعطف")


async def test_the_driver_reads_the_maneuver_with_each_step(
    client: AsyncClient, session_factory, jordan_settings: None, monkeypatch
) -> None:
    """**من التخزين إلى الباب بلا ضياع** — وخطوةٌ خُزِّنت بلا كلمةٍ تصل بـ`null` لا بخطأ."""
    from app.services import directions

    stub = directions.fetch_route

    async def with_maneuvers(token, *waypoints, with_geometry=False, with_steps=False):
        route = await stub(token, *waypoints, with_geometry=with_geometry, with_steps=with_steps)
        if route.steps:
            route.steps[0]["maneuver"] = "turn"
            route.steps[0]["modifier"] = "sharp left"
            route.steps.append({**route.steps[0], "maneuver": None, "modifier": None})
        return route

    monkeypatch.setattr(directions, "fetch_route", with_maneuvers)
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

    steps = (await _route(client, driver["headers"], ride["id"]))["steps"]
    assert [(s["maneuver"], s["modifier"]) for s in steps] == [("turn", "sharp left"), (None, None)]


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
