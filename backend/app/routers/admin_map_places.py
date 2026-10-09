"""صفحةُ «الأماكن» في اللوحة (SPEC §٧١-د/١٤) — إضافةٌ وتعديلٌ وإخفاء: اسمٌ عربيٌّ وإنجليزيّ، وفئة، وموقع، ودولة.

**ولا حذف**: الإخفاءُ هو الإيقاف — كالمرافق. **وكلُّ كتابةٍ تُختم في التدقيق** بما تغيّر قبلاً وبعداً (`audit.apply_changes`).
**والصلاحيةُ صلاحيةُ الإعدادات** كالمرافق جارتِها: ما يُرسم على خريطة كلِّ راكبٍ وكبتنٍ إعدادٌ عامّ.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.core.deps import DbSession, SettingsWriter, StaffUser
from app.models.enums import AuditAction, CountryCode
from app.models.map_place import MapPlace
from app.schemas.map_place import MapPlaceAdminOut, MapPlaceIn, MapPlacePatch
from app.services import audit, map_places

router = APIRouter(prefix="/admin/map-places", tags=["admin-map-places"])


def _out(row: MapPlace) -> MapPlaceAdminOut:
    return MapPlaceAdminOut(
        id=row.id,
        country_code=row.country_code,
        name_ar=row.name_ar,
        name_en=row.name_en,
        category=row.category,
        lat=row.lat,
        lng=row.lng,
        is_hidden=row.is_hidden,
        source=row.source,
        osm_ref=row.osm_ref,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[MapPlaceAdminOut])
async def list_places(
    _staff: StaffUser, session: DbSession, country: CountryCode | None = None
) -> list[MapPlaceAdminOut]:
    return [_out(row) for row in await map_places.list_for_panel(session, country)]


@router.post("", response_model=MapPlaceAdminOut, status_code=201)
async def create_place(payload: MapPlaceIn, admin: SettingsWriter, session: DbSession) -> MapPlaceAdminOut:
    row = MapPlace(**payload.model_dump())
    session.add(row)
    await session.flush()
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="map_place",
        entity_id=row.id,
        details={
            "country_code": row.country_code.value,
            "name_ar": row.name_ar,
            "name_en": row.name_en,
            "category": row.category,
            "lat": row.lat,
            "lng": row.lng,
            "is_hidden": row.is_hidden,
        },
    )
    await session.commit()
    await session.refresh(row)
    return _out(row)


@router.patch("/{place_id}", response_model=MapPlaceAdminOut)
async def update_place(
    place_id: uuid.UUID, payload: MapPlacePatch, admin: SettingsWriter, session: DbSession
) -> MapPlaceAdminOut:
    row = await map_places.get(session, place_id)
    sent = payload.model_dump(exclude_unset=True)
    map_places.require_name(sent)
    changes = audit.apply_changes(row, sent)
    if changes:
        await audit.record(
            session,
            actor=admin,
            action=AuditAction.UPDATE,
            entity_type="map_place",
            entity_id=row.id,
            changes=changes,
        )
    await session.commit()
    await session.refresh(row)
    return _out(row)
