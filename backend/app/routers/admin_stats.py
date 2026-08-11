"""نظرة عامة على العمليات (SPEC القسم 13/1).

القراءة لـ staff: «نظرة عامة» تقرير حالٍ لا إجراء، ومن يعالج النزاعات يحتاج
أن يرى كم منها مفتوح. والكتابةُ لا وجود لها هنا أصلاً.

**والنافذة والدولة من الطلب، والحساب في الخدمة**: لا صفوفَ تُعاد لتُجمع في
اللوحة (القسم 14 يحصر الحساب في الخلفية، والعدُّ مثلُه).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Query

from app.core.deps import DbSession, RedisDep, StaffUser
from app.models.enums import CountryCode
from app.schemas.stats import OverviewOut
from app.services import stats as stats_service

router = APIRouter(prefix="/admin/stats", tags=["admin"])


@router.get("/overview", response_model=OverviewOut)
async def overview(
    _staff: StaffUser,
    session: DbSession,
    redis: RedisDep,
    country_code: CountryCode,
    period: Literal["today", "week", "month"] = Query(default="today"),
) -> OverviewOut:
    """أرقام الشاشة الأولى — بنافذةٍ من ثلاث وبدولةٍ إلزامية.

    الدولةُ إلزامية لأن اللوحة تدير سوقين ولا معنى لرقمٍ يجمعهما: «الرحلات
    المكتملة» عبر سوقين لا يقول شيئاً عن أيٍّ منهما.
    """
    result = await stats_service.overview(
        session,
        redis,
        country=country_code,
        period=period,
        now=datetime.now(UTC),
    )
    return OverviewOut(**asdict(result))
