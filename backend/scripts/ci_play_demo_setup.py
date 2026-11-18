"""تهيئةُ قاعدة CI لفيديوهات إقرارات Play (أمرُ المالك ٢٠٢٦-١١-١٨ السادس، البند ٤).

**يعمل في قاعدة CI وحدَها ويرفض غيرَها** (`ENVIRONMENT=test`). يشعل في الأردن — بـ`set_flag` بابِ اللوحة — ما تصوّره الفيديوهات
وحدَه: فقاعةُ الحال وبطاقتُها، والموقعُ الأصليّ. **ولا شيءَ غيره**: الحسابُ من `provision_test_accounts`، والإعداداتُ من `seed`.
"""
from __future__ import annotations

import asyncio
import sys

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models.enums import CountryCode
from app.services import settings_service

KEYS = ("status_bubble", "native_location", "bubble_offer_card")


async def main() -> int:
    if get_settings().environment != "test":
        print("✗ يرفض: ليست قاعدةَ CI (ENVIRONMENT != test)", file=sys.stderr)
        return 1
    async with SessionLocal() as session:
        for key in KEYS:
            await settings_service.set_flag(
                session, country_code=CountryCode.JO, feature_key=key, enabled=True, reason="CI — فيديوهاتُ إقرارات Play"
            )
        await session.commit()
    print("✓ مشتعلةٌ في الأردن:", ", ".join(KEYS))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
