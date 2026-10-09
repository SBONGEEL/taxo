"""**محوُ تسجيلات المكالمات في سوقٍ بعد تجربة** (SPEC §٧١-ب/٧) — بالخدمة نفسِها التي يحذف بها زرُّ اللوحة (`ride_calls.erase_recording`).

    python -m scripts.erase_recordings --country JO            # يعدّ ويطبع ولا يمسّ شيئاً
    python -m scripts.erase_recordings --country JO --apply    # يمحو ويطبع العدد

**لكلِّ تسجيلٍ سطرٌ في التدقيق بلا فاعل** (إنسانٌ شغّل سكربتاً بأمر المالك) وسببُه فيه، **والملفّاتُ تُمحى بعد الالتزام** كالكنس:
صفٌّ يشير إلى ملفٍّ ممحوٍّ عطل. **وسطرُ المكالمة يبقى** (من اتصل بمن ومتى) حتى يحلّ موعدُه كسائر سجلّ الرحلة.
**ويطبع العددَ مرّتين**: ما وُجد قبل، وما بقي بعد — **والثاني صفرٌ أو يقف**.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import func, select

from app.core import storage
from app.core.db import SessionLocal, engine
from app.models.enums import CountryCode
from app.models.ride import Ride
from app.models.ride_call import RideCall
from app.services import ride_calls

APPLY = "--apply" in sys.argv
REASON = "محوُ تسجيلات التجربة بأمر المالك — SPEC §71-ب/7"


def _country() -> CountryCode:
    if "--country" not in sys.argv:
        raise SystemExit("✗ --country مطلوب (JO أو LY) — لا محوَ في كلِّ الأسواق بخطأ إملاء")
    return CountryCode(sys.argv[sys.argv.index("--country") + 1])


def _recorded(country: CountryCode):
    return (
        select(RideCall.id)
        .join(Ride, Ride.id == RideCall.ride_id)
        .where(Ride.country_code == country, RideCall.recording_path.is_not(None))
    )


async def main() -> int:
    country = _country()
    async with SessionLocal() as session:
        ids = list((await session.scalars(_recorded(country))).all())
        print(f"  التسجيلاتُ القائمة في {country.value}: {len(ids)}")
        if not APPLY:
            print("· لم يُمسّ شيء — أعد بـ--apply")
            await engine.dispose()
            return 0
        files = [await ride_calls.erase_recording(session, call_id=call_id, actor=None, reason=REASON) for call_id in ids]
        await session.commit()
    for path in files:
        await storage.delete(path)
    async with SessionLocal() as session:
        left = await session.scalar(select(func.count()).select_from(_recorded(country).subquery()))
    print(f"✓ مُحي {len(files)} تسجيلاً (والملفّاتُ معها) · بقي {left}")
    await engine.dispose()
    return 0 if left == 0 else 1


sys.exit(asyncio.run(main()))
