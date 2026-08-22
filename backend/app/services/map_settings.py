"""قراءةُ إعدادات الخريطة — **بابٌ واحدٌ وغيابُ الصفِّ يعني الافتراض**.

**ولا يُنشئ صفّاً بالقراءة**: إنشاءٌ كسولٌ عند أول قراءةٍ يحتاج قفلاً، وبلا
قفلٍ يكتب طلبان صفّين — وهو الدرسُ الذي أنشأ ترحيلةَ `0039` بدل التوليدِ
الكسول لرموز الإحالة. فالصفُّ يُكتب من اللوحة أو من البذرة، والقراءةُ تُرجع
الافتراضَ حين لا يجده.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CountryCode
from app.models.map_setting import (
    DEFAULT_NEARBY_MAX_COUNT,
    DEFAULT_NEARBY_RADIUS_KM,
    MapSetting,
)


@dataclass(frozen=True, slots=True)
class MapLimits:
    radius_km: float
    max_count: int


async def limits_for(session: AsyncSession, country_code: CountryCode) -> MapLimits:
    row = await session.get(MapSetting, CountryCode(country_code))
    if row is None:
        return MapLimits(
            radius_km=float(DEFAULT_NEARBY_RADIUS_KM),
            max_count=DEFAULT_NEARBY_MAX_COUNT,
        )
    return MapLimits(
        radius_km=float(row.nearby_radius_km), max_count=int(row.nearby_max_count)
    )
