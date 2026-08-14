"""الحسابات في اللوحة: القائمة والفلترة واعتماد الكباتن (SPEC القسم 13.2/13.3).

شريحةٌ صغيرة من صفحتي «الكباتن» و«الركاب» تسبق واجهتَهما في المرحلة 11،
لأن قاعدتين من المرحلة 8-ب لا مكان لهما بغيرها:

- **الحسابات غير المحققة تُعلَّم وتُفلتر**: الرقم غير المُثبَت حالةٌ استثنائية
  لا تقع إلا بإطفاء مفتاح الطوارئ، ولا تُعالَج إن لم تُرَ.
- **لا يُعتمد كبتنٌ غير محقق الرقم مهما كان المفتاح**: رقمُ الكبتن هو ما
  يستلم عليه حوالات كليك (SPEC القسم 6/9)، فاعتمادُ من لا نعرف أنه يملكه
  إرسالُ مالٍ إلى رقمٍ مجهول.

وأضافت **المرحلة 9-ب** مراجعةَ المستندات إلى نفس الملف (SPEC القسم 13/2):
معاينةُ كل مستند وقبولُه أو رفضُه بسبب. القراءة لـ staff والقرار لـ admin
وحده — مراجعةٌ تفتح باب العمل على المنصة ليست إجراء دعمٍ فني (القسم 13/8).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select

from app.core.deps import AdminUser, DbSession, RedisDep, StaffUser
from app.core.exceptions import InvalidInput, NotFound
from app.models.deactivation import DeactivationRequest
from app.models.driver import REQUIRED_DOCUMENT_TYPES, Driver, DriverDocument
from app.models.advance import DriverAdvance
from app.models.enums import (
    AdvanceStatus,
    DeactivationStatus,
    AuditAction,
    CountryCode,
    DocumentReviewStatus,
    DriverStatus,
    Gender,
    UserRole,
)
from app.models.user import User
from app.routers.drivers import document_response
from app.schemas.auth import UserBlockUpdate, UserOut
from app.schemas.driver import (
    AdminAdvanceIn,
    AdminAdvanceOut,
    AdvanceCapIn,
    AdvanceOut,
    AdvanceWriteOffIn,
    DeactivationDecisionIn,
    DeactivationRequestOut,
    AdminDriverRow,
    DocumentReviewIn,
    DriverDocumentOut,
    DriverDocumentsOut,
    DriverGenderUpdate,
    DriverOut,
    DriverStatusUpdate,
)
from app.services import deactivation
from app.services import (
    advances as advances_service,
    audit,
    documents as documents_service,
    drivers as drivers_service,
    notifications,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
async def list_users(
    _staff: StaffUser,
    session: DbSession,
    role: UserRole | None = None,
    country_code: CountryCode | None = None,
    phone_verified: bool | None = Query(
        default=None,
        description="فلترة الحسابات غير المحققة — تُعالَج أولاً بعد إعادة تفعيل المفتاح",
    ),
    is_blocked: bool | None = None,
    q: str | None = Query(default=None, max_length=120, description="اسمٌ أو رقم"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[UserOut]:
    """قائمة الحسابات بوسم التحقق — و`UserOut.phone_verified` هو الوسم."""
    stmt = select(User).order_by(User.created_at.desc())
    if role is not None:
        stmt = stmt.where(User.role == role)
    if country_code is not None:
        stmt = stmt.where(User.country_code == country_code)
    if phone_verified is True:
        stmt = stmt.where(User.phone_verified_at.is_not(None))
    elif phone_verified is False:
        stmt = stmt.where(User.phone_verified_at.is_(None))
    if is_blocked is not None:
        stmt = stmt.where(User.is_blocked.is_(is_blocked))
    if (q or "").strip():
        # البحثُ على الاسم والرقم معاً — والرقمُ يُبحث كما هو مخزَّن (E.164)
        # وكما قد يكتبه المشرف محلياً، فـ`ilike` بالاحتواء لا بالبادئة
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.name.ilike(pattern), User.phone.ilike(pattern)))

    rows = (await session.scalars(stmt.limit(limit).offset(offset))).all()
    return [UserOut.model_validate(row) for row in rows]


@router.post("/users/{user_id}/block", response_model=UserOut)
async def block_user(
    user_id: uuid.UUID,
    payload: UserBlockUpdate,
    admin: AdminUser,
    session: DbSession,
) -> UserOut:
    """حظرُ حساب (SPEC القسم 13/3) — **`admin` لا `support`**.

    القسم 13/8 يعطي الدعمَ قراءةً ومعالجةَ نزاعات، وإغلاقُ حسابٍ ليس منهما.

    **ولا حاجةَ لإبطال الجلسات**: `core/deps.get_current_user` يقرأ العمود في
    كل طلبٍ مُصادَق عليه، و`auth.refresh` يقرؤه كذلك — فالحظرُ يسري على
    التوكن القائم لا على ما بعده. إبطالُ الجلسات هنا كان سيوهم أن الحماية منه
    وهي من قراءة العمود.

    **والحظرُ غير تجميد المحفظة** (`/admin/wallets/{id}/freeze`): ذاك يوقف
    حركةَ محفظةٍ مشبوهة ويبقي صاحبَها راكباً يدفع نقداً (القسم 4/13.3)، وهذا
    يغلق الحساب كلَّه. الاثنان بابان لأن الحالتين مختلفتان.
    """
    if not (payload.reason or "").strip():
        raise InvalidInput("سبب الحظر مطلوب")

    return await _set_blocked(
        session, user_id=user_id, blocked=True, admin=admin, reason=payload.reason
    )


@router.post("/users/{user_id}/unblock", response_model=UserOut)
async def unblock_user(
    user_id: uuid.UUID,
    payload: UserBlockUpdate,
    admin: AdminUser,
    session: DbSession,
) -> UserOut:
    """رفعُ الحظر — بلا سببٍ إلزامي: القيدُ يُسأل عنه لا الإفراج."""
    return await _set_blocked(
        session, user_id=user_id, blocked=False, admin=admin, reason=payload.reason
    )


async def _set_blocked(
    session,
    *,
    user_id: uuid.UUID,
    blocked: bool,
    admin: User,
    reason: str | None,
) -> UserOut:
    """البابُ الوحيد لتغيير `is_blocked` — والقيدُ في نفس المعاملة (القسم 14).

    والصفُّ يُقفل قبل الكتابة كما تفرض قاعدة المشروع على كل تغيير حالة: بلا
    قفلٍ يمرّ حظرٌ ورفعُ حظرٍ متزامنان فيكتب أحدهما فوق الآخر، ويحمل السجلُّ
    قيدين متناقضين لا يقول أيُّهما الأخير.
    """
    user = await session.get(User, user_id, with_for_update=True)
    if user is None:
        raise NotFound("الحساب غير موجود")
    if user.role in (UserRole.ADMIN, UserRole.SUPPORT):
        # حظرُ حسابٍ إداريٍّ من اللوحة بابٌ يُغلق به مشرفٌ على زملائه — وإدارةُ
        # حسابات الموظفين ليست في القسم 13/3 أصلاً (هو عن الركاب)
        raise InvalidInput("لا يُحظر حسابٌ إداريٌّ من هذه الشاشة")

    user.is_blocked = blocked
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="user",
        entity_id=user.id,
        # نفس شكل `drivers.set_status`: الحالةُ الجديدة وسببُها. والسببُ
        # قرارُ مشرفٍ لا قيمةُ حقلٍ سرّية، فحفظُه هو الغرض من القيد
        details=(
            {"blocked": blocked, "reason": reason}
            if reason
            else {"blocked": blocked}
        ),
    )
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.get("/drivers", response_model=list[AdminDriverRow])
async def list_drivers(
    _staff: StaffUser,
    session: DbSession,
    status: DriverStatus | None = None,
    country_code: CountryCode | None = None,
    gender_verified: bool | None = Query(
        default=None,
        description="فرزُ من يعمل بلا جنسٍ مثبت — متراكمُ ما قبل الخدمة النسائية",
    ),
    q: str | None = Query(default=None, max_length=120, description="اسمٌ أو رقم"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AdminDriverRow]:
    """قائمة الكباتن بحالها وعدّ مستنداتها (SPEC القسم 13/2).

    **العدّ في الاستعلام لا في نداءٍ لكل صف**: القرار «من أراجع الآن» يُتخذ من
    القائمة، وصفحةٌ من خمسين كبتناً لا يجوز أن تصير خمسين نداءً.
    """
    pending = func.count(DriverDocument.id).filter(
        DriverDocument.review_status == DocumentReviewStatus.PENDING
    )
    rejected = func.count(DriverDocument.id).filter(
        DriverDocument.review_status == DocumentReviewStatus.REJECTED
    )
    approved_types = func.array_agg(DriverDocument.doc_type).filter(
        DriverDocument.review_status == DocumentReviewStatus.APPROVED
    )

    stmt = (
        select(Driver, User, pending, rejected, approved_types)
        .join(User, Driver.user_id == User.id)
        .outerjoin(DriverDocument, DriverDocument.driver_id == Driver.id)
        .group_by(Driver.id, User.id)
        .order_by(Driver.created_at.desc())
    )
    if status is not None:
        stmt = stmt.where(Driver.status == status)
    if country_code is not None:
        stmt = stmt.where(User.country_code == country_code)
    if gender_verified is True:
        stmt = stmt.where(User.gender_verified_at.is_not(None))
    elif gender_verified is False:
        stmt = stmt.where(User.gender_verified_at.is_(None))
    if (q or "").strip():
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.name.ilike(pattern), User.phone.ilike(pattern)))

    rows = (await session.execute(stmt.limit(limit).offset(offset))).all()
    return [
        AdminDriverRow(
            driver_id=driver.id,
            user_id=user.id,
            name=user.name,
            phone=user.phone,
            country_code=user.country_code,
            status=driver.status,
            phone_verified=user.phone_verified_at is not None,
            rating_avg=driver.rating_avg,
            is_online=driver.is_online,
            gender=user.gender,
            gender_verified=user.gender_verified_at is not None,
            gender_preference=driver.gender_preference,
            documents_pending=pending_count,
            documents_rejected=rejected_count,
            # الناقصُ من المطلوب: ما لم يُقبل بعد — وهو ما يمنع الاعتماد
            missing_required=[
                doc_type
                for doc_type in REQUIRED_DOCUMENT_TYPES
                if doc_type.value not in (approved or [])
            ],
            created_at=driver.created_at,
        )
        for driver, user, pending_count, rejected_count, approved in rows
    ]


@router.post("/drivers/{driver_id}/suspend", response_model=DriverOut)
async def suspend_driver(
    driver_id: uuid.UUID,
    payload: DriverStatusUpdate,
    admin: AdminUser,
    session: DbSession,
) -> DriverOut:
    """إيقافُ كبتن (SPEC القسم 13/2) — **بسببٍ إلزامي يدخل التدقيق**.

    والإيقافُ يُخرجه من التوزيع فوراً بحكم `dispatch.eligible_driver_ids`،
    ولا يُنهي رحلةً جارية: قطعُ رحلةٍ في منتصفها يترك راكباً في الطريق، والقرارُ
    الإداري يقع على ما بعدها.
    """
    if not (payload.reason or "").strip():
        raise InvalidInput("سبب الإيقاف مطلوب")

    driver = await _driver(session, driver_id)
    driver = await drivers_service.set_status(
        session,
        driver=driver,
        status=DriverStatus.SUSPENDED,
        actor=admin,
        reason=payload.reason.strip(),
    )
    await session.commit()
    await session.refresh(driver)
    return DriverOut.model_validate(driver)


@router.post("/drivers/{driver_id}/activate", response_model=DriverOut)
async def activate_driver(
    driver_id: uuid.UUID,
    payload: DriverStatusUpdate,
    admin: AdminUser,
    session: DbSession,
) -> DriverOut:
    """إعادةُ تفعيل موقوف — **بحارسَي الاعتماد نفسِهما**.

    من أُوقف ثم رُفعت عنه العقوبة يعود إلى `approved`، وذلك اعتمادٌ جديد: لو
    مرّ من باب غير `approve` لصار الإيقافُ طريقاً للالتفاف على شرط المستندات
    والرقم المُثبت.
    """
    driver = await _driver(session, driver_id)
    if driver.status is not DriverStatus.SUSPENDED:
        raise InvalidInput("هذا الكبتن ليس موقوفاً")

    driver = await drivers_service.approve(session, driver=driver, actor=admin)
    await session.commit()
    await session.refresh(driver)
    return DriverOut.model_validate(driver)


@router.put("/drivers/{driver_id}/gender", response_model=DriverOut)
async def set_driver_gender(
    driver_id: uuid.UUID,
    payload: DriverGenderUpdate,
    admin: AdminUser,
    session: DbSession,
    redis: RedisDep,
) -> DriverOut:
    """يثبّت المشرفُ جنسَ الكبتن من هويته المرفوعة (المرحلة 10-ج).

    **لـ admin لا support**: هذا الحقل هو ما يجعل حساباً «سائقةً للنساء»،
    ومراجعةُ المستندات نفسها قرارُ admin (القسم 13/8).

    **ويُختم بلحظته** (`gender_verified_at`)، لأن المطابقة تقرأ المختوم وحده:
    بغير الختم لا فرق بين جنسٍ قرأه مشرفٌ من هوية وجنسٍ كتبه صاحبه عن نفسه.

    **ولا يعيد دورة اعتماد**: الهوية مرفوعة ومراجَعة، وإرجاعُ كبتنٍ معتمدٍ إلى
    الطابور لأجل حقلٍ واحد يجعل تفريغ المتراكم مستحيلاً عملياً — وهو المتراكم
    الذي يبقى `women_service_enabled` مطفأً حتى يُفرَّغ.

    وقيدُ التدقيق يحمل **اسم الحقل لا قيمته**، كبقية كتابات اللوحة.
    """
    driver = await _driver(session, driver_id)
    user = await session.get(User, driver.user_id, with_for_update=True)
    if user is None:  # pragma: no cover - حسابٌ محذوف تحت كبتن قائم
        raise NotFound()

    # **مخالفةُ الوثائق لما أقرّته** (قرارُ المالك 2026-08-13): ختمٌ يخالف
    # إقراراً سابقاً يُلغي الوضعَ النسائيَّ عن الحساب — السِمةُ وخيارُها معاً،
    # لأن كليهما مبنيٌّ على `gender = female` وحده. ولا عمودَ «مُلغى» يُضاف:
    # الجنسُ المختوم **هو** الحقيقة، وعمودٌ ثانٍ يقول الشيءَ نفسَه يفترق عنه.
    revoking = (
        user.gender is Gender.FEMALE
        and payload.gender is not Gender.FEMALE
    )
    if revoking and not (payload.reason or "").strip():
        raise InvalidInput(
            "سببُ المخالفة مطلوب — فهو ما يُقرأ في سجل التدقيق بعد شهر"
        )

    user.gender = payload.gender
    user.gender_verified_at = datetime.now(UTC)
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="user",
        entity_id=user.id,
        # **والسببُ يُكتب حيث يُلغى وضعٌ لا حيث يُثبَّت حقل**: قاعدةُ «الأسماءُ
        # لا القيم» تُستثنى للسببِ المكتوب وحده (الإيقاف، الحظر، إطفاءُ حارس)
        details=(
            {
                "fields": ["gender", "gender_verified_at"],
                "women_mode_revoked": True,
                "reason": payload.reason,
            }
            if revoking
            else {"fields": ["gender", "gender_verified_at"]}
        ),
    )
    await session.commit()
    await session.refresh(driver)

    # **الإشعارُ بعد الـcommit** كبقية البثّ. واختفاءُ لونٍ وميزةٍ بلا تفسيرٍ
    # يفتح تذكرةَ دعمٍ فوراً — والنصُّ يقول السببَ العامَّ ولا يزيد
    if revoking:
        await notifications.publish_women_mode_revoked(
            session, redis, user_id=user.id
        )
    return DriverOut.model_validate(driver)


@router.get("/drivers/{driver_id}/documents", response_model=DriverDocumentsOut)
async def list_driver_documents(
    driver_id: uuid.UUID, _staff: StaffUser, session: DbSession
) -> DriverDocumentsOut:
    """مستندات كبتنٍ للمراجعة، ومعها ما ينقصه للاعتماد (SPEC القسم 13/2)."""
    await _driver(session, driver_id)
    return DriverDocumentsOut(
        documents=[
            DriverDocumentOut.model_validate(document)
            for document in await documents_service.list_for_driver(session, driver_id)
        ],
        missing_required=await documents_service.missing_required(session, driver_id),
        required=list(REQUIRED_DOCUMENT_TYPES),
    )


@router.get("/drivers/{driver_id}/documents/{document_id}/file")
async def download_driver_document(
    driver_id: uuid.UUID,
    document_id: uuid.UUID,
    _staff: StaffUser,
    session: DbSession,
) -> FileResponse:
    """معاينة المستند في اللوحة — بنفس ترويسات مسار الكبتن."""
    document = await documents_service.get_for_review(
        session, driver_id=driver_id, document_id=document_id
    )
    return document_response(document)


@router.post(
    "/drivers/{driver_id}/documents/{document_id}/review",
    response_model=DriverDocumentOut,
)
async def review_driver_document(
    driver_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: DocumentReviewIn,
    admin: AdminUser,
    session: DbSession,
    redis: RedisDep,
) -> DriverDocumentOut:
    """قبول مستند أو رفضه — **admin حصراً** (SPEC القسم 13/8).

    المراجعة قرارٌ يفتح باب العمل على المنصة، لا إجراءَ دعمٍ فني. وقفلُ
    الصفِّ داخل `documents.review` لا هنا: بغيره تمر ضغطتان متزامنتان فيصل
    الكبتنَ إشعاران متناقضان عن وثيقةٍ واحدة.
    """
    driver = await _driver(session, driver_id)
    document = await documents_service.review(
        session,
        driver_id=driver_id,
        document_id=document_id,
        actor=admin,
        approved=payload.approved,
        note=payload.note,
    )
    await session.commit()
    await session.refresh(document)

    # بعد الـ commit كما تفرض قاعدة البثّ: حالةٌ تُعلن ثم تُلغى أسوأ من
    # حالةٍ تتأخر لحظة
    await notifications.publish_document_review(
        session, redis, driver_user_id=driver.user_id, document=document
    )
    return DriverDocumentOut.model_validate(document)


@router.post("/drivers/{driver_id}/approve", response_model=DriverOut)
async def approve_driver(
    driver_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> DriverOut:
    """اعتماد الكبتن — بحارسَي `services/drivers.approve`.

    رقمٌ مُثبت (8-ب) **ومستنداتٌ مطلوبةٌ مقبولةٌ كلها** (9-ب). فالزرُّ لم يعد
    يعمل والمستنداتُ فارغة، وهو ما كان يقع قبل هذه المرحلة.
    """
    driver = await _driver(session, driver_id)
    driver = await drivers_service.approve(session, driver=driver, actor=admin)
    await session.commit()
    await session.refresh(driver)
    return DriverOut.model_validate(driver)


@router.post("/drivers/{driver_id}/reject", response_model=DriverOut)
async def reject_driver(
    driver_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> DriverOut:
    driver = await _driver(session, driver_id)
    driver = await drivers_service.set_status(
        session, driver=driver, status=DriverStatus.REJECTED, actor=admin
    )
    await session.commit()
    await session.refresh(driver)
    return DriverOut.model_validate(driver)


async def _driver(session, driver_id: uuid.UUID) -> Driver:
    driver = await session.get(Driver, driver_id)
    if driver is None:
        raise NotFound("الكبتن غير موجود")
    return driver


@router.get(
    "/drivers/deactivations", response_model=list[DeactivationRequestOut]
)
async def list_deactivations(
    _: AdminUser,
    session: DbSession,
    status: DeactivationStatus | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[DeactivationRequestOut]:
    """طلباتُ إغلاق الحسابات — المعلّقةُ أولاً بحكم الترتيب."""
    stmt = select(DeactivationRequest).order_by(
        DeactivationRequest.created_at.desc()
    )
    if status is not None:
        stmt = stmt.where(DeactivationRequest.status == status)
    rows = await session.scalars(stmt.limit(limit).offset(offset))
    return [DeactivationRequestOut.model_validate(row) for row in rows]


@router.patch(
    "/drivers/deactivations/{request_id}", response_model=DeactivationRequestOut
)
async def decide_deactivation(
    request_id: uuid.UUID,
    payload: DeactivationDecisionIn,
    admin: AdminUser,
    session: DbSession,
) -> DeactivationRequestOut:
    """قرارُ المشرف — والموافقةُ تُعيد قراءةَ الموانع لحظتَها لا لحظةَ الطلب."""
    row = await deactivation.decide(
        session,
        request_id=request_id,
        admin=admin,
        approved=payload.approved,
        note=payload.note,
    )
    await session.commit()
    await session.refresh(row)
    return DeactivationRequestOut.model_validate(row)


# ------------------------------------------------------- السلف (البند ١٥)


@router.get("/drivers/advances", response_model=list[AdminAdvanceOut])
async def list_advances(
    _: AdminUser,
    session: DbSession,
    status: AdvanceStatus | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AdminAdvanceOut]:
    """السلفُ بمتبقّيها — **والمتبقّي يُجمع من الدفتر لكل صف**.

    وهي صفحةٌ محدودةٌ لا جدولٌ كامل، فالجمعُ لكلٍّ منها استعلامٌ صغيرٌ على
    فهرسٍ — لا جمعٌ في المتصفح: مجموعُ صفحةٍ تحت عنوانٍ يقول «الكل» رقمٌ يكذب
    (قاعدةُ `services/stats.py`).
    """
    stmt = select(DriverAdvance).order_by(DriverAdvance.created_at.desc())
    if status is not None:
        stmt = stmt.where(DriverAdvance.status == status)
    rows = list(await session.scalars(stmt.limit(limit).offset(offset)))
    out: list[AdminAdvanceOut] = []
    for row in rows:
        paid = await advances_service.repaid_amount(session, row.id)
        out.append(
            AdminAdvanceOut(
                **AdvanceOut.model_validate(row).model_dump(),
                remaining=row.amount - paid,
                overdue=(
                    row.status is AdvanceStatus.OUTSTANDING
                    and row.due_at <= datetime.now(UTC)
                ),
            )
        )
    return out


@router.post("/drivers/advances", response_model=AdvanceOut, status_code=201)
async def disburse_advance(
    payload: AdminAdvanceIn, admin: AdminUser, session: DbSession
) -> AdvanceOut:
    """صرفٌ بموافقة مشرف — **البابُ الوحيد لما يتجاوز السقف** (القرار ٢)."""
    driver = await session.get(Driver, payload.driver_id)
    if driver is None:
        raise NotFound("الكبتن غير موجود")
    driver = await drivers_service.lock(session, driver)
    user = await session.get(User, driver.user_id)
    assert user is not None
    advance = await advances_service.disburse(
        session,
        driver=driver,
        user=user,
        country=user.country_code,
        amount=payload.amount,
        approved_by=admin,
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="driver_advance",
        entity_id=advance.id,
        details={"amount": str(advance.amount)},
    )
    await session.commit()
    await session.refresh(advance)
    return AdvanceOut.model_validate(advance)


@router.patch("/drivers/advances/{advance_id}/writeoff", response_model=AdvanceOut)
async def write_off_advance(
    advance_id: uuid.UUID,
    payload: AdvanceWriteOffIn,
    admin: AdminUser,
    session: DbSession,
) -> AdvanceOut:
    """شطبُ دَينٍ بقرارٍ إداريٍّ مسجَّل (القرار ٧).

    **ولا شطبَ آليّ**: تسعون يوماً تجعله *مقترحاً*، والاعترافُ بالخسارة قرارُ
    إنسانٍ باسمه. **ويرفع الإيقاف**: الشطبُ اعترافٌ بأن هذا المال لن يعود،
    وإبقاءُ الحساب موقوفاً بعده عقوبةٌ على دَينٍ لم يعد قائماً.
    """
    advance = await advances_service.write_off(
        session, advance_id=advance_id, admin=admin, reason=payload.reason
    )
    await session.commit()
    await session.refresh(advance)
    return AdvanceOut.model_validate(advance)


@router.put("/drivers/{driver_id}/advance-cap", response_model=DriverOut)
async def set_advance_cap(
    driver_id: uuid.UUID,
    payload: AdvanceCapIn,
    admin: AdminUser,
    session: DbSession,
) -> DriverOut:
    """سقفُ كبتنٍ بعينه — **`null` لا تخصيص، وصفرٌ منعٌ**، والسببُ في التدقيق."""
    driver = await _driver(session, driver_id)
    driver.advance_cap_override = payload.cap
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="driver",
        entity_id=driver.id,
        # **السببُ المكتوبُ استثناءُ «لا قيمَ في التدقيق»**: هو نفسُه محتوى
        # القيد — قرارُ مشرفٍ لا قيمةٌ مخزَّنة
        details={"advance_cap_override": True, "reason": payload.reason},
    )
    await session.commit()
    await session.refresh(driver)
    return DriverOut.model_validate(driver)
