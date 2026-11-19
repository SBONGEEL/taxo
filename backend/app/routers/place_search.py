"""**البحثُ الموحَّد والعنوانُ العكسيُّ عبر الخلفية** (قرارُ المالك ٢٠٢٦-١١-١٥) — مفتاحُ Google السرّيُّ لا يغادر الخادم، والسقوفُ
والرجوعُ إلى Mapbox هنا لا في كلِّ تطبيق. **ولكلِّ مستخدمٍ بجلسة**، والبلدُ بلدُه.
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import InvalidInput, NotFound
from app.models.enums import RideStatus
from app.models.ride import Ride
from app.services import google_maps, learned_places, maps

router = APIRouter(prefix="/places", tags=["places"])


class PlaceResultOut(BaseModel):
    id: str
    source: Literal["saved", "recent", "taxo", "learned", "google", "open", "mapbox"]
    name: str
    address: str = ""
    lat: float | None = None
    lng: float | None = None
    place_id: str | None = None
    distance_m: int | None = None
    #: **صنفُ الأيقونة** (§١٠٤/١١): airport · mall · hospital · university · mosque · restaurant · hotel · school · pharmacy · bank ·
    #: fuel · park · roundabout · street · city · district · place · saved · recent — و`null` أيقونةٌ عامّة. **نصٌّ لا تعداد**:
    #: الخدمةُ المفتوحة تملك قائمتَها، وصنفٌ جديدٌ فيها يصل أيقونةً عامّةً لا خطأَ تحقّق
    category: str | None = None


class PlaceSearchOut(BaseModel):
    items: list[PlaceResultOut]
    #: «google» ⇐ يُعرض «Powered by Google» تحت القائمة؛ «open» ⇐ `attribution_text` (شرطُ ODbL)؛ «mapbox» ⇐ نسبةُ Mapbox
    attribution: Literal["google", "open", "mapbox"] | None
    attribution_text: str | None = None


class ResolvedOut(BaseModel):
    place_id: str
    address: str
    lat: float
    lng: float


class ReverseOut(BaseModel):
    address: str | None
    provider: Literal["google", "mapbox", "open"]


class MapsProvidersOut(BaseModel):
    display: Literal["google", "mapbox"]
    search: Literal["google", "mapbox"]
    routes: Literal["google", "mapbox"]


class MapsHealthIn(BaseModel):
    feature: Literal["display"]
    reason: str = Field(default="", max_length=80)


class LearnIn(BaseModel):
    ride_id: uuid.UUID
    #: **ما كتبه الراكبُ في البحث** — نصُّه هو، لا اسمُ المزوّد
    label: str = Field(min_length=2, max_length=80)


def place_search_out(answer: maps.SearchAnswer) -> PlaceSearchOut:
    """**بانٍ واحدٌ لجواب البحث** — يستعمله بابُ الراكب (`/places/search`) وبابُ اللوحة (`/admin/map-places/search`) معاً،
    فنسبةُ ODbL (`attribution_text`) لا تُملأ في بابٍ وتُنسى في الآخر (الشكلُ الثامن، `test_two_doors`)."""
    return PlaceSearchOut(
        items=[
            PlaceResultOut(
                id=r.id, source=r.source, name=r.name, address=r.address, lat=r.lat, lng=r.lng,  # type: ignore[arg-type]
                place_id=r.place_id, distance_m=r.distance_m, category=r.category,
            )
            for r in answer.items
        ],
        attribution=answer.attribution,  # type: ignore[arg-type]
        attribution_text=maps.OPEN_ATTRIBUTION if answer.attribution == "open" else None,
    )


@router.get("/search", response_model=PlaceSearchOut)
async def search(
    user: CurrentUser,
    session: DbSession,
    q: str = Query(min_length=1, max_length=80),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    session_token: str | None = Query(default=None, max_length=64),
) -> PlaceSearchOut:
    near = (lat, lng) if lat is not None and lng is not None else None
    answer = await maps.search(
        session, user_id=user.id, country=user.country_code, query=q, near=near, session_token=session_token
    )
    return place_search_out(answer)


@router.get("/resolve", response_model=ResolvedOut)
async def resolve(
    user: CurrentUser,
    session: DbSession,
    place_id: str = Query(min_length=4, max_length=300),
    session_token: str | None = Query(default=None, max_length=64),
) -> ResolvedOut:
    """**موقعُ اقتراح Google المختار** — وإن تعذّر الآن: 404 بنصّ، والتطبيقُ يطلب من المستخدم أن يختار على الخريطة."""
    try:
        point = await maps.resolve(session, user.country_code, place_id, session_token)
    except google_maps.GoogleFailed as exc:
        raise NotFound("تعذّر تحديدُ هذا المكان الآن — اختره على الخريطة") from exc
    return ResolvedOut(place_id=point.place_id, address=point.address, lat=point.lat, lng=point.lng)


@router.get("/reverse", response_model=ReverseOut)
async def reverse(
    user: CurrentUser,
    session: DbSession,
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
) -> ReverseOut:
    address, provider = await maps.reverse(session, user.country_code, lat, lng)
    return ReverseOut(address=address, provider=provider)  # type: ignore[arg-type]


@router.get("/providers", response_model=MapsProvidersOut)
async def providers(user: CurrentUser, session: DbSession) -> MapsProvidersOut:
    """**مزوّدُ كلِّ ميزةٍ الآن في بلد المستخدم** — بعد المفاتيح والعقد والصحّة؛ فتطبيقٌ يقرؤه يرسم ما ستعمل به الخلفيّة."""
    return MapsProvidersOut(
        display=await maps.provider_for(session, user.country_code, "display"),  # type: ignore[arg-type]
        search=await maps.provider_for(session, user.country_code, "search"),  # type: ignore[arg-type]
        routes=await maps.provider_for(session, user.country_code, "routes"),  # type: ignore[arg-type]
    )


@router.post("/health", status_code=204)
async def report_display_failure(body: MapsHealthIn, user: CurrentUser) -> None:
    """**التطبيقُ لم يستطع رسمَ خريطة Google** فرسم Mapbox — يُعلَّم Google متوقّفاً للعرض ويُشعَر المالكُ مرّة."""
    await maps.note(body.feature, up=False, reason=body.reason or "تعذّر رسمُ الخريطة", country=user.country_code)


@router.post("/learn", status_code=204)
async def learn(body: LearnIn, user: CurrentUser, session: DbSession) -> None:
    """**رحلةٌ مكتملةٌ للراكب نفسِه** — يُتعلَّم ما كتبه **بموقع نهاية الرحلة من سجلّها** لا بما يرسله التطبيق."""
    ride = await session.scalar(select(Ride).where(Ride.id == body.ride_id, Ride.rider_id == user.id))
    if ride is None:
        raise NotFound("الرحلةُ غيرُ موجودة")
    if ride.status is not RideStatus.COMPLETED:
        raise InvalidInput("الرحلةُ لم تكتمل")
    await learned_places.learn(session, ride.country_code, body.label, ride.dropoff_lat, ride.dropoff_lng)
    await session.commit()
