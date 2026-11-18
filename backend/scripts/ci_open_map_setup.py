"""تهيئةُ قاعدة CI لإثبات الخريطة المفتوحة على المحاكي (أمرُ المالك ٢٠٢٦-١١-١٨ الثالث، البند ١).

**يعمل في قاعدة CI وحدَها ويرفض غيرَها**: `ENVIRONMENT=test` شرطٌ قبل أيِّ صفّ — فلا يُشغَّل على الإنتاج ولو نُودي بالخطأ.
يكتب ثلاثةً لا غير:

١. **`open_map_display` مشتعلاً** في الأردن وليبيا — بـ`set_flag` البابِ نفسِه الذي تكتب به اللوحة.
٢. **صفَّي إصدارٍ للتطبيقين على أندرويد** برقم `1` — **وهو رقمُ بناء التصحيح أبداً** (`versionCodeOverride = 1` في
   `build.gradle`)، **و`open_map_min_build = 1`** كي يقيس المحاكي الغلافَ الذي يحمل الخريطة. **ويُكتبان بالنموذج لا
   بـ`releases.create`**: ذاك يطرق رابطَ التنزيل ويستأذن مرّتين، ولا رابطَ ولا مشرفَ في CI.
٣. **أربعُ حالاتِ المنتقي لصورها**: مصرُ «ظاهرة» برسالتها، والسعوديّةُ «قريباً»، وتونسُ «متوقفة»، والكويتُ «مخفية».
٤. لا شيءَ غيرها — الحسابان من `provision_test_accounts` (بابُهما الحقيقيّ)، والإعداداتُ من `seed`.
"""
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models.app_release import AppRelease
from app.models.enums import ClientApp, CountryCode, ReleasePlatform, SignupDisplay
from app.models.signup_country import SignupCountry
from app.services import settings_service

KEY = "open_map_display"


async def main() -> int:
    if get_settings().environment != "test":
        print("✗ يرفض: ليست قاعدةَ CI (ENVIRONMENT != test)", file=sys.stderr)
        return 1
    async with SessionLocal() as session:
        for cc in (CountryCode.JO, CountryCode.LY):
            await settings_service.set_flag(
                session, country_code=cc, feature_key=KEY, enabled=True, reason="CI — إثباتُ الخريطة المفتوحة"
            )
        for app in (ClientApp.RIDER, ClientApp.DRIVER):
            found = await session.scalar(
                select(AppRelease).where(
                    AppRelease.app == app, AppRelease.platform == ReleasePlatform.ANDROID, AppRelease.build == 1
                )
            )
            if found is None:
                session.add(
                    AppRelease(
                        app=app,
                        platform=ReleasePlatform.ANDROID,
                        build=1,
                        min_supported_build=1,
                        open_map_min_build=1,
                        download_url="https://taxo.tajora.ly/",
                        release_notes="CI",
                        reminder_hours=24,
                    )
                )
        states = {
            "EG": (SignupDisplay.VISIBLE, "TAXO سيبدأ قريباً في مصر. سنُعلمك فور الإطلاق."),
            "SA": (SignupDisplay.SOON, None),
            "TN": (SignupDisplay.STOPPED, None),
            "KW": (SignupDisplay.HIDDEN, None),
        }
        for code, (display, message) in states.items():
            row = await session.get(SignupCountry, code)
            if row is None:
                session.add(SignupCountry(code=code, display=display, visible_message=message))
            else:
                row.display, row.visible_message = display, message
        await session.commit()
    print("✓ المفتاحُ مشتعلٌ في JO وLY، وصفّا الإصدار برقم 1 وحدِّ الخريطة 1، وحالاتُ المنتقي الأربع")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
