"""**طابورُ مراجعة الخريطة في اللوحة** (أمرُ المالك ٢٠٢٦-١١-١٨ السابع): اقتراحاتُ الأماكن (توافَق فتصير مكاناً، أو تُرفض بسبب) وبلاغاتُ
الطريق (تُظهَر بلا انتظار التأكيد، أو تُزال). **بصلاحية الإعدادات** كأماكن المالك، **وكلُّ حكمٍ في سجلِّ التدقيق**.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.core.deps import DbSession, SettingsWriter, StaffUser
from app.models.enums import CountryCode
from app.schemas.map_community import (
    PlaceSuggestionAdminOut,
    RoadReportAdminOut,
    SuggestionApproveIn,
    SuggestionRejectIn,
)
from app.services import map_community

router = APIRouter(prefix="/admin/map", tags=["admin-map"])


def _suggestion_out(row) -> PlaceSuggestionAdminOut:
    return PlaceSuggestionAdminOut(
        id=row.id, country_code=str(row.country_code.value if hasattr(row.country_code, "value") else row.country_code),
        kind=row.kind, name_ar=row.name_ar, name_en=row.name_en, category=row.category, lat=row.lat, lng=row.lng,
        current_name=row.current_name, note=row.note, status=row.status, created_at=row.created_at,
        reviewed_at=row.reviewed_at, review_note=row.review_note, map_place_id=row.map_place_id,
    )


def _report_out(row) -> RoadReportAdminOut:
    return RoadReportAdminOut(
        id=row.id, kind=row.kind, lat=row.lat, lng=row.lng, confirmations=row.confirmations, expires_at=row.expires_at,
        country_code=str(row.country_code.value if hasattr(row.country_code, "value") else row.country_code),
        approved=row.approved, status=row.status, created_at=row.created_at,
    )


@router.get("/suggestions", response_model=list[PlaceSuggestionAdminOut])
async def list_suggestions(
    _staff: StaffUser,
    session: DbSession,
    status: str = Query(default="pending", pattern="^(pending|approved|rejected)$"),
    country: CountryCode | None = None,
) -> list[PlaceSuggestionAdminOut]:
    return [_suggestion_out(row) for row in await map_community.suggestions(session, status=status, country=country)]


@router.post("/suggestions/{suggestion_id}/approve", response_model=PlaceSuggestionAdminOut)
async def approve_suggestion(
    suggestion_id: uuid.UUID, payload: SuggestionApproveIn, admin: SettingsWriter, session: DbSession
) -> PlaceSuggestionAdminOut:
    row = await map_community.approve(
        session, suggestion_id, admin, name_ar=payload.name_ar, category=payload.category.value if payload.category else None
    )
    return _suggestion_out(row)


@router.post("/suggestions/{suggestion_id}/reject", response_model=PlaceSuggestionAdminOut)
async def reject_suggestion(
    suggestion_id: uuid.UUID, payload: SuggestionRejectIn, admin: SettingsWriter, session: DbSession
) -> PlaceSuggestionAdminOut:
    return _suggestion_out(await map_community.reject(session, suggestion_id, admin, reason=payload.reason))


@router.get("/road-reports", response_model=list[RoadReportAdminOut])
async def list_reports(_staff: StaffUser, session: DbSession, country: CountryCode | None = None) -> list[RoadReportAdminOut]:
    return [_report_out(row) for row in await map_community.admin_reports(session, country)]


@router.post("/road-reports/{report_id}/approve", response_model=RoadReportAdminOut)
async def approve_report(report_id: uuid.UUID, admin: SettingsWriter, session: DbSession) -> RoadReportAdminOut:
    return _report_out(await map_community.review_report(session, report_id, admin, action="approve"))


@router.post("/road-reports/{report_id}/remove", response_model=RoadReportAdminOut)
async def remove_report(report_id: uuid.UUID, admin: SettingsWriter, session: DbSession) -> RoadReportAdminOut:
    return _report_out(await map_community.review_report(session, report_id, admin, action="remove"))
