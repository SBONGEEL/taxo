"""**خريطةُ الطلب في اللوحة** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٨) — العددُ و«غيرُ المخدوم» لكلِّ خلية."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.deps import DbSession, StaffUser
from app.models.enums import CountryCode
from app.services import heatmap

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminHeatCell(BaseModel):
    lat: float
    lng: float
    requests: int
    #: ما انتهى «لم يُعثر على كبتن» أو يبحث منذ أكثر من ثلاث دقائق — **المناطقُ غيرُ المغطّاة**
    unserved: int


@router.get("/heatmap", response_model=list[AdminHeatCell])
async def admin_heatmap(
    session: DbSession,
    _: StaffUser,
    country_code: CountryCode,
    minutes: int = Query(default=heatmap.WINDOW_MINUTES, ge=15, le=180),
) -> list[AdminHeatCell]:
    found = await heatmap.cells(session, country=country_code, now=datetime.now(UTC), minutes=minutes)
    return [AdminHeatCell(lat=c.lat, lng=c.lng, requests=c.requests, unserved=c.unserved) for c in found]
