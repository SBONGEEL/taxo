from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.deps import AdminUser, DbSession, StaffUser
from app.core.exceptions import Conflict, InvalidInput, NotFound
from app.models.audit import AdminAuditLog
from app.models.cancellation import CancellationSetting
from app.models.commission import CommissionSetting
from app.models.enums import AuditAction, CountryCode
from app.models.pricing import PricingRule
from app.models.subscription import SubscriptionPlan
from app.models.user import User
from app.models.payment_setting import PaymentSetting
from app.models.wallet_setting import WalletSetting
from app.schemas.audit import AuditLogOut
from app.schemas.cancellation import (
    CancellationSettingOut,
    CancellationSettingUpdate,
)
from app.schemas.settings import (
    CommissionSettingOut,
    CommissionSettingUpdate,
    CountryFeatureFlagsOut,
    FeatureFlagUpsert,
    PaymentSettingOut,
    PaymentSettingUpdate,
    PricingRuleCreate,
    PricingRuleOut,
    PricingRuleUpdate,
    SubscriptionPlanCreate,
    SubscriptionPlanOut,
    SubscriptionPlanUpdate,
)
from app.models.advance import AdvanceSetting
from app.schemas.driver import AdvanceSettingOut, AdvanceSettingUpdate
from app.schemas.wallet import WalletSettingOut, WalletSettingUpdate
from app.services import audit, settings_service

router = APIRouter(prefix="/admin/settings", tags=["admin"])


def _apply_updates(instance: object, changes: dict[str, Any]) -> list[str]:
    """يطبّق الحقول المرسلة فقط ويعيد أسماء ما تغيّر فعلاً."""
    changed = []
    for field, value in changes.items():
        if getattr(instance, field) != value:
            setattr(instance, field, value)
            changed.append(field)
    return changed


async def _flush(session: AsyncSession, *, conflict_message: str) -> None:
    """flush مبكر للحصول على المُعرّف قبل قيد التدقيق — يترجم تعارض القيود."""
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict(conflict_message) from exc


async def _commit(
    session: AsyncSession,
    instance: object | None = None,
    *,
    conflict_message: str = "تعارض في البيانات",
) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict(conflict_message) from exc

    if instance is not None:
        # `updated_at` يُحسب في SQL (onupdate) فتبقى القيمة منتهية بعد التحديث
        await session.refresh(instance)


# ---------------------------------------------------------------- التسعير


@router.get("/pricing", response_model=list[PricingRuleOut])
async def list_pricing_rules(
    _staff: StaffUser, session: DbSession, country_code: CountryCode | None = None
) -> list[PricingRuleOut]:
    stmt = select(PricingRule).order_by(
        PricingRule.country_code, PricingRule.vehicle_category
    )
    if country_code is not None:
        stmt = stmt.where(PricingRule.country_code == country_code)
    rules = (await session.scalars(stmt)).all()
    return [PricingRuleOut.model_validate(rule) for rule in rules]


@router.post(
    "/pricing", response_model=PricingRuleOut, status_code=status.HTTP_201_CREATED
)
async def create_pricing_rule(
    payload: PricingRuleCreate, admin: AdminUser, session: DbSession
) -> PricingRuleOut:
    rule = PricingRule(**payload.model_dump())
    session.add(rule)
    await _flush(session, conflict_message="توجد تسعيرة لهذه الدولة والفئة مسبقاً")
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="pricing_rule",
        entity_id=rule.id,
        details={
            "country_code": payload.country_code.value,
            "vehicle_category": payload.vehicle_category.value,
        },
    )
    await _commit(session, rule)
    return PricingRuleOut.model_validate(rule)


@router.patch("/pricing/{rule_id}", response_model=PricingRuleOut)
async def update_pricing_rule(
    rule_id: uuid.UUID,
    payload: PricingRuleUpdate,
    admin: AdminUser,
    session: DbSession,
) -> PricingRuleOut:
    rule = await session.get(PricingRule, rule_id)
    if rule is None:
        raise NotFound("التسعيرة غير موجودة")

    changed = _apply_updates(rule, payload.model_dump(exclude_unset=True))
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="pricing_rule",
        entity_id=rule.id,
        details={"changed_fields": changed},
    )
    await _commit(session, rule)
    return PricingRuleOut.model_validate(rule)


@router.delete("/pricing/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pricing_rule(
    rule_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> None:
    rule = await session.get(PricingRule, rule_id)
    if rule is None:
        raise NotFound("التسعيرة غير موجودة")

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.DELETE,
        entity_type="pricing_rule",
        entity_id=rule.id,
        details={
            "country_code": rule.country_code.value,
            "vehicle_category": rule.vehicle_category.value,
        },
    )
    await session.delete(rule)
    await _commit(session)


# ------------------------------------------------------------ مفاتيح الميزات


@router.get("/feature-flags", response_model=list[CountryFeatureFlagsOut])
async def list_feature_flags(
    _staff: StaffUser, session: DbSession
) -> list[CountryFeatureFlagsOut]:
    return [
        CountryFeatureFlagsOut(
            country_code=country,
            flags=await settings_service.get_flags(session, country),
        )
        for country in CountryCode
    ]


@router.put("/feature-flags", response_model=CountryFeatureFlagsOut)
async def upsert_feature_flag(
    payload: FeatureFlagUpsert, admin: AdminUser, session: DbSession
) -> CountryFeatureFlagsOut:
    """`admin` وحده — و**إطفاءُ مفتاحٍ حارس يشترط سبباً مكتوباً**.

    `otp_verification_enabled` ليس ميزةً تُجرَّب: إطفاؤه يسمح بإنشاء حساباتٍ
    بأرقامٍ لم يملكها أصحابُها. فهو إجراءُ طوارئٍ يُسأل عنه، وسجلُّ تدقيقٍ
    يقول «أُطفئ» بلا «لماذا» نصفُ سجل (SPEC القسم 13/6).
    """
    if (
        payload.feature_key in settings_service.DEFAULT_ENABLED_FLAGS
        and not payload.enabled
        and not (payload.reason or "").strip()
    ):
        raise InvalidInput(
            "إطفاء مفتاح التحقق إجراء طوارئ — اكتب سببه (8 أحرف على الأقل)"
        )

    await settings_service.set_flag(
        session,
        country_code=payload.country_code,
        feature_key=payload.feature_key,
        enabled=payload.enabled,
        actor=admin,
        reason=payload.reason,
    )
    await _commit(session)
    return CountryFeatureFlagsOut(
        country_code=payload.country_code,
        flags=await settings_service.get_flags(session, payload.country_code),
    )


# ------------------------------------------------------------------ العمولة


@router.get("/commission", response_model=list[CommissionSettingOut])
async def list_commission_settings(
    _staff: StaffUser, session: DbSession
) -> list[CommissionSettingOut]:
    settings_rows = (
        await session.scalars(
            select(CommissionSetting).order_by(CommissionSetting.country_code)
        )
    ).all()
    return [CommissionSettingOut.model_validate(row) for row in settings_rows]


@router.patch("/commission/{country_code}", response_model=CommissionSettingOut)
async def update_commission_setting(
    country_code: CountryCode,
    payload: CommissionSettingUpdate,
    admin: AdminUser,
    session: DbSession,
) -> CommissionSettingOut:
    """تعديل العمولة — يسري على الرحلات الجديدة فقط.

    هذا هو المكان الوحيد لتفعيل العمولة؛ لا مفتاح مقابل في `feature_flags`.
    الرحلات القائمة تحمل `commission_percent_at_ride` مجمّدة (SPEC القسم 8).
    """
    setting = await settings_service.get_or_create_commission(session, country_code)
    changed = _apply_updates(setting, payload.model_dump(exclude_unset=True))

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="commission_setting",
        entity_id=setting.id,
        details={"country_code": country_code.value, "changed_fields": changed},
    )
    await _commit(session, setting)
    return CommissionSettingOut.model_validate(setting)


# ------------------------------------------------------------ خطط الاشتراك


@router.get("/subscription-plans", response_model=list[SubscriptionPlanOut])
async def list_subscription_plans(
    _staff: StaffUser, session: DbSession, country_code: CountryCode | None = None
) -> list[SubscriptionPlanOut]:
    stmt = select(SubscriptionPlan).order_by(
        SubscriptionPlan.country_code, SubscriptionPlan.price
    )
    if country_code is not None:
        stmt = stmt.where(SubscriptionPlan.country_code == country_code)
    plans = (await session.scalars(stmt)).all()
    return [SubscriptionPlanOut.model_validate(plan) for plan in plans]


@router.post(
    "/subscription-plans",
    response_model=SubscriptionPlanOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_subscription_plan(
    payload: SubscriptionPlanCreate, admin: AdminUser, session: DbSession
) -> SubscriptionPlanOut:
    plan = SubscriptionPlan(
        **payload.model_dump(),
        currency=currency_for_country(payload.country_code),
    )
    session.add(plan)
    await _flush(session, conflict_message="توجد خطة بهذا الاسم في نفس الدولة")
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="subscription_plan",
        entity_id=plan.id,
        details={"country_code": payload.country_code.value, "name": payload.name},
    )
    await _commit(session, plan)
    return SubscriptionPlanOut.model_validate(plan)


@router.patch("/subscription-plans/{plan_id}", response_model=SubscriptionPlanOut)
async def update_subscription_plan(
    plan_id: uuid.UUID,
    payload: SubscriptionPlanUpdate,
    admin: AdminUser,
    session: DbSession,
) -> SubscriptionPlanOut:
    plan = await session.get(SubscriptionPlan, plan_id)
    if plan is None:
        raise NotFound("الخطة غير موجودة")

    changed = _apply_updates(plan, payload.model_dump(exclude_unset=True))
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="subscription_plan",
        entity_id=plan.id,
        details={"changed_fields": changed},
    )
    await _commit(session, plan, conflict_message="توجد خطة بهذا الاسم في نفس الدولة")
    return SubscriptionPlanOut.model_validate(plan)


@router.delete(
    "/subscription-plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_subscription_plan(
    plan_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> None:
    plan = await session.get(SubscriptionPlan, plan_id)
    if plan is None:
        raise NotFound("الخطة غير موجودة")

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.DELETE,
        entity_type="subscription_plan",
        entity_id=plan.id,
        details={"country_code": plan.country_code.value, "name": plan.name},
    )
    await session.delete(plan)
    await _commit(session)


# ------------------------------------------------------------ حدود المحفظة


@router.get("/wallet", response_model=list[WalletSettingOut])
async def list_wallet_settings(
    _staff: StaffUser, session: DbSession
) -> list[WalletSettingOut]:
    rows = (
        await session.scalars(select(WalletSetting).order_by(WalletSetting.country_code))
    ).all()
    return [WalletSettingOut.model_validate(row) for row in rows]


@router.patch("/wallet/{country_code}", response_model=WalletSettingOut)
async def update_wallet_settings(
    country_code: CountryCode,
    payload: WalletSettingUpdate,
    admin: AdminUser,
    session: DbSession,
) -> WalletSettingOut:
    """حدود التحويل والسحب لكل دولة (SPEC القسم 7/9/13.6).

    الصف يُنشأ بأصفار عند أول تعديل؛ صفرٌ في حدود التحويل يعني «غير مضبوط»
    فيُرفض التحويل حتى تُدخل الإدارة قيمة صريحة.
    """
    setting = await settings_service.get_or_create_wallet_settings(
        session, country_code
    )
    changed = _apply_updates(setting, payload.model_dump(exclude_unset=True))

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="wallet_setting",
        entity_id=setting.id,
        details={"country_code": country_code.value, "changed_fields": changed},
    )
    await _commit(session, setting)
    return WalletSettingOut.model_validate(setting)


# ------------------------------------------------------- سياسة السلف


@router.get("/advances", response_model=list[AdvanceSettingOut])
async def list_advance_settings(
    _staff: StaffUser, session: DbSession
) -> list[AdvanceSettingOut]:
    rows = (
        await session.scalars(
            select(AdvanceSetting).order_by(AdvanceSetting.country_code)
        )
    ).all()
    return [AdvanceSettingOut.model_validate(row) for row in rows]


@router.patch("/advances/{country_code}", response_model=AdvanceSettingOut)
async def update_advance_settings(
    country_code: CountryCode,
    payload: AdvanceSettingUpdate,
    admin: AdminUser,
    session: DbSession,
) -> AdvanceSettingOut:
    """سياسةُ السلف لكل دولة (البند ١٥).

    **وما يُعدَّل هنا يحكم ما يأتي لا ما صُدر**: مهلةُ التحصيل مجمَّدةٌ على كل
    سلفةٍ لحظةَ صرفها — كنسبة العمولة على الرحلة تماماً. فتقصيرُ المهلة اليوم
    لا يُقصّر مهلةً ينظر إليها كبتنٌ في شاشته الآن.
    """
    setting = await session.scalar(
        select(AdvanceSetting).where(AdvanceSetting.country_code == country_code)
    )
    if setting is None:
        setting = AdvanceSetting(country_code=country_code)
        session.add(setting)
        await session.flush()
    changed = _apply_updates(setting, payload.model_dump(exclude_unset=True))

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="advance_setting",
        entity_id=setting.id,
        details={"country_code": country_code.value, "changed_fields": changed},
    )
    await _commit(session, setting)
    return AdvanceSettingOut.model_validate(setting)


# --------------------------------------------------- سياسة رسم الإلغاء


@router.get("/cancellation", response_model=list[CancellationSettingOut])
async def list_cancellation_settings(
    _staff: StaffUser, session: DbSession
) -> list[CancellationSettingOut]:
    rows = (
        await session.scalars(
            select(CancellationSetting).order_by(CancellationSetting.country_code)
        )
    ).all()
    return [CancellationSettingOut.model_validate(row) for row in rows]


@router.patch("/cancellation/{country_code}", response_model=CancellationSettingOut)
async def update_cancellation_settings(
    country_code: CountryCode,
    payload: CancellationSettingUpdate,
    admin: AdminUser,
    session: DbSession,
) -> CancellationSettingOut:
    """سياسةُ رسم الإلغاء لكل دولة (`design/CANCELLATION-FEE.md`).

    **وما يُعدَّل هنا يحكم ما يأتي لا ما وقع**: مبلغُ الرسم مجمَّدٌ على الرحلة
    لحظةَ إلغائها، ومهلةُ الحامل مجمَّدةٌ لحظةَ قبضه — فتقصيرُ المهلة اليوم لا
    يُقصّر مهلةً ينظر إليها كبتنٌ في شاشته الآن.

    **واثنان يُقرآن حيّين عمداً**: حدُّ الإيقاف ومدّةُ الدَّين القديم. كلاهما
    **سؤالٌ عن سياسةٍ تُراجَع** لا وعدٌ قيل لأحد، فرفعُ الحدِّ يُطلق سراحَ من
    كان ممنوعاً بلا لمس صفٍّ واحد — قاعدةُ «flagged» في تقارير عدم التطابق.
    """
    setting = await session.get(CancellationSetting, country_code)
    if setting is None:
        setting = CancellationSetting(country_code=country_code)
        session.add(setting)
        await session.flush()
    changed = _apply_updates(setting, payload.model_dump(exclude_unset=True))

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="cancellation_setting",
        entity_id=None,
        details={"country_code": country_code.value, "changed_fields": changed},
    )
    await _commit(session, setting)
    return CancellationSettingOut.model_validate(setting)


# ------------------------------------------------------- سياسات الدفع


@router.get("/payments", response_model=list[PaymentSettingOut])
async def list_payment_settings(
    _staff: StaffUser, session: DbSession
) -> list[PaymentSettingOut]:
    rows = (
        await session.scalars(
            select(PaymentSetting).order_by(PaymentSetting.country_code)
        )
    ).all()
    return [PaymentSettingOut.model_validate(row) for row in rows]


@router.patch("/payments/{country_code}", response_model=PaymentSettingOut)
async def update_payment_settings(
    country_code: CountryCode,
    payload: PaymentSettingUpdate,
    admin: AdminUser,
    session: DbSession,
) -> PaymentSettingOut:
    """مهلةُ تأكيد حوالة كليك لكل دولة (SPEC القسم 6.2/13.6).

    **ولا أثرَ رجعياً**: المهلة تُجمَّد على الدفعة لحظة إدخال المرجع، فتعديلُها
    هنا يحكم ما يأتي بعده لا ما هو معلّقٌ الآن — كبتنٌ رأى «يبقى ٦ ساعات» لا
    يجوز أن تتحول تحته إلى ساعة.
    """
    setting = await settings_service.get_or_create_payment_settings(
        session, country_code
    )
    changed = _apply_updates(setting, payload.model_dump(exclude_unset=True))

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="payment_setting",
        entity_id=setting.id,
        details={"country_code": country_code.value, "changed_fields": changed},
    )
    await _commit(session, setting)
    return PaymentSettingOut.model_validate(setting)


# ------------------------------------------------------------- سجل التدقيق


@router.get("/audit-logs", response_model=list[AuditLogOut])
async def list_audit_logs(
    _staff: StaffUser,
    session: DbSession,
    entity_type: str | None = None,
    action: AuditAction | None = None,
    actor_id: uuid.UUID | None = None,
    entity_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AuditLogOut]:
    """سجلُّ التدقيق (SPEC القسم 14) — يُقرأ ولا يُكتب من مسار.

    كلُّ قيدٍ فيه كتبته **معاملةُ التغيير نفسها**: لا بابَ هنا يضيف قيداً ولا
    يعدّله ولا يحذفه — سجلٌّ يُكتب من الخارج سجلٌّ يمكن أن يقول غير ما جرى.

    والفلاترُ الأربع هي أسئلة القراءة الحقيقية: ماذا جرى على **هذا العنصر**،
    وماذا فعل **هذا المشرف**، وأيُّ نوعٍ من الإجراءات. و`entity_id` هو ما
    يجعل درجَ سائقٍ يفتح تاريخَه بدل أن يُبحث عنه في قائمةٍ عامة.
    """
    stmt = (
        select(AdminAuditLog, User.name)
        .outerjoin(User, AdminAuditLog.actor_id == User.id)
        .order_by(AdminAuditLog.created_at.desc())
    )
    if entity_type is not None:
        stmt = stmt.where(AdminAuditLog.entity_type == entity_type)
    if action is not None:
        stmt = stmt.where(AdminAuditLog.action == action)
    if actor_id is not None:
        stmt = stmt.where(AdminAuditLog.actor_id == actor_id)
    if entity_id is not None:
        stmt = stmt.where(AdminAuditLog.entity_id == entity_id)

    rows = (await session.execute(stmt.limit(limit).offset(offset))).all()
    return [
        AuditLogOut.model_validate(entry).model_copy(update={"actor_name": name})
        for entry, name in rows
    ]
