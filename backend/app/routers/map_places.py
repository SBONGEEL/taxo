"""**أماكنُ الخريطة للتطبيقين** (SPEC §٧١-د) — ما يُرسم فوق أسماء المزوّد، وما يتقدّم البحث. **لكلِّ مستخدمٍ بجلسة**، والسوقُ سوقُه.

**ولا سرَّ هنا**: اسمٌ وفئةٌ وموقعٌ لمكانٍ عامّ. **والمفتاحُ مطفأً ⇒ قائمتان فارغتان** (`services/map_places.visible`).
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.schemas.map_place import MapPlaceOut
from app.services import map_places

router = APIRouter(prefix="/map-places", tags=["map-places"])


def _out(spot: map_places.Spot, distance: int | None = None) -> MapPlaceOut:
    return MapPlaceOut(
        id=spot.id,
        name_ar=spot.name_ar,
        name_en=spot.name_en,
        category=spot.category,
        lat=spot.lat,
        lng=spot.lng,
        source=spot.source,  # type: ignore[arg-type]
        distance_m=distance,
    )


@router.get("", response_model=list[MapPlaceOut])
async def places_on_map(user: CurrentUser, session: DbSession) -> list[MapPlaceOut]:
    """**ما يرسمه التطبيقُ فوق خريطته** — أماكنُ سوق المستخدم ومطاراتُه."""
    return [_out(spot) for spot in await map_places.visible(session, user.country_code, for_map=True)]


@router.get("/search", response_model=list[MapPlaceOut])
async def search_places(
    user: CurrentUser,
    session: DbSession,
    q: str = Query(min_length=1, max_length=80),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
) -> list[MapPlaceOut]:
    """**رأسُ نتائج البحث** — ما طابق من أماكن السوق، الأقربُ أوّلاً. ونتائجُ المزوّد تُضاف تحتها في التطبيق."""
    near = (lat, lng) if lat is not None and lng is not None else None
    return [_out(spot, distance) for spot, distance in await map_places.search(session, user.country_code, q, near)]
