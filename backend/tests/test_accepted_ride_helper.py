"""**`helpers.accepted_ride` يطلب رحلةً جديدةً حين ينهي التوزيعُ بحثَ الأولى بلا عرض** (CI ‎38164641410، 2026-10-11).

**ما وقع**: `test_ride_calls_concurrency::test_answer_and_start_racing_completion_find_the_window_closed` سقط عند `f17b403`
بـ«لم يصل عرض الرحلة لأي كبتن» وستُّ مجموعاتٍ متوازيةٌ على المشغّل — **والاختبارُ والتوزيعُ لم يتغيّر منهما حرف**. ومهلةُ البحث في
الاختبارات خمسُ ثوانٍ: دورةٌ أولى أبطأُ منها تُنهي الرحلةَ `no_driver_found`، والمساعدُ كان ينتظر عشرين ثانيةً عرضاً لن يأتي.

**والحالُ تُصنع هنا لا تُنتظر من الحمل**: التوزيعُ لا يرى أحداً **للرحلة الأولى وحدَها** (`_ranked_candidates` فارغةٌ لها)، فتنتهي
بلا عرض — **والمساعدُ يطلب الثانيةَ فتُقبل**. **وبالمساعد القديم يسقط هذا الاختبار** بنصِّ العطب نفسِه.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services import dispatch
from tests.helpers import accepted_ride, approved_driver, bring_online, rider_session

pytestmark = pytest.mark.usefixtures("jordan_settings")


async def test_a_search_that_ended_without_an_offer_is_requested_again(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = dispatch._ranked_candidates
    first: dict = {}

    async def _blind_to_the_first(session, redis, *, ride, **kwargs):
        first.setdefault("id", ride.id)
        if ride.id == first["id"]:
            return []
        return await real(session, redis, ride=ride, **kwargs)

    monkeypatch.setattr(dispatch, "_ranked_candidates", _blind_to_the_first)
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)

    ride = await accepted_ride(client, rider["headers"], driver)

    assert ride["status"] == "accepted"
    assert str(first["id"]) != ride["id"]
    gave_up = await client.get(f"/rides/{first['id']}", headers=rider["headers"])
    assert gave_up.json()["status"] == "no_driver_found"
