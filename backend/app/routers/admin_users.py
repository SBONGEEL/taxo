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

from fastapi import APIRouter, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select

from app.core.deps import (
    DbSession,
    PermissionsManager,
    RedisDep,
    StaffUser,
    UsersManager,
)
from app.core.email import normalize_email
from app.core.exceptions import InvalidInput, NotFound
from app.models.deactivation import DeactivationRequest
from app.models.driver import Driver, DriverDocument, required_document_types
from app.models.advance import DriverAdvance
from app.models.enums import (
    AdminPermission,
    AdvanceStatus,
    DeactivationStatus,
    AuditAction,
    CountryCode,
    DriverDebtStatus,
    DocumentReviewStatus,
    DriverStatus,
    Gender,
    UserRole,
)
from app.models.admin_permission import AdminPermissionGrant
from app.models.user import User
from app.models.vehicle import Vehicle
from app.routers.drivers import document_response
from app.schemas.auth import (
    AdminPermissionsIn,
    AdminPermissionsOut,
    UserBlockUpdate,
    UserMessageIn,
    UserOut,
    UserProfileUpdate,
)
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
    VehicleOut,
)
from app.models.user_role_grant import has_role_clause
from app.models.debt import DriverDebt
from app.schemas.debt import (
    AdminDebtOut,
    DebtClaimOut,
    DebtConfirmIn,
    DebtWriteOffIn,
)
from app.services import deactivation
from app.services import permissions as permissions_service
from app.services import (
    admin_search,
    advances as advances_service,
    audit,
    cliq_debts,
    debts as debts_service,
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
        # **مَن يملك الدور** لا مَن دورُه الأساسيُّ هو (نموذجُ الأدوار)
        stmt = stmt.where(has_role_clause(role))
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
        # **حروفُ `LIKE` تُهرَّب** (عطبٌ قِيس 2026-09-02): كان النمطُ
        # `f"%{q}%"` عارياً — **فمن كتب `%` رأى الجدولَ كلَّه وظنّه نتيجةَ
        # بحثه**، ومن كتب `_` طابق أيَّ حرف. والبيتُ الواحد
        # `services/admin_search.py`.
        stmt = stmt.where(admin_search.person_clause(q.strip()))

    rows = (await session.scalars(stmt.limit(limit).offset(offset))).all()
    return [UserOut.model_validate(row) for row in rows]


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(
    user_id: uuid.UUID, _staff: StaffUser, session: DbSession
) -> UserOut:
    """حسابٌ واحدٌ بحاله — **قسمُ «الحساب» في الملفِّ الشخصيّ** (§37).

    **ولمَ بابٌ ولا قراءةٌ من صفِّ القائمة**: صفُّ الكبتن (`AdminDriverRow`)
    يحمل ما يُفرز به «من أراجع الآن» — **ولا يحمل `is_blocked` ولا البريدَ
    ولا الأدوارَ ولا «رقمٌ محجوز»**. فكان المشرفُ يفتح كبتناً موقوفَ الحساب
    **ولا شيءَ في درجه يقول ذلك**: يقرأ «معتمد» ويسأل لماذا لا تصله رحلات.

    **ولا تُوسَّع حمولةُ القائمة بدلاً منه**: صفحةٌ من خمسين تحمل ذلك لخمسين
    لا يُقرأ منهم واحد — وهو ما يقوله §5-ج عن العمود المحضَّر بثمنه.

    **ولا كتابةَ هنا**: الحظرُ بابُه `_set_blocked` وحدَه بسببٍ إلزاميٍّ
    وقفلٍ، **وبابُ قراءةٍ لا يصير طريقاً ثانياً إليه**.
    """
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("الحساب غير موجود")
    return UserOut.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user_profile(
    user_id: uuid.UUID,
    payload: UserProfileUpdate,
    admin: UsersManager,
    session: DbSession,
) -> UserOut:
    """تعديلُ اسمِ حسابٍ وبريدِه من ملفّه — **البند ١١ (§39٫١١، §46)**.

    **وحقلان لا أكثر، وكلُّ غائبٍ غائبٌ بعلّته المكتوبة في `UserProfileUpdate`**:
    الهاتفُ مُعرِّفُ دخولٍ لا حقلُ اتصال، والسوقُ يُختم على كلِّ رحلةٍ ودفعة،
    والأدوارُ والحظرُ والجنسُ لكلٍّ بابُه وحارسُه.

    **وكتابةُ بريدٍ تُسقط إثباتَه دائماً**: المُثبَتُ وحدَه يحجز العنوان
    (الفهرسُ الجزئيُّ) ويصلح قناةَ استرجاع (§31) — **فبريدٌ يكتبه مشرفٌ ويبقى
    مُثبَتاً بابُ استيلاءٍ على حساب**. فيبقى بياناً يُراسَل به **حتى يُثبته
    صاحبُه**.

    **والقيمةُ قبل وبعد في التدقيق** (§40٫١): «عُدِّل الاسم» لا تقول شيئاً بعد
    شهر.
    """
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("الحساب غير موجود")

    fields = payload.model_dump(exclude_unset=True)
    changes: dict[str, dict[str, object]] = {}

    if "name" in fields and fields["name"] is not None:
        after = fields["name"].strip()
        if not after:
            raise InvalidInput("الاسم مطلوب — ولا يُمحى اسمُ حساب.")
        if after != user.name:
            changes["name"] = {"before": user.name, "after": after}
            user.name = after

    if "email" in fields:
        raw_email = (fields["email"] or "").strip()
        after_email = normalize_email(raw_email) if raw_email else None
        if after_email != user.email:
            changes["email"] = {"before": user.email, "after": after_email}
            user.email = after_email
            # **الإثباتُ يسقط مع كلِّ كتابةٍ من اللوحة** — ولو أُعيد العنوانُ
            # نفسُه لاحقاً فصاحبُه هو من يُثبته
            if user.email_verified_at is not None:
                changes["email_verified_at"] = {
                    "before": user.email_verified_at.isoformat(),
                    "after": None,
                }
                user.email_verified_at = None

    if not changes:
        return UserOut.model_validate(user)

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="user",
        entity_id=user.id,
        changes=changes,
    )
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.post("/users/{user_id}/notify", status_code=status.HTTP_204_NO_CONTENT)
async def notify_one_user(
    user_id: uuid.UUID,
    payload: UserMessageIn,
    admin: UsersManager,
    session: DbSession,
    redis: RedisDep,
) -> None:
    """رسالةٌ فرديةٌ إلى صاحب حساب — **بمسار FCM القائم لا بمسارٍ جديد**.

    **شرطُ المالك بنصِّه** (§39٫١١): «وإرسالُ إشعارٍ فرديٍّ له يمرّ بمسار FCM
    القائم لا بمسارٍ جديد، نصُّه بالعربية ومختومٌ في التدقيق».

    **فالصندوقُ ثمّ Push** من `notifications.publish_admin_message` — ومنه
    تأتي كلُّ خصائص المسار: صفٌّ يبقى ولو لم يكن ثمّة عقدُ FCM، وتعطيلُ
    الرموز الميتة، وابتلاعُ عطبِ المزوّد فلا يسقط الطلب.

    **والنصُّ يدخل التدقيق كاملاً**: «أُرسلت رسالة» لا تقول شيئاً بعد شهر،
    **ومن يُسأل عمّا كُتب لحسابٍ يحتاج ما كُتب**. وهو نفسُ سببِ حفظ سببِ الحظر.

    **ولا يُرسل إلى موظّف**: اللوحةُ ليست صندوقَ بريدٍ داخلياً، **ورسالةٌ إلى
    مشرفٍ من مشرفٍ تخلط قناةَ العملاء بقناة العمل**.
    """
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("الحساب غير موجود")
    if user.role in (UserRole.ADMIN, UserRole.SUPPORT):
        raise InvalidInput(
            "لا تُرسل رسالةُ عملاءَ إلى حساب موظّف — القناةُ لصاحب التطبيق."
        )

    title = payload.title.strip()
    body = payload.body.strip()
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="user_message",
        entity_id=user.id,
        details={"title": title, "body": body},
    )
    await session.commit()

    # **البثُّ بعد الـcommit** كبقية النواشر: حدثٌ يُعلَن قبل أن يثبت قد يُلغى
    await notifications.publish_admin_message(
        session, redis, user_id=user.id, title=title, body=body
    )


@router.post("/users/{user_id}/block", response_model=UserOut)
async def block_user(
    user_id: uuid.UUID,
    payload: UserBlockUpdate,
    admin: UsersManager,
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
    admin: UsersManager,
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
    if user.has_role(UserRole.ADMIN, UserRole.SUPPORT):
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
        # **حروفُ `LIKE` تُهرَّب** (عطبٌ قِيس 2026-09-02): كان النمطُ
        # `f"%{q}%"` عارياً — **فمن كتب `%` رأى الجدولَ كلَّه وظنّه نتيجةَ
        # بحثه**، ومن كتب `_` طابق أيَّ حرف. والبيتُ الواحد
        # `services/admin_search.py`.
        stmt = stmt.where(admin_search.person_clause(q.strip()))

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
            advance_cap_override=driver.advance_cap_override,
            documents_pending=pending_count,
            documents_rejected=rejected_count,
            # الناقصُ من المطلوب: ما لم يُقبل بعد — وهو ما يمنع الاعتماد.
            # **والمطلوبُ لكل كبتنٍ على حدة** (البند ٥٢)، ويُحسب هنا **بلا
            # استعلامٍ إضافي**: جنسُ صاحبه وختمُه في الصفِّ المقروء أصلاً
            missing_required=[
                doc_type
                for doc_type in required_document_types(
                    gender_verified_female=(
                        user.gender is Gender.FEMALE
                        and user.gender_verified_at is not None
                    )
                )
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
    admin: UsersManager,
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
    admin: UsersManager,
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
    admin: UsersManager,
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


@router.get("/drivers/{driver_id}/vehicles", response_model=list[VehicleOut])
async def list_driver_vehicles(
    driver_id: uuid.UUID, _staff: StaffUser, session: DbSession
) -> list[VehicleOut]:
    """مركباتُ الكبتن — **قسمُ المركبة في الملفِّ الشخصيّ** (§37).

    **ولمَ بابٌ ولا حقلٌ على صفِّ القائمة**: `AdminDriverRow` صفُّ فرزٍ يُقرأ
    منه «من أراجع الآن»، **وصفحةٌ من خمسين تحمل مركباتِ خمسين** توسّع الصفَّ
    لِما لا يُقرأ فيه. والملفُّ يُفتح لواحد.

    **ولا كتابةَ هنا**: هوّيةُ المركبة يكتبها صاحبُها من تطبيقه، **وتحريرُها
    يُسقط اعتمادَه إلى `pending`** بقفلٍ مكتوبٍ في `CLAUDE.md`. **وبابُ لوحةٍ
    يكتبها يصير طريقاً ثانياً إلى ذلك السقوط لا يمرّ بالقفل** — فالمشرفُ يقرأ
    ويقرّر على الوثيقة، لا يصحّح لوحةَ سيّارةٍ بيده.

    **وقائمةٌ لا صفٌّ واحد**: العلاقةُ `drivers.vehicles` جمعٌ في النموذج،
    **ورجوعُ الأولِ وحدَه يخفي الثانيةَ** عمّن يقرأ ملفّاً اسمُه «الكامل».
    """
    await _driver(session, driver_id)
    rows = await session.scalars(
        select(Vehicle)
        .where(Vehicle.driver_id == driver_id)
        .order_by(Vehicle.created_at.desc())
    )
    return [VehicleOut.model_validate(row) for row in rows]


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
        # اللوحةُ تقرأ سؤالَ الحارس، وهذا يُملأ لأن المخطّط واحد — والمشرفُ
        # يرى بعينه ما ينتظر رفعاً وما ينتظر قراره
        awaiting_upload=await documents_service.awaiting_upload(session, driver_id),
        # **المطلوبُ لهذا الكبتن لا للجميع** (البند ٥٢): المُعفاةُ من
        # الصورة الشخصية لا تُعرض لها في قائمة ما يلزمها
        required=list(await documents_service.required_for(session, driver_id)),
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
    admin: UsersManager,
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
        expires_on=payload.expires_on,
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
    driver_id: uuid.UUID, admin: UsersManager, session: DbSession
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
    driver_id: uuid.UUID, admin: UsersManager, session: DbSession
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
    _: UsersManager,
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
    admin: UsersManager,
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
    _: UsersManager,
    session: DbSession,
    status: AdvanceStatus | None = None,
    driver_id: uuid.UUID | None = Query(
        default=None, description="سلفُ كبتنٍ بعينه — للملفِّ الشخصيّ (§37)"
    ),
    q: str | None = Query(default=None, max_length=120, description="اسمُ الكبتن أو رقمُه"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AdminAdvanceOut]:
    """السلفُ بمتبقّيها — **والمتبقّي يُجمع من الدفتر لكل صف**.

    وهي صفحةٌ محدودةٌ لا جدولٌ كامل، فالجمعُ لكلٍّ منها استعلامٌ صغيرٌ على
    فهرسٍ — لا جمعٌ في المتصفح: مجموعُ صفحةٍ تحت عنوانٍ يقول «الكل» رقمٌ يكذب
    (قاعدةُ `services/stats.py`).

    **و`driver_id` مرشِّحٌ كـ`q` لا منطقٌ ثانٍ** (§37): الملفُّ الشخصيُّ يقرأ
    سلفَ صاحبه **من هذا الباب** لا من بابٍ يُبنى له — «الصفحةُ تقرأ ولا تحسب
    من جديد» (§5-ج). **ولا يُرشَّح بالاسم بدلاً منه**: كبتنان يتشابه اسمُهما
    يخلطان صفوفَهما في ملفٍّ يقول «سلفُ هذا الشخص».
    """
    stmt = (
        select(DriverAdvance, User)
        .join(Driver, Driver.id == DriverAdvance.driver_id)
        .join(User, User.id == Driver.user_id)
        .order_by(DriverAdvance.created_at.desc())
    )
    if status is not None:
        stmt = stmt.where(DriverAdvance.status == status)
    if driver_id is not None:
        stmt = stmt.where(DriverAdvance.driver_id == driver_id)
    # **مرشِّحٌ فقط** (`services/admin_search.py`) — و`User` مضمومٌ هنا الآن
    # **وواحدٌ لواحد** (كبتنٌ واحدٌ لكلِّ سلفة) فلا يضاعف صفّاً ولا يمسّ الصفحة
    term = admin_search.normalize(q)
    if term is not None:
        pattern = admin_search.like(term)
        stmt = stmt.where(or_(User.name.ilike(pattern), User.phone.ilike(pattern)))
    rows = (await session.execute(stmt.limit(limit).offset(offset))).all()
    out: list[AdminAdvanceOut] = []
    for row, owner in rows:
        paid = await advances_service.repaid_amount(session, row.id)
        out.append(
            AdminAdvanceOut(
                **AdvanceOut.model_validate(row).model_dump(),
                driver_name=owner.name,
                driver_phone=owner.phone,
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
    payload: AdminAdvanceIn, admin: UsersManager, session: DbSession
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
    admin: UsersManager,
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
    admin: UsersManager,
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


# ------------------------------------- دَينُ الكبتن (الترحيلة `0061`)
#
# **ثلاثةُ أبوابٍ للوحة**: تقرأ المستحقّات، وتؤكّد سداداً وصل، وتشطب بسبب.
# **ولا بابَ يكتب دَيناً بيد**: النشأةُ من التسوية وحدَها — ومن كتب دَيناً
# بيده كتب رقماً لا رحلةَ خلفه.


@router.get("/drivers/debts", response_model=list[AdminDebtOut])
async def list_driver_debts(
    _: UsersManager,
    session: DbSession,
    status: DriverDebtStatus | None = None,
    driver_id: uuid.UUID | None = Query(
        default=None, description="مستحقّاتُ كبتنٍ بعينه — للملفِّ الشخصيّ (§37)"
    ),
    q: str | None = Query(default=None, max_length=120, description="اسمُ الكبتن أو رقمُه"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AdminDebtOut]:
    """المستحقّاتُ ومعها أصحابُها — صفحةٌ محدودةٌ لا جدولٌ كامل.

    **و`driver_id` مرشِّحٌ كـ`q`** (§37): الملفُّ الشخصيُّ يقرأ من هذا الباب
    ولا يُبنى له ثانٍ.
    """
    stmt = (
        select(DriverDebt, User)
        .join(Driver, Driver.id == DriverDebt.driver_id)
        .join(User, User.id == Driver.user_id)
        .order_by(DriverDebt.created_at.desc())
    )
    if status is not None:
        stmt = stmt.where(DriverDebt.status == status)
    if driver_id is not None:
        stmt = stmt.where(DriverDebt.driver_id == driver_id)
    # **مرشِّحٌ فقط**: `User` مضمومٌ في هذا الاستعلام أصلاً — **والضمُّ واحدٌ
    # لواحد** (كبتنٌ واحدٌ لكلِّ دَين) فلا يضاعف صفّاً ولا يمسّ حدَّ الصفحة
    term = admin_search.normalize(q)
    if term is not None:
        pattern = admin_search.like(term)
        stmt = stmt.where(or_(User.name.ilike(pattern), User.phone.ilike(pattern)))
    rows = (await session.execute(stmt.limit(limit).offset(offset))).all()
    return [
        AdminDebtOut(
            id=debt.id,
            driver_id=debt.driver_id,
            driver_name=owner.name,
            driver_phone=owner.phone,
            amount=debt.amount,
            collected=debt.collected,
            currency=debt.currency,
            status=debt.status,
            source=debt.source,
            ride_id=debt.ride_id,
            created_at=debt.created_at,
        )
        for debt, owner in rows
    ]


@router.get("/drivers/debts/claims", response_model=list[DebtClaimOut])
async def list_debt_claims(
    _: UsersManager, session: DbSession, country: CountryCode | None = None
) -> list[DebtClaimOut]:
    """مطالباتُ السداد المعلّقة — **ما ينتظر عينَ مشرف**."""
    # **البانِي الواحد** — وبلاه كان المشرفُ يقرأ مطالبةً بلا حسابٍ ولا رمز
    return [
        await cliq_debts.claim_out(session, order)
        for order in await cliq_debts.list_pending(session, country=country)
    ]


@router.post("/drivers/debts/claims/{order_id}/confirm", response_model=DebtClaimOut)
async def confirm_debt_claim(
    order_id: uuid.UUID,
    payload: DebtConfirmIn,
    admin: UsersManager,
    session: DbSession,
) -> DebtClaimOut:
    """**المشرفُ يكتب ما وصل فعلاً** — والناقصُ يُقبل ويُنقص الدَّين."""
    order, _applied = await cliq_debts.confirm_payment(
        session, order_id=order_id, actor=admin, credited=payload.credited
    )
    out = await cliq_debts.claim_out(session, order)
    await session.commit()
    return out


@router.post("/drivers/debts/{debt_id}/writeoff", response_model=AdminDebtOut)
async def write_off_debt(
    debt_id: uuid.UUID,
    payload: DebtWriteOffIn,
    admin: UsersManager,
    session: DbSession,
) -> AdminDebtOut:
    """شطبٌ بقرارٍ إداريٍّ **بسببٍ مكتوب** — ويُرفع المنعُ إن صفا حسابه."""
    debt = await session.get(DriverDebt, debt_id)
    if debt is None:
        raise NotFound("المستحقّ غير موجود")
    driver = await session.get(Driver, debt.driver_id)
    owner = await session.get(User, driver.user_id)
    await debts_service.write_off(
        session, debt=debt, actor=admin, reason=payload.reason
    )
    # **والشطبُ سدادٌ في أثره** — فمن صفا حسابُه يعود إلى العمل في المسار نفسِه
    await debts_service.refresh_block(
        session, driver=driver, country=owner.country_code
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="driver_debt",
        entity_id=debt.id,
        details={"action": "write_off", "reason": payload.reason},
    )
    await session.commit()
    return AdminDebtOut(
        id=debt.id,
        driver_id=debt.driver_id,
        driver_name=owner.name,
        driver_phone=owner.phone,
        amount=debt.amount,
        collected=debt.collected,
        currency=debt.currency,
        status=debt.status,
        source=debt.source,
        ride_id=debt.ride_id,
        created_at=debt.created_at,
    )


# ═══════════════ مصفوفةُ الصلاحيات (البند ٥، §39٫٥)


@router.get("/permissions", response_model=list[AdminPermissionsOut])
async def list_admin_permissions(
    _staff: StaffUser, session: DbSession
) -> list[AdminPermissionsOut]:
    """من يملك ماذا — **وما يُقرأ هو ما يحكم**، لا جدولٌ ثابتٌ في شاشة.

    **وكانت الشاشةُ تعرض مصفوفةً مكتوبةً بيد** (`Users.tsx` للقراءة فقط):
    **جدولٌ يصف نيّةً لا واقعاً**، ويفترق عن `core/deps` أوّلَ تعديل.

    **والغيابُ يُقرأ افتراضَ الدور** لا «لا يملك شيئاً» — فالحقلُ `explicit`
    يقول أيّهما، **وبغيره يظنّ القارئُ أن مشرفاً بلا صفوفٍ بلا صلاحيات**.
    """
    staff = list(
        await session.scalars(
            select(User)
            .where(has_role_clause(UserRole.ADMIN) | has_role_clause(UserRole.SUPPORT))
            .order_by(User.created_at)
        )
    )
    rows: list[AdminPermissionsOut] = []
    for member in staff:
        explicit = set(
            await session.scalars(
                select(AdminPermissionGrant.permission).where(
                    AdminPermissionGrant.user_id == member.id
                )
            )
        )
        rows.append(
            AdminPermissionsOut(
                user_id=member.id,
                name=member.name,
                roles=list(member.roles),
                permissions=sorted(
                    p.value for p in await permissions_service.for_user(session, member)
                ),
                explicit=bool(explicit),
            )
        )
    return rows


@router.put("/permissions/{user_id}", response_model=AdminPermissionsOut)
async def set_admin_permissions(
    user_id: uuid.UUID,
    payload: AdminPermissionsIn,
    admin: PermissionsManager,
    session: DbSession,
) -> AdminPermissionsOut:
    """يكتب مجموعةَ مشرفٍ كاملةً — **استبدالٌ لا إضافة**، وبثلاثة حرّاس.

    **والحرّاسُ في الخدمة لا هنا**: بابٌ ثانٍ يُضاف غداً يجدها مطبَّقةً،
    **وشرطٌ في موجّهٍ يُنسى في ثاني موجّه**.
    """
    target = await session.get(User, user_id)
    if target is None:
        raise NotFound("الحساب غير موجود")

    before = sorted(
        p.value for p in await permissions_service.for_user(session, target)
    )
    after = await permissions_service.set_for_user(
        session,
        target=target,
        actor=admin,
        permissions={AdminPermission(value) for value in payload.permissions},
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="admin_permissions",
        entity_id=target.id,
        changes={
            "permissions": {
                "before": ", ".join(before),
                "after": ", ".join(sorted(p.value for p in after)),
            }
        },
    )
    await session.commit()
    return AdminPermissionsOut(
        user_id=target.id,
        name=target.name,
        roles=list(target.roles),
        permissions=sorted(p.value for p in after),
        explicit=True,
    )
