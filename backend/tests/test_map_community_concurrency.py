"""**تزامنُ `map_community`** (أمرُ المالك ٢٠٢٦-١١-١٨ السابع) — قفلا الصفِّ في `services/map_community.py`، **وكلٌّ يسقط بحذف قفله**.

١) **ثلاثُ موافقاتٍ معاً على اقتراحٍ واحد ⇐ مكانٌ واحد** (`_locked_suggestion`، على الخدمة بثلاث جلسات): بلا القفل تقرأ الثلاثُ «قيدَ المراجعة» وتكتب ثلاثةَ أماكن.
٢) **تأكيدان معاً لبلاغٍ واحد ⇐ ثلاثةُ تأكيداتٍ لا اثنان** (`report`): بلا القفل يقرأ الاثنان «١» ويكتبان «٢» — تحديثٌ ضائع.

**والتداخلُ مقصودٌ لا مأمول** (قِيس ٢٠٢٦-١١-١٨): النسخةُ الأولى من الاختبارين **بقيت خضراءَ والقفلان محذوفان** — الطلباتُ القصيرة
تنتهي واحداً بعد واحدٍ قبل أن تتداخل. فـ`_slow_commits` يؤخّر كلَّ `commit` أثناء الطلبات المتزامنة وحدَها: **كلُّ معاملةٍ تقرأ قبل
أن تُودِع أيّةٌ منها** — فبلا قفلٍ تقرأ كلُّها الحالَ نفسَه، وبالقفل تنتظر الثانيةُ إيداعَ الأولى وتقرأ ما كتبته.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import contextmanager

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInput
from app.models.map_community import RoadReport
from app.models.map_place import MapPlace
from app.models.user import User
from app.services import map_community
from tests.helpers import DRIVER, SECOND_DRIVER, THIRD_DRIVER, auth, enable_features, register, rider_session

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("jordan_settings")]

PLACE = {"kind": "add", "name_ar": "صيدلية النور", "category": "clinic", "lat": 31.95, "lng": 35.91}


@contextmanager
def _slow_commits(monkeypatch: pytest.MonkeyPatch, seconds: float = 0.4):
    original = AsyncSession.commit

    async def slow(self: AsyncSession) -> None:
        await asyncio.sleep(seconds)
        await original(self)

    monkeypatch.setattr(AsyncSession, "commit", slow)
    try:
        yield
    finally:
        monkeypatch.setattr(AsyncSession, "commit", original)


async def test_three_concurrent_approvals_make_one_place(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**على الخدمة لا على الباب** (قِيس ٢٠٢٦-١١-١٨): ثلاثُ موافقاتٍ عبر HTTP برمز مشرفٍ واحد **بقيت خضراءَ والقفلُ محذوف** —
    شيءٌ قبل القراءة يُسلسل طلباتِ الرمز الواحد، فلا يقيس الاختبارُ القفل. فالثلاثُ هنا بثلاث جلساتٍ متزامنةٍ على `approve` نفسِها."""
    await enable_features(session_factory, "map_place_suggestions")
    rider = await rider_session(client)
    sid = uuid.UUID((await client.post("/map/suggestions", json=PLACE, headers=rider["headers"])).json()["id"])

    async def approve_once() -> str:
        async with session_factory() as session:
            reviewer = await session.get(User, uuid.UUID(rider["user"]["id"]))
            try:
                await map_community.approve(session, sid, reviewer, name_ar=None, category=None)
                return "ok"
            except InvalidInput:
                await session.rollback()
                return "reviewed"

    with _slow_commits(monkeypatch):
        results = await asyncio.wait_for(asyncio.gather(*[approve_once() for _ in range(3)]), timeout=30)
    assert sorted(results) == ["ok", "reviewed", "reviewed"], results
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(MapPlace).where(MapPlace.source == "community")) == 1


async def test_two_drivers_confirming_at_once_lose_no_confirmation(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await enable_features(session_factory, "map_road_reports")
    first = auth(await register(client, DRIVER))
    second = auth(await register(client, SECOND_DRIVER))
    third = auth(await register(client, THIRD_DRIVER))
    spot = {"kind": "accident", "lat": 31.97, "lng": 35.88}
    await client.post("/map/road-reports", json=spot, headers=first)
    with _slow_commits(monkeypatch):
        await asyncio.wait_for(
            asyncio.gather(*[client.post("/map/road-reports", json=spot, headers=h) for h in (second, third)]), timeout=30
        )
    async with session_factory() as session:
        rows = list(await session.scalars(select(RoadReport)))
    assert len(rows) == 1 and rows[0].confirmations == 3, [(r.id, r.confirmations) for r in rows]
