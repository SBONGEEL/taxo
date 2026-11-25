"""**غلافُ الراكب بمفتاح الرفع القديم** (أمرُ المالك ٢٠٢٦-١١-٢٦، SPEC §١١٦) — رسالةٌ اختياريّةٌ إلى Play في كلِّ فتح، وعدُّ من رآها ومن انتقل."""

from __future__ import annotations

from httpx import AsyncClient

from app.core.redis_client import get_redis_client
from app.services import releases as releases_service


async def _version(client: AsyncClient, app: str, build: int, platform: str = "android", ip: str = "198.51.100.7"):
    response = await client.get(
        "/public/app-version",
        params={"app": app, "build": build, "platform": platform},
        headers={"X-Forwarded-For": ip},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_the_old_key_rider_gets_play_once_per_open(client: AsyncClient) -> None:
    """772 وما دونه: **اختياريٌّ برابط Play ونصِّ الحذف والتثبيت، و«لاحقاً» حتى الفتح التالي** — ولا سجلَّ في اللوحة يلزم."""
    for build in (772, 496):
        body = await _version(client, "rider", build)
        assert body["state"] == "optional"
        assert body["download_url"] == "https://play.google.com/store/apps/details?id=ly.tajora.rider"
        assert body["reminder_hours"] == 0
        assert "Google Play" in body["release_notes"] and "سجّل الدخول" in body["release_notes"]


async def test_play_builds_drivers_and_ios_are_untouched(client: AsyncClient) -> None:
    """**ما بعد 772 والكبتنُ وiOS كما كانوا** — بلا سجلٍّ: `ok` بحقولٍ فارغة."""
    for app, build, platform in (("rider", 773, "android"), ("rider", 1452, "android"), ("driver", 772, "android"), ("rider", 772, "ios")):
        body = await _version(client, app, build, platform)
        assert body["state"] == "ok" and body["download_url"] is None, (app, build, platform)


async def test_seen_and_moved_are_counted_by_a_sealed_address(client: AsyncClient) -> None:
    """**من رأى ومن انتقل** — العنوانُ مختومٌ لا صريح، والانتقالُ سؤالُ العنوان نفسِه بغلافٍ من Play بعد الرسالة."""
    redis = get_redis_client()
    for key in (releases_service.OLD_KEY_SEEN, releases_service.OLD_KEY_MOVED, releases_service.OLD_KEY_ASKS):
        await redis.delete(key)

    await _version(client, "rider", 772, ip="198.51.100.7")
    await _version(client, "rider", 772, ip="198.51.100.7")
    await _version(client, "rider", 772, ip="203.0.113.9")
    # **غلافُ Play من عنوانٍ لم يرَ الرسالة لا يُعدّ منتقلاً**
    await _version(client, "rider", 1452, ip="192.0.2.44")
    await _version(client, "rider", 1452, ip="198.51.100.7")

    assert await redis.hlen(releases_service.OLD_KEY_SEEN) == 2
    assert int(await redis.get(releases_service.OLD_KEY_ASKS)) == 3
    assert await redis.hlen(releases_service.OLD_KEY_MOVED) == 1
    stored = " ".join(await redis.hkeys(releases_service.OLD_KEY_SEEN))
    assert "198.51.100.7" not in stored and "203.0.113.9" not in stored
