"""عددُ رحلات الكبتن في بطاقته — `GET /rides/{id}/driver/stats` (§٦٢-ج/٢٧، R08 «4.92 · 2,140 رحلة»).

**ما يُسأل هنا**: يقرأ راكبُ الرحلةِ الجاريةِ عددَ ما **أكمله** كبتنُها — لا ما قَبِله ولا ما أُلغي؛ وغيرُ طرفيها ٤٠٤ —
**والمشرفُ منهم**؛ **ورحلةٌ انتهت لا تبقى نافذةً** على عمل الكبتن (٤٠٩)؛ ورحلةٌ بلا كبتنٍ بعد ٤٠٤ كبابِ صورته.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import (
    OTHER_RIDER,
    RIDER,
    accepted_ride,
    approved_driver,
    auth,
    bring_online,
    completed_ride,
    register,
    request_ride,
)


async def test_the_rider_reads_how_many_rides_his_captain_completed(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """رحلةٌ مكتملةٌ مع راكبٍ أوّل، ثمّ رحلةٌ جاريةٌ مع ثانٍ: **الثاني يقرأ «1»** — والجاريةُ نفسُها لا تُعدّ."""
    first_rider = auth(await register(client, RIDER))
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    done = await completed_ride(client, first_rider, driver)

    second_rider = auth(await register(client, OTHER_RIDER))
    live = await accepted_ride(client, second_rider, driver)

    seen = await client.get(f"/rides/{live['id']}/driver/stats", headers=second_rider)
    assert seen.status_code == 200, seen.text
    assert seen.json() == {"completed_rides": 1}

    # **والكبتنُ نفسُه طرفٌ فيها** — يقرأ الرقمَ نفسَه
    own = await client.get(f"/rides/{live['id']}/driver/stats", headers=driver["headers"])
    assert own.status_code == 200, own.text
    assert own.json() == seen.json()

    # **لا IDOR**: راكبُ الرحلة الأولى غريبٌ عن الثانية، **والمشرفُ لا يقرؤها من هذا الباب**
    for stranger in (first_rider, admin_headers):
        response = await client.get(f"/rides/{live['id']}/driver/stats", headers=stranger)
        assert response.status_code == 404, response.text
        assert "completed_rides" not in response.json()

    # **ورحلتُه المنتهية لا تبقى نافذةً** على عدّادٍ يكبر كلَّ يوم
    ended = await client.get(f"/rides/{done['id']}/driver/stats", headers=first_rider)
    assert ended.status_code == 409, ended.text
    assert "completed_rides" not in ended.json()


async def test_no_captain_yet_is_404(
    client: AsyncClient, jordan_settings: None
) -> None:
    """**لا كبتنَ متصلاً فلا إسناد** — والبابُ يقول «لا كبتن» كبابِ الصورة، ولا رقمَ صفرٍ يُقرأ عن كبتنٍ لا وجودَ له."""
    rider = auth(await register(client, RIDER))
    ride = await request_ride(client, rider)

    response = await client.get(f"/rides/{ride['id']}/driver/stats", headers=rider)
    assert response.status_code == 404, response.text
    assert "completed_rides" not in response.json()
