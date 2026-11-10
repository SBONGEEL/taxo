"""**نقطةُ التقاطٍ مقترحة** (البند ١١، SPEC §٩٧/١١) — قبل الطلب، **والراكبُ يقبل أو يُبقي دبّوسه**."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession, RedisDep
from app.schemas.map_place import PickupSuggestionOut
from app.services import pickup_spots

router = APIRouter(prefix="/pickup", tags=["pickup"])


@router.get("/suggestion", response_model=PickupSuggestionOut | None)
async def pickup_suggestion(
    user: CurrentUser,
    session: DbSession,
    redis: RedisDep,
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
) -> PickupSuggestionOut | None:
    """**أقربُ نقطةٍ سهلة** في سوق المستخدم، أو `null` حين لا أفضلَ من دبّوسه."""
    found = await pickup_spots.suggest(session, redis, user.country_code, lat, lng)
    if found is None:
        return None
    return PickupSuggestionOut(
        lat=found.lat,
        lng=found.lng,
        name_ar=found.name_ar,
        name_en=found.name_en,
        source=found.source,  # type: ignore[arg-type]
        distance_m=found.distance_m,
    )
