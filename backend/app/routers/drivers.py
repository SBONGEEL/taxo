from __future__ import annotations

import secrets
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, File, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core import rate_limit, storage
from app.core.config import settings
from app.core.deps import CurrentDriver, CurrentUser, DbSession, RedisDep, RiderUser
from app.core.exceptions import Conflict, RateLimited
from app.models.user import User
from app.models.driver import DriverDocument
from app.models.enums import DocumentType
from app.models.vehicle import Vehicle
from app.schemas.auth import UserOut
from app.schemas.driver import (
    AdvanceDebtOut,
    AdvanceOut,
    AdvanceRequestIn,
    AdvanceRequirementOut,
    AdvanceStateOut,
    DeactivationDecisionIn,
    DeactivationRequestIn,
    DeactivationRequestOut,
    DeactivationStateOut,
    DocumentUploadOut,
    DriverDocumentOut,
    DriverDocumentsOut,
    DriverLocationIn,
    DriverOut,
    DriverProfileOut,
    DriverUpdate,
    NearbyDriverOut,
    VehicleCreate,
    VehicleOut,
    VehicleUpdate,
    VehicleUpdateResultOut,
)
from app.schemas.wallet import EarningsOut
from app.core.currency import currency_for_country
from app.services import (
    advances as advances_service,
    notifications,
    deactivation,
    documents as documents_service,
    drivers as drivers_service,
    earnings as earnings_service,
    settings_service,
    vehicles as vehicles_service,
)

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.get("/me", response_model=DriverProfileOut)
async def get_my_driver_profile(
    driver: CurrentDriver, user: CurrentUser, session: DbSession
) -> DriverProfileOut:
    vehicles = (
        await session.scalars(
            select(Vehicle).where(Vehicle.driver_id == driver.id).order_by(Vehicle.created_at)
        )
    ).all()
    documents = (
        await session.scalars(
            select(DriverDocument)
            .where(DriverDocument.driver_id == driver.id)
            .order_by(DriverDocument.created_at)
        )
    ).all()

    return DriverProfileOut(
        driver=DriverOut.model_validate(driver),
        user=UserOut.model_validate(user),
        vehicles=[VehicleOut.model_validate(v) for v in vehicles],
        documents=[DriverDocumentOut.model_validate(d) for d in documents],
    )


@router.patch("/me", response_model=DriverOut)
async def update_my_driver_profile(
    payload: DriverUpdate, driver: CurrentDriver, session: DbSession
) -> DriverOut:
    """تعديل ما يملكه الكبتن من ملفه: `cliq_alias` وتفضيلُ الركاب والتجديد.

    يُكتب في التسجيل (الخطوة الثالثة) ويُعدَّل من الإعدادات. ولا يمسّ
    الاعتماد: alias خاطئ يعطّل سحباً واحداً ويُصحَّح، ولا علاقة له بمن يحق
    له استقبال الطلبات.
    """
    if payload.cliq_alias is not None:
        alias = payload.cliq_alias.strip()
        driver.cliq_alias = alias or None
    if payload.gender_preference is not None:
        # تفضيلُه لا جنسُه: الأول يملكه، والثاني يضبطه المشرف من هويته
        driver.gender_preference = payload.gender_preference
    if payload.auto_renew is not None:
        driver.auto_renew = payload.auto_renew

    await session.commit()
    await session.refresh(driver)
    return DriverOut.model_validate(driver)


@router.get("/me/vehicles", response_model=list[VehicleOut])
async def list_my_vehicles(driver: CurrentDriver, session: DbSession) -> list[VehicleOut]:
    vehicles = (
        await session.scalars(
            select(Vehicle).where(Vehicle.driver_id == driver.id).order_by(Vehicle.created_at)
        )
    ).all()
    return [VehicleOut.model_validate(v) for v in vehicles]


@router.post(
    "/me/vehicles", response_model=VehicleOut, status_code=status.HTTP_201_CREATED
)
async def add_my_vehicle(
    payload: VehicleCreate, driver: CurrentDriver, session: DbSession
) -> VehicleOut:
    vehicle = Vehicle(
        driver_id=driver.id,
        make=payload.make.strip(),
        model=payload.model.strip(),
        year=payload.year,
        color=payload.color.strip(),
        plate_number=payload.plate_number.strip().upper(),
        category=payload.category,
    )
    session.add(vehicle)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("رقم اللوحة مسجّل مسبقاً") from exc

    await session.refresh(vehicle)
    return VehicleOut.model_validate(vehicle)


# ------------------------------------------------------------- المستندات


@router.patch(
    "/me/vehicles/{vehicle_id}", response_model=VehicleUpdateResultOut
)
async def update_my_vehicle(
    vehicle_id: uuid.UUID,
    payload: VehicleUpdate,
    driver: CurrentDriver,
    session: DbSession,
) -> VehicleUpdateResultOut:
    """تعديلُ بيانات المركبة (`FUTURE-FEATURES` بند 43/18).

    **وتغييرُ ما تشهد عليه رخصةُ المركبة يُسقط الاعتماد** — نفس سياسة استبدال
    المستند في المرحلة 9-ب، لأن الأثر واحد: اعتمادٌ صدر لمركبةٍ يُشغَّل به
    غيرُها. والقواعدُ في `services/vehicles.py`، والجوابُ يقول ما وقع.
    """
    result = await vehicles_service.update(
        session,
        driver=driver,
        vehicle_id=vehicle_id,
        changes=payload.model_dump(exclude_unset=True, exclude_none=True),
    )
    await session.commit()
    await session.refresh(result.vehicle)
    await session.refresh(driver)
    return VehicleUpdateResultOut(
        vehicle=VehicleOut.model_validate(result.vehicle),
        approval_reverted=result.approval_reverted,
        driver_status=driver.status,
    )


@router.get("/me/earnings", response_model=EarningsOut)
async def my_earnings(
    driver: CurrentDriver,
    user: CurrentUser,
    session: DbSession,
    period: Literal["today", "week", "month"] = Query(default="today"),
) -> EarningsOut:
    """ملخّصُ الأرباح على نافذة (SPEC القسم 9 و12/7).

    **والتجميعُ في الخلفية** كبقية الأرقام: تطبيقٌ يجمع صفحةً مسقوفة من الدفتر
    يعرض رقماً لا يطابقه. والنافذةُ **يومُ الدولة** لا يومُ الخادم.
    """
    result = await earnings_service.summary(
        session,
        driver=driver,
        user_id=user.id,
        country=user.country_code,
        period=period,
        now=datetime.now(UTC),
    )
    return EarningsOut(**asdict(result))


@router.get("/me/documents", response_model=DriverDocumentsOut)
async def list_my_documents(
    driver: CurrentDriver, session: DbSession
) -> DriverDocumentsOut:
    """مستنداتي وما ينقصني للاعتماد (SPEC القسم 12/1)."""
    return DriverDocumentsOut(
        documents=[
            DriverDocumentOut.model_validate(document)
            for document in await documents_service.list_for_driver(session, driver.id)
        ],
        missing_required=await documents_service.missing_required(session, driver.id),
        awaiting_upload=await documents_service.awaiting_upload(session, driver.id),
        # **المطلوبُ لهذا الكبتن لا للجميع** (البند ٥٢): المُعفاةُ من
        # الصورة الشخصية لا تُعرض لها في قائمة ما يلزمها
        required=list(await documents_service.required_for(session, driver.id)),
    )


@router.put(
    "/me/documents/{doc_type}",
    response_model=DocumentUploadOut,
    status_code=status.HTTP_200_OK,
)
async def upload_my_document(
    doc_type: DocumentType,
    driver: CurrentDriver,
    session: DbSession,
    redis: RedisDep,
    file: Annotated[UploadFile, File(description="صورة أو PDF")],
) -> DocumentUploadOut:
    """رفع مستندٍ أو استبدالُ سابقه — والاستبدال يعيده «قيد المراجعة».

    `PUT` لا `POST` لأن العملية إحلالٌ لا إضافة: النوع الواحد صفٌّ واحد
    (`uq_driver_documents_driver_doc_type`)، فرفعُ رخصةٍ ثانية استبدالٌ
    للأولى لا رخصتان.

    ونوعُ الملف وحجمُه يُفحصان من **محتواه** لا من ترويسته (`core/storage.py`).
    وإن كان الكبتن معتمداً والمستندُ مطلوباً عاد حسابُه `pending` — والجواب
    يقول ذلك صراحةً.
    """
    limit = await rate_limit.hit(
        redis,
        f"documents:driver:{driver.id}",
        limit=settings.document_upload_rate_limit,
        window_seconds=settings.document_upload_rate_limit_window_seconds,
    )
    if not limit.allowed:
        raise RateLimited(retry_after=limit.retry_after)

    result = await documents_service.upload(
        session, driver=driver, doc_type=doc_type, reader=file
    )
    await session.commit()
    await session.refresh(result.document)
    await session.refresh(driver)

    # **بعد** الـ commit: ملفٌّ يتيم نفايةٌ تُنظَّف، وصفٌّ بلا ملفٍ عطلٌ يُرى
    if result.superseded_path is not None:
        await storage.delete(result.superseded_path)

    return DocumentUploadOut(
        document=DriverDocumentOut.model_validate(result.document),
        driver_status=driver.status,
        approval_reverted=result.approval_reverted,
    )


@router.get("/me/documents/{document_id}/file")
async def download_my_document(
    document_id: uuid.UUID, driver: CurrentDriver, session: DbSession
) -> FileResponse:
    """ملفُّ مستندي — لا خادمَ ملفاتٍ ساكن ولا رابطَ يُخمَّن (القسم 14)."""
    document = await documents_service.get_for_driver(
        session, driver_id=driver.id, document_id=document_id
    )
    return document_response(document)


def document_response(document: DriverDocument) -> FileResponse:
    """ردٌّ واحد لمسارَي التحميل — الكبتن واللوحة — بنفس الترويسات.

    `nosniff` لأننا نخدم ملفاً رفعه مستخدم: بغيره قد يخمّن متصفحٌ نوعاً
    أخطر مما استنتجناه. و`no-store` لأن المستند وثيقةُ هوية لا صفحةُ عرض.
    """
    path = storage.resolve(document.file_path)
    return FileResponse(
        path,
        media_type=document.content_type,
        headers={
            "Content-Disposition": (
                f'inline; filename="{document.doc_type.value}{path.suffix}"'
            ),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


# ------------------------------------------------- الاتصال والموقع اللحظي


@router.post("/me/online", response_model=DriverOut)
async def go_online(driver: CurrentDriver, session: DbSession) -> DriverOut:
    """مفتاح Online في تطبيق الكبتن (SPEC القسم 12.2).

    يصير الكبتن مرئياً للتوزيع بعد أول بث موقع — لا بمجرد رفع المفتاح.
    """
    await drivers_service.go_online(session, driver)
    await session.commit()
    return DriverOut.model_validate(driver)


@router.post("/me/offline", response_model=DriverOut)
async def go_offline(
    driver: CurrentDriver, session: DbSession, redis: RedisDep
) -> DriverOut:
    await drivers_service.go_offline(session, redis, driver)
    await session.commit()
    return DriverOut.model_validate(driver)


@router.post("/me/location", status_code=status.HTTP_204_NO_CONTENT)
async def report_location(
    payload: DriverLocationIn,
    driver: CurrentDriver,
    session: DbSession,
    redis: RedisDep,
) -> Response:
    """بديل REST لبث الموقع.

    القناة الأساسية هي `WS /ws/driver` (كل ثلاث ثوانٍ بلا كلفة طلب كامل)؛
    هذا المسار لتطبيقٍ فقد مقبسه ولم يُعِده بعد، فلا يختفي الكبتن من الخريطة
    لأجل انقطاع لحظي.

    محكوم بسقف لكل كبتن (SPEC القسم 10): كتابةٌ في Redis تتكرر بلا كلفة على
    العميل، فبغير سقفٍ يكفي توكن صالح واحد لإغراقها.
    """
    limit = await rate_limit.hit(
        redis,
        f"location:driver:{driver.id}",
        limit=settings.location_rate_limit_requests,
        window_seconds=settings.location_rate_limit_window_seconds,
    )
    if not limit.allowed:
        raise RateLimited(retry_after=limit.retry_after)

    context = await drivers_service.presence_context(session, driver)
    await drivers_service.report_location(
        redis, context, lat=payload.lat, lng=payload.lng, heading=payload.heading
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/nearby", response_model=list[NearbyDriverOut])
async def list_nearby_drivers(
    rider: RiderUser,
    session: DbSession,
    redis: RedisDep,
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
) -> list[NearbyDriverOut]:
    """لقطة واحدة من سيارات خريطة الراكب — البث المستمر على `WS /ws/rider`.

    تُستعمل لأول رسمة للخريطة وبعد انقطاع المقبس (SPEC القسم 10: الاسترجاع
    عبر REST). المِلح جديد لكل طلب، فلا يربط `ref` لقطتين ببعضهما.
    """
    salt = secrets.token_hex(16)
    presences = await drivers_service.nearby_available(
        redis, session, country_code=rider.country_code, lat=lat, lng=lng, rider=rider
    )
    return [
        NearbyDriverOut(
            ref=drivers_service.anonymous_ref(presence.driver_id, salt),
            lat=presence.lat,
            lng=presence.lng,
            heading=presence.heading,
            vehicle_category=presence.vehicle_category,
        )
        for presence in presences
    ]


# ------------------------------------------------- إلغاءُ تفعيل الحساب (البند ١٣)


@router.get("/me/deactivation", response_model=DeactivationStateOut)
async def my_deactivation_state(
    driver: CurrentDriver, session: DbSession
) -> DeactivationStateOut:
    """حالُ طلبه وموانعُه والمحتجَزُ برقمه — سؤالٌ واحدٌ بجوابٍ واحد."""
    user = await session.get(User, driver.user_id)
    assert user is not None  # كبتنٌ بلا حسابٍ لا يمرّ من `CurrentDriver`
    limits = await settings_service.get_or_create_wallet_settings(
        session, user.country_code
    )
    pending = await deactivation.pending_for(session, driver.id)
    return DeactivationStateOut(
        request=(
            DeactivationRequestOut.model_validate(pending) if pending else None
        ),
        blockers=await deactivation.blockers(session, driver),
        reserve_amount=limits.withdrawal_reserve_amount,
        currency=currency_for_country(user.country_code).value,
    )


@router.post("/me/deactivation", response_model=DeactivationRequestOut, status_code=201)
async def request_deactivation(
    payload: DeactivationRequestIn, driver: CurrentDriver, session: DbSession
) -> DeactivationRequestOut:
    """يفتح طلبَ إغلاق — يُرفض إن كان عليه ما لا يُترك خلفه (SPEC القسم 7)."""
    row = await deactivation.request(session, driver=driver, reason=payload.reason)
    await session.commit()
    await session.refresh(row)
    return DeactivationRequestOut.model_validate(row)


@router.delete("/me/deactivation", response_model=DeactivationRequestOut)
async def cancel_deactivation(
    driver: CurrentDriver, session: DbSession
) -> DeactivationRequestOut:
    """يعدل عن طلبه ما دام معلّقاً — والقفلُ يمنع سباقَه مع قرار المشرف."""
    row = await deactivation.cancel(session, driver=driver)
    await session.commit()
    await session.refresh(row)
    return DeactivationRequestOut.model_validate(row)


# ------------------------------------------------------- السلف (البند ١٥)


def _state_out(state: advances_service.Eligibility) -> AdvanceStateOut:
    return AdvanceStateOut(
        offered=state.offered,
        eligible=state.eligible,
        requirements=[
            AdvanceRequirementOut(
                key=item.key, met=item.met, value=item.value, needed=item.needed
            )
            for item in state.requirements
        ],
        cap=state.cap,
        currency=state.currency,
        deduction_percent=state.deduction_percent,
        min_kept_amount=state.min_kept_amount,
        term_days=state.term_days,
        debt=(
            AdvanceDebtOut(
                advance=AdvanceOut.model_validate(state.debt.advance),
                remaining=state.debt.remaining,
                overdue=state.debt.overdue,
            )
            if state.debt
            else None
        ),
    )


@router.get("/me/advances", response_model=AdvanceStateOut)
async def my_advance_state(
    driver: CurrentDriver, user: CurrentUser, session: DbSession
) -> AdvanceStateOut:
    """الأهليةُ بشروطها والسقفُ والدَّينُ — نداءٌ واحدٌ لشاشةٍ واحدة."""
    state = await advances_service.eligibility(
        session, driver=driver, country=user.country_code
    )
    return _state_out(state)


@router.post("/me/advances", response_model=AdvanceOut, status_code=201)
async def request_advance(
    payload: AdvanceRequestIn,
    driver: CurrentDriver,
    user: CurrentUser,
    session: DbSession,
    redis: RedisDep,
) -> AdvanceOut:
    """يصرف سلفةً **داخل السقف تلقائياً** — وما فوقه بابُ الإدارة (القرار ٢).

    **وصفُّ الكبتن يُقفل قبل قراءة أهليته**: بغير القفل يقرأ طلبان متزامنان
    «لا سلفةَ قائمة» معاً فيمرّان، ويخرج مالٌ مرتين على سقفٍ واحد.
    """
    locked = await drivers_service.lock(session, driver)
    advance = await advances_service.disburse(
        session,
        driver=locked,
        user=user,
        country=user.country_code,
        amount=payload.amount,
    )
    await session.commit()
    await session.refresh(advance)
    # **بعد الـcommit دائماً**: حالٌ يُعلَن قبل تثبيته قد يتراجع
    await notifications.publish_advance_event(
        session,
        redis,
        driver_user_id=user.id,
        kind="advance_disbursed",
        amount=advance.amount,
        currency=advance.currency.value,
        due_at=advance.due_at,
    )
    return AdvanceOut.model_validate(advance)


@router.post("/me/advances/repay", response_model=AdvanceOut)
async def repay_advance(
    driver: CurrentDriver, user: CurrentUser, session: DbSession, redis: RedisDep
) -> AdvanceOut:
    """سدادٌ كاملٌ من المحفظة — ويرفع الإيقافَ في المسار نفسِه لا بدورةٍ تالية."""
    locked = await drivers_service.lock(session, driver)
    advance = await advances_service.repay_in_full(
        session, driver=locked, user=user
    )
    await session.commit()
    await session.refresh(advance)
    await notifications.publish_advance_event(
        session,
        redis,
        driver_user_id=user.id,
        kind="advance_repaid",
        amount=advance.amount,
        currency=advance.currency.value,
    )
    return AdvanceOut.model_validate(advance)
