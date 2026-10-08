"""«المطار» عند الراكب (SPEC §٦٣-ج/٢) — **بابُ قراءةٍ واحد**: مطاراتُ سوقه ليختارها وجهة.

**ولمَ بابٌ لا كلمةٌ في البحث**: البحثُ في التطبيق يسأل Mapbox مباشرة، و«مطار» عنده يعيد **شارعَ المطار** قرب الراكب لا المطارَ
نفسَه (قِيس على S21 ٢٠٢٦-١٠-٠٨: «شارع مطار الملكة علياء» في ثلاثة أحياء). **والمرفقُ في قاعدتنا بمضلّعه** — فنقطتُه هي ما يُحسب
عليه الرسمُ نفسُه، **ولا تخمينَ لمكانه**. ومطفأُ المفتاح لا يُعرض فيه شيء: بلاطةٌ مطفأةٌ «قريباً» ولا بابَ إلى خدمةٍ لا تعمل.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import DbSession, RiderUser
from app.models.enums import FeatureKey
from app.schemas.facility import AirportOut
from app.services import facilities, settings_service

router = APIRouter(prefix="/airports", tags=["airports"])


@router.get("", response_model=list[AirportOut])
async def list_airports(rider: RiderUser, session: DbSession) -> list[AirportOut]:
    if not await settings_service.is_feature_enabled(session, rider.country_code, FeatureKey.AIRPORT_ENABLED):
        return []
    rows = await facilities.airports_for_rider(session, country=rider.country_code)
    return [AirportOut(id=row[0], name=row[1], lat=row[2], lng=row[3]) for row in rows]
