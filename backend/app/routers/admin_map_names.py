"""صفحةُ «أماكن بلا اسم عربي» في اللوحة (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-ب) — القائمةُ لكلِّ دولةٍ ومدينة، والمشرفُ يكتب الاسم.

**وكلُّ كتابةٍ تُختم في التدقيق** بالاسم قبلاً وبعداً. **والصلاحيةُ صلاحيةُ الإعدادات** كجارتها «الأماكن»: ما يُرسم على خريطة كلِّ
راكبٍ وكبتنٍ إعدادٌ عامّ.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field

from app.core.deps import DbSession, SettingsWriter, StaffUser
from app.core.exceptions import PlacesServiceUnavailable
from app.models.enums import AuditAction, CountryCode
from app.models.map_name_fix import MapNameFix
from app.services import audit, map_names

router = APIRouter(prefix="/admin/map-names", tags=["admin-map-names"])


class MissingPlaceOut(BaseModel):
    okey: str
    city: str
    name: str
    tag: str
    #: فئةُ المكان (`hospital`، `clinic`…) — `None` من خدمةٍ أقدم
    cat: str | None = None
    lat: float
    lng: float


class MissingCityOut(BaseModel):
    city: str
    count: int


class MissingCatOut(BaseModel):
    cat: str
    count: int


class MissingPageOut(BaseModel):
    #: `false` ⇐ فهرسُ الخادم أقدمُ من القائمة — تظهر بعد رفع بناء الخريطة القادم
    built: bool
    cities: list[MissingCityOut]
    #: **أعدادُ الفئات بترتيب الأهمّيّة** (أمرُ المالك ٢٠٢٦-١١-٢٠ الثاني، البند ٤) — داخل المدينة المختارة
    cats: list[MissingCatOut] = []
    total: int
    items: list[MissingPlaceOut]


class NameFixIn(BaseModel):
    country_code: CountryCode
    name_ar: str = Field(min_length=1, max_length=200)
    original_name: str = Field(default="", max_length=200)
    city: str = Field(default="", max_length=200)


class NameFixOut(BaseModel):
    okey: str
    country_code: CountryCode
    name_ar: str
    original_name: str
    city: str
    updated_at: datetime


def _out(row: MapNameFix) -> NameFixOut:
    return NameFixOut(
        okey=row.okey, country_code=row.country_code, name_ar=row.name_ar, original_name=row.original_name,
        city=row.city, updated_at=row.updated_at,
    )


@router.get("/missing", response_model=MissingPageOut)
async def missing_places(
    _staff: StaffUser,
    session: DbSession,
    country: CountryCode,
    city: str = Query(default="", max_length=120),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    cat: str = Query(default="", max_length=40),
) -> MissingPageOut:
    page = await map_names.missing(session, country, city, offset, limit, cat)
    if page is None:
        raise PlacesServiceUnavailable()
    return MissingPageOut(
        built=page.built,
        cities=[MissingCityOut(city=str(c.get("city") or "—"), count=int(c.get("count") or 0)) for c in page.cities],
        cats=[MissingCatOut(cat=str(c.get("cat") or "place"), count=int(c.get("count") or 0)) for c in page.cats],
        total=page.total,
        items=[MissingPlaceOut(**{key: item[key] for key in MissingPlaceOut.model_fields if key in item}) for item in page.items],
    )


@router.get("/fixes", response_model=list[NameFixOut])
async def list_fixes(_staff: StaffUser, session: DbSession, country: CountryCode) -> list[NameFixOut]:
    return [_out(row) for row in await map_names.fixes(session, country)]


@router.put("/{okey}", response_model=NameFixOut)
async def put_fix(okey: str, payload: NameFixIn, admin: SettingsWriter, session: DbSession) -> NameFixOut:
    row, previous = await map_names.put(
        session, okey=okey, country=payload.country_code, name_ar=payload.name_ar,
        original_name=payload.original_name, city=payload.city, actor_id=admin.id,
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE if previous is None else AuditAction.UPDATE,
        entity_type="map_name_fix",
        details={
            "okey": row.okey,
            "country_code": row.country_code.value,
            "original_name": row.original_name,
            "name_ar": {"before": previous, "after": row.name_ar},
        },
    )
    await session.commit()
    await session.refresh(row)
    return _out(row)


@router.delete("/{okey}", status_code=204)
async def delete_fix(okey: str, admin: SettingsWriter, session: DbSession) -> Response:
    row = await map_names.remove(session, okey)
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.DELETE,
        entity_type="map_name_fix",
        details={"okey": row.okey, "country_code": row.country_code.value, "name_ar": {"before": row.name_ar, "after": None}},
    )
    await session.commit()
    return Response(status_code=204)
