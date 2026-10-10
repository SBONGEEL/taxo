"""لوحةُ فئات الرحلة (SPEC §٦٧-ب/١–٥) — **إضافةٌ وتعديلٌ وتشغيلٌ وإطفاءٌ وترتيب، وشروطُ المركبة، ومنحُ كبتنٍ أو نزعُها منه**.

**والأسعارُ في «التسعير» القائمة** (`/admin/settings/pricing`) بمفتاح الفئة — **ولا تُشعَل فئةٌ بلا أسعارٍ موجبة** (`categories.require_priced`).
**وكلُّ كتابةٍ قيدُ تدقيق** بما تغيّر. **والمفتاحُ والدولةُ لا يتغيّران بعد الإنشاء**: مكتوبان على الرحلات والأسعار.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.deps import DbSession, SettingsWriter, StaffUser
from app.core.exceptions import Conflict, InvalidInput, NotFound
from app.models.driver import Driver
from app.models.enums import AuditAction, CountryCode
from app.models.ride_category import DriverCategoryAccess, RideCategory
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.category import (
    CategoryAccessIn,
    CategoryAccessOut,
    RideCategoryCreate,
    RideCategoryOut,
    RideCategoryUpdate,
    VehicleAttributesIn,
)
from app.schemas.driver import VehicleOut
from app.services import audit, categories

router = APIRouter(prefix="/admin", tags=["admin"])


async def _category(session, category_id: uuid.UUID, *, lock: bool = False) -> RideCategory:
    stmt = select(RideCategory).where(RideCategory.id == category_id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    row = await session.scalar(stmt)
    if row is None:
        raise NotFound("لا فئةَ بهذا المعرّف")
    return row


def _plain(value):
    return [str(item) for item in value] if isinstance(value, list) else value


@router.get("/settings/ride-categories", response_model=list[RideCategoryOut])
async def list_categories(
    _staff: StaffUser, session: DbSession, country_code: CountryCode = Query(...)
) -> list[RideCategoryOut]:
    return [RideCategoryOut.model_validate(row) for row in await categories.for_country(session, country_code)]


@router.post("/settings/ride-categories", response_model=RideCategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(payload: RideCategoryCreate, admin: SettingsWriter, session: DbSession) -> RideCategoryOut:
    """**فئةٌ جديدةٌ تولد مطفأة** (§٦٧-ب/١٠) — وتُشعَل بعد أن توضع أسعارُها."""
    if categories.is_builtin(payload.key):
        raise InvalidInput("«اقتصادي» و«مريحة» مدمجتان — يُعدَّلان ولا يُنشآن")
    data = {key: _plain(value) for key, value in payload.model_dump().items()}
    row = RideCategory(**data, is_active=False, is_builtin=False)
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("في هذه الدولة فئةٌ بهذا المفتاح") from exc
    await audit.record(
        session, actor=admin, action=AuditAction.CREATE, entity_type="ride_category", entity_id=row.id,
        details={key: (value.value if hasattr(value, "value") else value) for key, value in data.items()},
    )
    await session.commit()
    await session.refresh(row)
    return RideCategoryOut.model_validate(row)


@router.patch("/settings/ride-categories/{category_id}", response_model=RideCategoryOut)
async def update_category(
    category_id: uuid.UUID, payload: RideCategoryUpdate, admin: SettingsWriter, session: DbSession
) -> RideCategoryOut:
    """**تعديلٌ جزئيّ** — وما غاب لا يُكتب. **وإشعالُ فئةٍ يشترط أسعاراً موجبة**، والإطفاءُ بلا شرط: يُخفيها من الطلبات الجديدة وحدَها."""
    changes_in = {key: _plain(value) for key, value in payload.model_dump(exclude_unset=True).items()}
    row = await _category(session, category_id, lock=True)
    if changes_in.get("is_active") is True and not row.is_active:
        await categories.require_priced(session, row.country_code, row.key)
    changed = audit.apply_changes(row, changes_in)
    if changed:
        await audit.record(
            session, actor=admin, action=AuditAction.UPDATE, entity_type="ride_category", entity_id=row.id,
            details={"country_code": row.country_code.value, "key": row.key}, changes=changed,
        )
    await session.commit()
    await session.refresh(row)
    return RideCategoryOut.model_validate(row)


@router.get("/settings/ride-categories/{category_id}/access", response_model=list[CategoryAccessOut])
async def list_access(category_id: uuid.UUID, _staff: StaffUser, session: DbSession) -> list[CategoryAccessOut]:
    """**من منحه المشرفُ هذه الفئةَ أو نزعها منه** — بأسمائهم."""
    await _category(session, category_id)
    rows = await session.execute(
        select(DriverCategoryAccess, User.name, User.phone)
        .join(Driver, Driver.id == DriverCategoryAccess.driver_id)
        .join(User, User.id == Driver.user_id)
        .where(DriverCategoryAccess.category_id == category_id)
        .order_by(DriverCategoryAccess.created_at)
    )
    return [
        CategoryAccessOut(driver_id=row.driver_id, driver_name=name, driver_phone=phone, granted=row.granted, reason=row.reason)
        for row, name, phone in rows.all()
    ]


@router.put("/settings/ride-categories/{category_id}/access", response_model=list[CategoryAccessOut])
async def set_access(
    category_id: uuid.UUID, payload: CategoryAccessIn, admin: SettingsWriter, session: DbSession
) -> list[CategoryAccessOut]:
    """**منحٌ أو نزعٌ أو رفعُهما** (§٦٧-ب/٥) — **بقفل صفِّ الكبتن** (ترتيبُ الأقفال في `CLAUDE.md`)، فمشرفان معاً على كبتنٍ واحدٍ يتركان صفّاً
    واحداً متّسقاً لا صفّين أو قراراً ضائعاً. **وللفئة الجديدة وحدَها**: المدمجتان تتبعان فئةَ المركبة."""
    category = await _category(session, category_id)
    if category.is_builtin:
        raise InvalidInput("«اقتصادي» و«مريحة» تتبعان فئةَ المركبة — لا تُمنحان ولا تُنزعان يدوياً")
    driver = await session.scalar(
        select(Driver).where(Driver.id == payload.driver_id).with_for_update().execution_options(populate_existing=True)
    )
    if driver is None:
        raise NotFound("لا كبتنَ بهذا المعرّف")
    existing = await session.scalar(
        select(DriverCategoryAccess).where(
            DriverCategoryAccess.driver_id == driver.id, DriverCategoryAccess.category_id == category.id
        )
    )
    before = None if existing is None else existing.granted
    if payload.granted is None:
        if existing is not None:
            await session.delete(existing)
    elif existing is None:
        session.add(
            DriverCategoryAccess(
                driver_id=driver.id, category_id=category.id, granted=payload.granted, actor_id=admin.id, reason=payload.reason
            )
        )
    else:
        existing.granted = payload.granted
        existing.actor_id = admin.id
        existing.reason = payload.reason
    if before != payload.granted:
        await audit.record(
            session, actor=admin, action=AuditAction.UPDATE, entity_type="driver_category_access", entity_id=driver.id,
            details={"category": category.key, "country_code": category.country_code.value, "reason": payload.reason},
            changes={"granted": {"before": before, "after": payload.granted}},
        )
    await session.commit()
    return await list_access(category_id, admin, session)


@router.patch("/drivers/{driver_id}/vehicles/{vehicle_id}/attributes", response_model=VehicleOut)
async def set_vehicle_attributes(
    driver_id: uuid.UUID, vehicle_id: uuid.UUID, payload: VehicleAttributesIn, admin: SettingsWriter, session: DbSession
) -> VehicleOut:
    """**صفاتُ المركبة في مراجعتها** (§٦٧-ج/٥) — الهيكلُ والوقودُ والمقاعد. **ليست من حقول الهويّة**: لا تُسقط اعتماداً ولا تمرّ بقفله؛
    **وتحكم الفئاتِ الجديدةَ وحدَها** — المدمجتان تتبعان فئةَ المركبة كما كانت."""
    vehicle = await session.scalar(select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.driver_id == driver_id))
    if vehicle is None:
        raise NotFound("لا مركبةَ بهذا المعرّف لهذا الكبتن")
    changed = audit.apply_changes(vehicle, {key: _plain(value) for key, value in payload.model_dump().items()})
    if changed:
        await audit.record(
            session, actor=admin, action=AuditAction.UPDATE, entity_type="vehicle_attributes", entity_id=vehicle.id,
            details={"driver_id": str(driver_id)}, changes=changed,
        )
    await session.commit()
    await session.refresh(vehicle)
    return VehicleOut.model_validate(vehicle)
