"""**دقّةُ وقت الوصول في اللوحة** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٢) — المتوقَّعُ مقابل الفعليّ."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.deps import DbSession, StaffUser
from app.models.enums import CountryCode
from app.services import eta_accuracy

router = APIRouter(prefix="/admin/eta", tags=["admin"])


class HourAccuracyOut(BaseModel):
    hour: int
    samples: int
    mean_abs_error_min: float


class EtaAccuracyOut(BaseModel):
    samples: int
    #: متوسّطُ الخطأ بالدقائق فيما عُرض (بعد التصحيح)
    mean_abs_error_min: float | None
    within_two_min_percent: int | None
    #: موجبٌ = يصل الكبتنُ متأخّراً عمّا قيل
    bias_min: float | None
    #: متوسّطُ الخطأ لو عُرض ما قاله المزوّدُ بلا تصحيح — به يُقرأ أثرُ التصحيح
    raw_mean_abs_error_min: float | None
    by_hour: list[HourAccuracyOut]


@router.get("/accuracy", response_model=EtaAccuracyOut)
async def eta_accuracy_summary(
    session: DbSession, _: StaffUser, country_code: CountryCode, days: int = Query(default=28, ge=1, le=90)
) -> EtaAccuracyOut:
    found = await eta_accuracy.summary(session, country=country_code, days=days)
    return EtaAccuracyOut(
        samples=found.samples,
        mean_abs_error_min=found.mean_abs_error_min,
        within_two_min_percent=found.within_two_min_percent,
        bias_min=found.bias_min,
        raw_mean_abs_error_min=found.raw_mean_abs_error_min,
        by_hour=[HourAccuracyOut(hour=h.hour, samples=h.samples, mean_abs_error_min=h.mean_abs_error_min) for h in found.by_hour],
    )
