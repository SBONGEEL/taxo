"""رابطا تنزيل التطبيقين في `GET /config` (زرُّ «كن سائقاً / كن راكباً»، أمرُ المالك ٢٠٢٦-١١-٠٢).

**وما يُقاس هنا أن الرابطَ إعدادُ خادمٍ لا ثابتٌ**: يُقرأ من حقلَي المتجر في إعدادات الموقع، **والفارغُ يذهب إلى الموقع الرسميّ**
— فيومَ يُكتب رابطُ Play للكبتن من اللوحة يتبدّل الزرُّ بلا إصدار.
"""

from __future__ import annotations

import pytest

from app.services import site as site_service

pytestmark = pytest.mark.asyncio

PLAY_DRIVER = "https://play.google.com/store/apps/details?id=ly.tajora.driver"


async def test_without_a_settings_row_the_rider_goes_to_play_and_the_captain_to_the_site(client) -> None:
    links = (await client.get("/config")).json()["app_links"]
    assert links["rider"] == {"package": "ly.tajora.rider", "download_url": site_service.play_url("ly.tajora.rider")}
    assert links["driver"] == {"package": "ly.tajora.driver", "download_url": site_service.PUBLIC_SITE_URL}


async def test_the_links_follow_the_site_settings(client, session_factory) -> None:
    async with session_factory() as session:
        row = await site_service.get_or_create(session)
        row.play_url_rider = ""
        row.play_url_driver = PLAY_DRIVER
        await session.commit()

    links = (await client.get("/config")).json()["app_links"]
    # **الفارغُ يعني «لا رابطَ متجرٍ بعد»** — فالموقعُ الرسميّ، كما تذهب بطاقةُ الموقع إلى ملفّها
    assert links["rider"]["download_url"] == site_service.PUBLIC_SITE_URL
    assert links["driver"]["download_url"] == PLAY_DRIVER
