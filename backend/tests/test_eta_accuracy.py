"""**دقّةُ وقت الوصول وتصحيحُه** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٢)."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.core.redis_client import get_redis_client
from app.models.enums import CountryCode
from app.models.eta_sample import EtaSample
from tests.helpers import RIDER, approved_driver, auth, bring_online, enable_features, register, request_ride, wait_for_offer


async def test_arrival_turns_the_prediction_into_a_sample_and_the_panel_reads_it(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    await enable_features(session_factory, "eta_enabled")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = auth(await register(client, RIDER))
    ride = await request_ride(client, rider)
    await wait_for_offer(ride["id"], driver["driver_id"])
    assert (await client.post(f"/rides/{ride['id']}/accept", headers=driver["headers"])).status_code == 200
    approach = await client.get(f"/rides/{ride['id']}/approach", headers=driver["headers"])
    assert approach.status_code == 200, approach.text

    redis = get_redis_client()
    stored = await redis.get(f"eta:pred:{ride['id']}")
    assert stored, "الاقترابُ يحفظ ما قيل"
    # **ثلاثُ دقائق مضت منذ التوقّع** — فالوصولُ في الثانية نفسِها صفرٌ لا يُعدّ
    import json
    from datetime import UTC, datetime, timedelta

    data = json.loads(stored)
    data["at"] = (datetime.now(UTC) - timedelta(minutes=3)).isoformat()
    await redis.set(f"eta:pred:{ride['id']}", json.dumps(data))
    arrived = await client.post(f"/rides/{ride['id']}/arrive", headers=driver["headers"])
    assert arrived.status_code == 200, arrived.text
    assert await redis.get(f"eta:pred:{ride['id']}") is None

    async with session_factory() as session:
        sample = await session.scalar(select(EtaSample).where(EtaSample.ride_id == uuid.UUID(ride["id"])))
    assert sample is not None and 170 <= sample.actual_seconds <= 240 and sample.raw_seconds >= 0

    shown = await client.get("/admin/eta/accuracy", params={"country_code": "JO"}, headers=admin_headers)
    assert shown.status_code == 200, shown.text
    body = shown.json()
    assert body["samples"] == 1 and body["mean_abs_error_min"] is not None and len(body["by_hour"]) == 1


def test_the_factor_needs_twenty_samples_and_stays_within_bounds() -> None:
    from app.services import eta_accuracy

    assert eta_accuracy.ratio_from([(600, 300)] * (eta_accuracy.MIN_SAMPLES - 1)) is None, "دون العشرين لا تصحيح"
    assert eta_accuracy.clamp(eta_accuracy.ratio_from([(600, 300)] * eta_accuracy.MIN_SAMPLES)) == 1.6, "ضعفٌ يُسقف"
    assert eta_accuracy.clamp(eta_accuracy.ratio_from([(150, 300)] * eta_accuracy.MIN_SAMPLES)) == 0.8, "ونصفٌ يُرفع"
    mixed = [(330, 300)] * 15 + [(3000, 300)] * 5
    assert eta_accuracy.clamp(eta_accuracy.ratio_from(mixed)) == 1.1, "الوسيطُ لا المتوسّط — الشاذُّ لا يقلبه"
