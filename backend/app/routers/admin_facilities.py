"""صفحةُ «المرافق الحيوية» في اللوحة (SPEC §٦٣-ج/٢) — المطاراتُ وأمثالُها: الاسمُ والبلدُ والمنطقةُ على الخريطة والرسم.

**ولا حذف**: المرفقُ يُطفأ ولا يُمحى — رحلاتٌ قديمةٌ تشير إليه، وحذفُ صفٍّ يمسّ المال ممنوعٌ على الإنتاج. **وكلُّ كتابةٍ تُختم في
التدقيق** بما تغيّر قبلاً وبعداً، والمضلّعُ بعدد نقاطه لا بنقاطه.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.core.deps import DbSession, SettingsWriter, StaffUser
from app.models.enums import AuditAction, CountryCode
from app.models.facility import Facility
from app.schemas.facility import FacilityIn, FacilityOut, FacilityPatch
from app.services import audit, facilities

router = APIRouter(prefix="/admin/facilities", tags=["admin-facilities"])


async def _out(session, row: Facility) -> FacilityOut:
    return FacilityOut(
        id=row.id,
        country_code=row.country_code,
        kind=row.kind,
        name=row.name,
        area=await facilities.area_points(session, row),
        fee=row.fee,
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[FacilityOut])
async def list_facilities(
    _staff: StaffUser, session: DbSession, country: CountryCode | None = None
) -> list[FacilityOut]:
    """كلُّها **بما فيها المطفأة** — فالمشرفُ يرى ما أطفأه."""
    return [await _out(session, row) for row in await facilities.list_for(session, country=country)]


@router.post("", response_model=FacilityOut, status_code=201)
async def create_facility(
    payload: FacilityIn, admin: SettingsWriter, session: DbSession
) -> FacilityOut:
    row = await facilities.create(
        session,
        country_code=payload.country_code,
        name=payload.name,
        area=payload.area,
        fee=payload.fee,
        is_active=payload.is_active,
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="facility",
        entity_id=row.id,
        details={
            "country_code": row.country_code.value,
            "name": row.name,
            "fee": str(row.fee),
            "is_active": row.is_active,
            "area": f"{len(payload.area)} نقطة",
        },
    )
    await session.commit()
    await session.refresh(row)
    return await _out(session, row)


@router.patch("/{facility_id}", response_model=FacilityOut)
async def update_facility(
    facility_id: uuid.UUID, payload: FacilityPatch, admin: SettingsWriter, session: DbSession
) -> FacilityOut:
    row = await facilities.get(session, facility_id)
    changed = await facilities.update(
        session,
        row,
        name=payload.name,
        area=payload.area,
        fee=payload.fee,
        is_active=payload.is_active,
    )
    if changed:
        await audit.record(
            session,
            actor=admin,
            action=AuditAction.UPDATE,
            entity_type="facility",
            entity_id=row.id,
            details=changed,
        )
    await session.commit()
    await session.refresh(row)
    return await _out(session, row)
