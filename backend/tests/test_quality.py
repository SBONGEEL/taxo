"""**درجةُ جودة الكبتن** (البند ٣) — الحسابُ والأوزان، والعدّادات، وأثرُها في الترتيب حيث المفتاحُ وحده، والأبواب."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select

from app.core.redis_client import get_redis_client
from app.models.enums import CountryCode
from app.models.quality import DriverQualityScore, QualitySetting
from app.services import quality
from tests.helpers import DRIVER, approved_driver


def test_score_from_weights_and_neutral_parts() -> None:
    parts = {"acceptance": 1.0, "cancellation": 1.0, "rating": 1.0, "complaints": 1.0, "completed": 1.0}
    assert quality.score_from(quality.DEFAULTS, parts) == 100
    parts["acceptance"] = 0.0
    assert quality.score_from(quality.DEFAULTS, parts) == 70
    # وزنُ القبول صفرٌ ⇐ لا أثرَ له
    no_acceptance = quality.Weights(True, 0, 25, 25, 10, 10, 150, 50)
    assert quality.score_from(no_acceptance, parts) == 100
    assert quality.weakest(parts) == ["acceptance"]


async def test_counters_and_measure_neutral_for_new_driver(client: AsyncClient, session_factory) -> None:
    redis = get_redis_client()
    driver_id = uuid.uuid4()
    now = datetime.now(UTC)
    for _ in range(4):
        await quality.record(redis, "offered", driver_id, now)
    await quality.record(redis, "accepted", driver_id, now)
    async with session_factory() as session:
        parts, counts = await quality.measure(session, redis, driver_id=driver_id, now=now)
        assert counts["offered"] == 4 and counts["accepted"] == 1
        # أربعةُ عروضٍ دون حدِّ العيّنة ⇐ محايد، لا عقوبة
        assert parts["acceptance"] == quality.NEUTRAL
        await quality.record(redis, "offered", driver_id, now)
        parts, _ = await quality.measure(session, redis, driver_id=driver_id, now=now)
        assert parts["acceptance"] == 0.2
        assert parts["completed"] == 0.0 and parts["complaints"] == 1.0


async def test_bonus_only_when_enabled_and_the_doors(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    driver = await approved_driver(client, session_factory, DRIVER)
    headers, driver_id = driver["headers"], driver["driver_id"]
    async with session_factory() as session:
        session.add(DriverQualityScore(driver_id=driver_id, day=datetime.now(UTC).date(), score=80, components={"parts": {}, "counts": {}}))
        await session.commit()
        assert await quality.bonuses(session, CountryCode.JO, [driver_id]) == {}, "المطفأُ لا يمسّ الترتيب"

    listed = await client.get("/admin/quality/settings", headers=admin_headers)
    assert listed.status_code == 200, listed.text
    jo = next(row for row in listed.json() if row["country_code"] == "JO")
    assert jo["enabled"] is False and jo["w_acceptance"] == 30

    mine = await client.get("/drivers/me/quality", headers=headers)
    assert mine.status_code == 200, mine.text
    assert mine.json()["enabled"] is False and 0 <= mine.json()["score"] <= 100
    assert [day["score"] for day in mine.json()["history"]] == [80]

    zero = {"w_acceptance": 0, "w_cancellation": 0, "w_rating": 0, "w_complaints": 0, "w_completed": 0}
    bad = await client.patch("/admin/quality/settings/JO", headers=admin_headers, json=zero)
    assert bad.status_code == 422

    on = await client.patch(
        "/admin/quality/settings/JO", headers=admin_headers, json={"enabled": True, "warn_below": 40, "dispatch_bonus_m": 200}
    )
    assert on.status_code == 200, on.text
    assert on.json()["enabled"] is True and on.json()["warn_below"] == 40
    assert (await client.get("/drivers/me/quality", headers=headers)).json()["enabled"] is True
    assert (await client.get(f"/admin/quality/drivers/{driver_id}", headers=admin_headers)).status_code == 200

    async with session_factory() as session:
        assert await quality.bonuses(session, CountryCode.JO, [driver_id]) == {uuid.UUID(str(driver_id)): 160.0}
        row = await session.scalar(select(QualitySetting).where(QualitySetting.country_code == CountryCode.JO))
        assert row is not None and row.warn_below == 40
