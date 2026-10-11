"""سوقُ النسخة من إعدادها لا من ثابتٍ أردنيّ (SPEC §٧٣-هـ المرحلة ٦) — **والأردنُ كما كان حرفاً**.

**ما يُقاس**: نسخةُ الأردن (`default_country_code=JO` — الافتراض) تقرأ الأردنَ في الثلاثة كما كانت؛ ونسخةٌ تُضبط `DZ` تقرأ الجزائرَ في
صفحة الموقع العامّة بلا دولةٍ في الطلب، وفي مِنطقة جدول النسخ.
"""

from __future__ import annotations

from httpx import AsyncClient

from app.core.config import settings
from app.models.enums import CountryCode
from app.services import backups, settings_service, site


def test_the_jordan_instance_reads_jordan_as_before() -> None:
    assert settings.default_country_code is CountryCode.JO
    assert site.SITE_COUNTRY is CountryCode.JO


async def test_the_public_landing_reads_the_instance_market_when_none_is_given(
    client: AsyncClient, monkeypatch
) -> None:
    asked: list[CountryCode] = []
    real = settings_service.is_feature_enabled

    async def spy(session, country, key):
        asked.append(country)
        return await real(session, country, key)

    monkeypatch.setattr(settings_service, "is_feature_enabled", spy)
    assert (await client.get("/public/landing")).status_code == 200
    assert asked[-1] is CountryCode.JO
    monkeypatch.setattr(settings, "default_country_code", CountryCode.DZ)
    assert (await client.get("/public/landing")).status_code == 200
    assert asked[-1] is CountryCode.DZ
    # **ودولةٌ صريحةٌ في الطلب تبقى كما كانت**
    assert (await client.get("/public/landing?country_code=LY")).status_code == 200
    assert asked[-1] is CountryCode.LY


async def test_the_backup_schedule_zone_is_the_instance_market(session_factory, monkeypatch) -> None:
    from app.services import stats

    asked: list[CountryCode] = []
    real = stats._zone

    async def spy(session, country):
        asked.append(country)
        return await real(session, country)

    monkeypatch.setattr(stats, "_zone", spy)
    async with session_factory() as session:
        await backups._zone(session)
        monkeypatch.setattr(settings, "default_country_code", CountryCode.DZ)
        await backups._zone(session)
    assert asked == [CountryCode.JO, CountryCode.DZ]
