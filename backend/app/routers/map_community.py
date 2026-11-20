"""**أبوابُ الخريطة المفتوحة للتطبيقين** (أمرُ المالك ٢٠٢٦-١١-١٨ السابع، المهمّتان ٢ و٣):
اقتراحُ مكان · بلاغُ طريق · البلاغاتُ المرئيّة · الازدحام · ومربّعاتُ الأماكن.

**المربّعاتُ بلا جلسة**: بياناتٌ مفتوحةٌ (ODbL وأخواتها) لا سرَّ فيها ولا تخصّ أحداً، **والمحرّكُ يطلبها بلا رأس دخول** — وتُخبَّأ يوماً
في الهاتف فلا يُطلب المربّعُ نفسُه مرّتين. **وما سواها بجلسة**، والسوقُ سوقُ المستخدم.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Path, Response

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, RedisDep
from app.core.exceptions import PermissionDenied
from app.models.enums import FeatureKey, UserRole
from app.schemas.map_community import (
    PlaceSuggestionIn,
    PlaceSuggestionOut,
    RoadReportAckOut,
    RoadReportIn,
    RoadReportOut,
    TrafficOut,
)
from app.services import map_community, map_names, settings_service, traffic

router = APIRouter(prefix="/map", tags=["map"])

TILE_LAYERS = ("places",)


def _report_out(row) -> RoadReportOut:
    return RoadReportOut(id=row.id, kind=row.kind, lat=row.lat, lng=row.lng, confirmations=row.confirmations, expires_at=row.expires_at)


@router.post("/suggestions", response_model=PlaceSuggestionOut, status_code=201)
async def suggest_place(payload: PlaceSuggestionIn, user: CurrentUser, session: DbSession) -> PlaceSuggestionOut:
    """**«أضف مكاناً» / «اقترح تصحيحاً»** — يصل قيدَ المراجعة، **ولا يظهر على الخريطة قبل موافقة المشرف**."""
    row = await map_community.suggest(
        session,
        user,
        kind=payload.kind,
        name_ar=payload.name_ar,
        name_en=payload.name_en,
        category=payload.category.value,
        lat=payload.lat,
        lng=payload.lng,
        current_name=payload.current_name,
        note=payload.note,
    )
    return PlaceSuggestionOut(id=row.id, status=row.status)


@router.post("/road-reports", response_model=RoadReportAckOut, status_code=201)
async def report_road(payload: RoadReportIn, user: CurrentUser, session: DbSession) -> RoadReportAckOut:
    """**لمسةٌ واحدةٌ من الكبتن**: صيانة · طريق مغلق · حادث · ازدحام — بلاغٌ جديدٌ أو تأكيدٌ لما بلّغ به غيرُه هناك."""
    if not user.has_role(UserRole.DRIVER):
        raise PermissionDenied("البلاغُ للكباتن")
    result = await map_community.report(session, user, kind=payload.kind, lat=payload.lat, lng=payload.lng)
    row = result.report
    return RoadReportAckOut(
        **_report_out(row).model_dump(),
        created=result.created,
        counted=result.counted,
        visible=row.approved or row.confirmations >= map_community.SHOW_AT,
    )


@router.get("/road-reports", response_model=list[RoadReportOut])
async def road_reports(user: CurrentUser, session: DbSession) -> list[RoadReportOut]:
    """**ما يُرسم**: مؤكَّدٌ أو موافَقٌ عليه، لم ينتهِ — بلا اسم المبلِّغ. وفارغٌ والمفتاحُ مطفأ."""
    return [_report_out(row) for row in await map_community.visible_reports(session, user.country_code)]


@router.get("/traffic", response_model=TrafficOut)
async def live_traffic(user: CurrentUser, session: DbSession, redis: RedisDep) -> TrafficOut:
    """**الازدحامُ المجهول** — مقاطعُ مرّ بها ثلاثةُ كباتن مختلفون فأكثر، بلونٍ لا برقم. وفارغٌ والمفتاحُ مطفأ أو الكباتنُ قليلون."""
    if not await settings_service.is_feature_enabled(session, user.country_code, FeatureKey.MAP_LIVE_TRAFFIC):
        return TrafficOut(features=[])
    return TrafficOut(**await traffic.view(redis, user.country_code))


@router.get("/name-fixes", response_model=dict[str, str])
async def name_fixes(user: CurrentUser, session: DbSession) -> dict[str, str]:
    """**أسماءٌ عربيّةٌ كتبها المشرفُ لأماكن المربّعات** (SPEC §١٠٩-ب) — مفتاحُ المكان ⇐ اسمُه؛ يرسمها التطبيقان فوق اسم المربّع.
    **وفارغٌ والأماكنُ المفتوحةُ مطفأةٌ للسوق** — لا مربّعاتٍ فلا أسماءَ عليها."""
    if not await settings_service.is_feature_enabled(session, user.country_code, FeatureKey.MAP_OPEN_PLACES):
        return {}
    return await map_names.for_country(session, user.country_code)


@router.get("/tiles/{layer}/{z}/{x}/{y}.pbf", include_in_schema=False)
async def open_tile(
    layer: str = Path(pattern="^(places)$"),
    z: int = Path(ge=0, le=16),
    x: int = Path(ge=0),
    y: int = Path(ge=0),
) -> Response:
    """**مربّعُ الأماكن المفتوحة** من `places-search` (ملفُّ `mbtiles` على القرص) — مضغوطاً كما بُني، ومخبّأً يوماً."""
    base = settings.places_search_url.rstrip("/")
    if not base or layer not in TILE_LAYERS:
        return Response(status_code=204)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            upstream = await client.get(f"{base}/tiles/{layer}/{z}/{x}/{y}.pbf")
    except httpx.HTTPError:
        return Response(status_code=204, headers={"Cache-Control": "no-store"})
    if upstream.status_code != 200:
        return Response(status_code=204, headers={"Cache-Control": "public, max-age=3600"})
    headers = {"Cache-Control": "public, max-age=86400", "Content-Type": "application/x-protobuf"}
    if upstream.headers.get("x-tile-encoding") == "gzip":
        headers["Content-Encoding"] = "gzip"
    return Response(content=upstream.content, headers=headers)
