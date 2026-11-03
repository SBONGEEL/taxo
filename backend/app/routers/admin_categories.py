"""لوحةُ فئات الرحلة (SPEC §٦٧-ب/١–٥) — **إضافةٌ وتعديلٌ وتشغيلٌ وإطفاءٌ وترتيب، وشروطُ المركبة، ومنحُ كبتنٍ أو نزعُها منه**،
**وفئةُ المركبة يعيّنها المشرف** (§٩١-ب/٥): اقتراحٌ من الطراز والسنة، وتأكيد، وقائمةُ «بحاجة لمراجعة الفئة».

**والأسعارُ في «التسعير» القائمة** (`/admin/settings/pricing`) بمفتاح الفئة — **ولا تُشعَل فئةٌ بلا أسعارٍ موجبة** (`categories.require_priced`).
**وكلُّ كتابةٍ قيدُ تدقيق** بما تغيّر. **والمفتاحُ والدولةُ لا يتغيّران بعد الإنشاء**: مكتوبان على الرحلات والأسعار.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

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
    CategoryReviewOut,
    CategorySuggestionOut,
    RideCategoryCreate,
    RideCategoryOut,
    RideCategoryUpdate,
    VehicleAttributesIn,
    VehicleCategoryIn,
)
from app.schemas.driver import VehicleOut
from app.services import audit, categories
from app.services import drivers as drivers_service

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


async def _driver_vehicle(session, driver_id: uuid.UUID, vehicle_id: uuid.UUID) -> tuple[Vehicle, CountryCode]:
    row = (
        await session.execute(
            select(Vehicle, User.country_code)
            .join(Driver, Driver.id == Vehicle.driver_id)
            .join(User, User.id == Driver.user_id)
            .where(Vehicle.id == vehicle_id, Vehicle.driver_id == driver_id)
            .execution_options(populate_existing=True)
        )
    ).first()
    if row is None:
        raise NotFound("لا مركبةَ بهذا المعرّف لهذا الكبتن")
    return row[0], row[1]


@router.get("/drivers/{driver_id}/vehicles/{vehicle_id}/category-suggestion", response_model=CategorySuggestionOut)
async def category_suggestion(
    driver_id: uuid.UUID, vehicle_id: uuid.UUID, _staff: StaffUser, session: DbSession
) -> CategorySuggestionOut:
    """**الفئةُ المقترحة** (§٩١-ب/٥) — اقتراحٌ يؤكّده المشرف، ومعه علّتُه."""
    vehicle, country = await _driver_vehicle(session, driver_id, vehicle_id)
    suggested, reason = await categories.suggest(session, country, vehicle)
    return CategorySuggestionOut(suggested=suggested, reason=reason)


@router.put("/drivers/{driver_id}/vehicles/{vehicle_id}/category", response_model=VehicleOut)
async def set_vehicle_category(
    driver_id: uuid.UUID, vehicle_id: uuid.UUID, payload: VehicleCategoryIn, admin: SettingsWriter, session: DbSession
) -> VehicleOut:
    """**المشرفُ يعيّن فئةَ المركبة ويؤكّدها** (§٩١-ب/٥) — والتأكيدُ نفسُه يُكتب ولو لم تتغيّر الفئة (يُخرجها من قائمة المراجعة).

    **بقفل صفِّ الكبتن قبل قراءة المركبة** (ترتيبُ الأقفال في `CLAUDE.md`): تعديلُ الكبتن طرازَه يأخذ القفلَ نفسَه ويُفرغ التأكيد —
    فلا يُكتب تأكيدٌ على طرازٍ لم يره المشرف بعد أن أُفرغ. **ويسري على التوزيع من اتصال الكبتن التالي**: فئةُ الحضور تُقرأ مرّةً لكلِّ اتصال.
    """
    driver = await session.scalar(select(Driver).where(Driver.id == driver_id))
    if driver is None:
        raise NotFound("لا كبتنَ بهذا المعرّف")
    await drivers_service.lock(session, driver)
    vehicle, _country = await _driver_vehicle(session, driver_id, vehicle_id)
    before = {"category": vehicle.category, "confirmed": vehicle.category_confirmed_at is not None}
    vehicle.category = payload.category.value
    vehicle.category_confirmed_at = datetime.now(UTC)
    vehicle.category_confirmed_by = admin.id
    await audit.record(
        session, actor=admin, action=AuditAction.UPDATE, entity_type="vehicle_category", entity_id=vehicle.id,
        details={"driver_id": str(driver_id), "reason": payload.reason},
        changes={
            "category": {"before": before["category"], "after": payload.category.value},
            "confirmed": {"before": before["confirmed"], "after": True},
        },
    )
    await session.commit()
    await session.refresh(vehicle)
    return VehicleOut.model_validate(vehicle)


@router.get("/vehicles/category-review", response_model=list[CategoryReviewOut])
async def category_review(
    _staff: StaffUser, session: DbSession, country_code: CountryCode = Query(...)
) -> list[CategoryReviewOut]:
    """**«بحاجة لمراجعة الفئة»** (§٩١-ب/٥) — كلُّ مركبةٍ فئتُها مؤقّتة: القائمةُ يومَ الترحيلة، والجديدةُ، ومن غيّر طرازَه أو سنتَه.
    **وفئتُها تعمل كما هي حتى يؤكّدها مشرف** — فلا يفقد كبتنٌ عملَه بالانتظار."""
    rows = await session.execute(
        select(Vehicle, Driver.status, User.name, User.phone)
        .join(Driver, Driver.id == Vehicle.driver_id)
        .join(User, User.id == Driver.user_id)
        .where(User.country_code == country_code, Vehicle.category_confirmed_at.is_(None))
        .order_by(Vehicle.created_at)
    )
    out: list[CategoryReviewOut] = []
    for vehicle, driver_status, name, phone in rows.all():
        suggested, reason = await categories.suggest(session, country_code, vehicle)
        out.append(
            CategoryReviewOut(
                driver_id=vehicle.driver_id, driver_name=name, driver_phone=phone, driver_status=driver_status,
                vehicle_id=vehicle.id, make=vehicle.make, model=vehicle.model, year=vehicle.year,
                plate_number=vehicle.plate_number, category=vehicle.category, suggested=suggested, reason=reason,
            )
        )
    return out
