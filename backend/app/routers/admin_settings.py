from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, File, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.deps import SettingsWriter, DbSession, StaffUser
from app.core.exceptions import Conflict, InvalidInput, NotFound
from app.models.audit import AdminAuditLog
from app.models.cancellation import CancellationSetting
from app.models.commission import CommissionSetting
from app.models.map_setting import MapSetting
from app.models.otp_setting import OtpSetting
from app.models.enums import AuditAction, CountryCode, FeatureKey, ProviderKey
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
from app.schemas.storefront import (
    AdminPromoBannerOut,
    AdminServiceTileOut,
    PromoBannerIn,
    PromoBannerPatch,
    ServiceTileIn,
    ServiceTilePatch,
)
from app.services import storefront
from app.schemas.settings import (
    DispatchSettingOut,
    DispatchSettingUpdate,
    CommissionSettingOut,
    OtpExhaustedOut,
    MapSettingOut,
    MapSettingUpdate,
    OtpSettingOut,
    OtpSettingUpdate,
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
from app.models.dispatch_setting import DispatchSetting
from app.models.storefront import PromoBanner, ServiceTile
from app.schemas.driver import AdvanceSettingOut, AdvanceSettingUpdate
from app.schemas.wallet import WalletSettingOut, WalletSettingUpdate
from app.core.deps import RedisDep
from app.core import storage
from app.services import admin_search, audit, money_guards, otp_limits, settings_service
from app.services.providers.credentials import provider_is_active

router = APIRouter(prefix="/admin/settings", tags=["admin"])


def _apply_updates(instance: object, changes: dict[str, Any]) -> dict[str, dict]:
    """يطبّق الحقول المرسلة فقط **ويعيد قبلَ وبعدَ لكلِّ ما تغيّر** (البند ٤).

    **وبيتُه `services/audit.py` لا هنا**: كان يعيد **أسماءً بلا قيم**، وقرارُ
    المالك 2026-09-02 أن يُختم «**من ومتى والقيمةُ قبل وبعد**». **ونقلُه إلى
    الخدمة يجعل كلَّ موجّهٍ يعدّل يصله** — وبقاؤه هنا كان يعني نسخةً في ثاني
    موجّه.
    """
    return audit.apply_changes(instance, changes)


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
    payload: PricingRuleCreate, admin: SettingsWriter, session: DbSession
) -> PricingRuleOut:
    await money_guards.require_pricing_writes(
        session, actor=admin, country_code=payload.country_code
    )
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
    admin: SettingsWriter,
    session: DbSession,
) -> PricingRuleOut:
    rule = await session.get(PricingRule, rule_id)
    if rule is None:
        raise NotFound("التسعيرة غير موجودة")

    await money_guards.require_pricing_writes(
        session, actor=admin, country_code=rule.country_code, entity_id=rule.id
    )
    changed = _apply_updates(rule, payload.model_dump(exclude_unset=True))
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="pricing_rule",
        entity_id=rule.id,
        changes=changed,
    )
    await _commit(session, rule)
    return PricingRuleOut.model_validate(rule)


@router.delete("/pricing/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pricing_rule(
    rule_id: uuid.UUID, admin: SettingsWriter, session: DbSession
) -> None:
    rule = await session.get(PricingRule, rule_id)
    if rule is None:
        raise NotFound("التسعيرة غير موجودة")

    await money_guards.require_pricing_writes(
        session, actor=admin, country_code=rule.country_code, entity_id=rule.id
    )
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
    payload: FeatureFlagUpsert, admin: SettingsWriter, session: DbSession
) -> CountryFeatureFlagsOut:
    """`admin` وحده — و**إطفاءُ مفتاحٍ حارس يشترط سبباً مكتوباً**.

    `otp_verification_enabled` ليس ميزةً تُجرَّب: إطفاؤه يسمح بإنشاء حساباتٍ
    بأرقامٍ لم يملكها أصحابُها. فهو إجراءُ طوارئٍ يُسأل عنه، وسجلُّ تدقيقٍ
    يقول «أُطفئ» بلا «لماذا» نصفُ سجل (SPEC القسم 13/6).

    **والشرطُ على `GUARDED_FLAGS` لا على `DEFAULT_ENABLED_FLAGS`**: الثانيةُ
    تقول كيف يُقرأ الغياب، والأولى تقول ما ثمنُ الإطفاء — ومنذ دخول
    `country_visible` لم تعودا واحدة. وكلُّ تبديلٍ يُسجَّل في التدقيق سبباً
    كان أو لا (`settings_service.set_flag`).
    """
    if (
        payload.feature_key in settings_service.GUARDED_FLAGS
        and not payload.enabled
        and not (payload.reason or "").strip()
    ):
        # **ولا يُسمّى مفتاحٌ بعينه**: الشرطُ على `GUARDED_FLAGS` كلِّها، وكان
        # النصُّ يقول «مفتاح التحقق» فيقرؤه من جمّد التسعيرَ جملةً لا علاقةَ
        # لها بما ضغط — وهي بعينها العلّةُ المكتوبةُ فوق `GUARDED_FLAGS`.
        raise InvalidInput(
            "إطفاء مفتاحٍ حارس إجراء طوارئ — اكتب سببه (8 أحرف على الأقل)"
        )

    # **ومفتاحُ البريد لا يُشعَل بلا مُرسِلٍ فعّال** (قرارُ المالك 2026-08-31).
    #
    # **وهو شرطٌ في الاتجاه المعاكس للحرّاس**: أولئك يشترطون سبباً **للإطفاء**،
    # وهذا يشترط عقداً **للإشعال**. **والعلّةُ أن المفتاحَ يرسم باباً**:
    # التطبيقان يقرآن `email_signup` في `/config` فيرسمان «سجّل ببريدك»،
    # **ومفتاحٌ مشتعلٌ بلا مُرسِلٍ يرسم باباً يسقط عند أول ضغطة** — وهو «زرٌّ
    # بلا باب»، وهو أسوأُ من غياب الزرّ: من لا يراه يسجّل بالهاتف، ومن يراه
    # يجرّب ويفشل ويظنّ العطبَ في بريده.
    #
    # **ولا يُقاس على وجود صفِّ عقدٍ بل على فعّاليّته** — `provider_is_active`:
    # عقدٌ مُدخَلٌ ومطفأٌ لا يرسل شيئاً.
    if (
        payload.feature_key == FeatureKey.EMAIL_OTP_ENABLED
        and payload.enabled
        and not await provider_is_active(session, ProviderKey.EMAIL)
    ):
        raise InvalidInput(
            "لا يُشعَل التحقّق بالبريد بلا عقدِ مُرسِلٍ فعّال — "
            "أدخِل العقد من صفحة العقود وفعّله، ثم أشعِل المفتاح"
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
    admin: SettingsWriter,
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
        details={"country_code": country_code.value},
        changes=changed,
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
    payload: SubscriptionPlanCreate, admin: SettingsWriter, session: DbSession
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
    admin: SettingsWriter,
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
        changes=changed,
    )
    await _commit(session, plan, conflict_message="توجد خطة بهذا الاسم في نفس الدولة")
    return SubscriptionPlanOut.model_validate(plan)


@router.delete(
    "/subscription-plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_subscription_plan(
    plan_id: uuid.UUID, admin: SettingsWriter, session: DbSession
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
    admin: SettingsWriter,
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
        details={"country_code": country_code.value},
        changes=changed,
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
    admin: SettingsWriter,
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
        details={"country_code": country_code.value},
        changes=changed,
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
    admin: SettingsWriter,
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
        details={"country_code": country_code.value},
        changes=changed,
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
    admin: SettingsWriter,
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
        details={"country_code": country_code.value},
        changes=changed,
    )
    await _commit(session, setting)
    return PaymentSettingOut.model_validate(setting)


# ----------------------------------------------- سقوف طلب رمز التحقق


@router.get("/map", response_model=list[MapSettingOut])
async def list_map_settings(
    _staff: StaffUser, session: DbSession
) -> list[MapSettingOut]:
    """حدودُ خريطةِ الراكب لكلِّ سوق — **لا حدودُ التوزيع**."""
    rows = (
        await session.scalars(select(MapSetting).order_by(MapSetting.country_code))
    ).all()
    return [MapSettingOut.model_validate(row) for row in rows]


@router.patch("/map/{country_code}", response_model=MapSettingOut)
async def update_map_settings(
    country_code: CountryCode,
    payload: MapSettingUpdate,
    admin: SettingsWriter,
    session: DbSession,
) -> MapSettingOut:
    """كم سيارةً يرى الراكبُ وإلى أيِّ بُعد (قرارُ المالك 2026-08-22).

    **ولا تمسّ التوزيعَ بحال**: `dispatch` يقرأ ثوابتَ §5.3 من
    `services/geo.py`، فمشرفٌ يوسّع هنا يغيّر **ما يُرسم** لا **من يصله
    الطلب**. وخلطُ الاثنين يجعل حقلَ عرضٍ يحرّك سوقاً.

    **وتُقرأ حيّةً**: التوسيعُ يظهر في أول تحديثٍ للخريطة بلا نشرٍ ولا بناء.
    """
    setting = await session.get(MapSetting, country_code)
    if setting is None:
        setting = MapSetting(country_code=country_code)
        session.add(setting)
        await session.flush()
    changed = _apply_updates(setting, payload.model_dump(exclude_unset=True))

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="map_setting",
        entity_id=None,
        details={"country_code": country_code.value},
        changes=changed,
    )
    await _commit(session, setting)
    return MapSettingOut.model_validate(setting)


@router.get("/otp", response_model=list[OtpSettingOut])
async def list_otp_settings(
    _staff: StaffUser, session: DbSession
) -> list[OtpSettingOut]:
    rows = (
        await session.scalars(select(OtpSetting).order_by(OtpSetting.country_code))
    ).all()
    return [OtpSettingOut.model_validate(row) for row in rows]


@router.patch("/otp/{country_code}", response_model=OtpSettingOut)
async def update_otp_settings(
    country_code: CountryCode,
    payload: OtpSettingUpdate,
    admin: SettingsWriter,
    session: DbSession,
) -> OtpSettingOut:
    """سقوفُ طلب الرمز لكل دولة (قرارُ المالك 2026-08-16).

    **وتسري على القنوات كلِّها لا على واتساب وحدها**: السقفُ سياسةُ حسابٍ
    يُقاس على الرقم، فمن استنفد محاولاته لا يلتفّ عليها بتبديل القناة.

    **وتُقرأ حيّةً لا مجمَّدة**: توسيعُها هنا يُطلق سراحَ من كان محجوزاً في
    الحال، وتضييقُها يسري على الطلب التالي — وهي قاعدةُ حدِّ الإيقاف نفسُها.
    ولا يمسّ التعديلُ **حجزاً قائماً** (`lockout`): مهلتُه كُتبت بعمرها لحظةَ
    وقوعها، ومن قيل له «بعد ساعة» لا تُقصَّر تحته ولا تُطال.
    """
    setting = await session.get(OtpSetting, country_code)
    if setting is None:
        setting = OtpSetting(country_code=country_code)
        session.add(setting)
        await session.flush()
    changed = _apply_updates(setting, payload.model_dump(exclude_unset=True))

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="otp_setting",
        entity_id=None,
        details={"country_code": country_code.value},
        changes=changed,
    )
    await _commit(session, setting)
    return OtpSettingOut.model_validate(setting)


@router.get("/otp/exhausted", response_model=OtpExhaustedOut)
async def list_exhausted_phones(
    _staff: StaffUser, redis: RedisDep
) -> OtpExhaustedOut:
    """أرقامُ اليوم التي بلغت سقفاً — **تكرارٌ مشبوهٌ يُرى قبل أن يحرق الرقم**.

    ومصدرُها Redis لا القاعدة: مجموعةٌ بعمر يومين، لأن السؤال «من استنفد
    اليوم» لا «من استنفد يوماً ما» — وجدولٌ يحفظ الثاني ينمو بلا قارئ.
    """
    from datetime import UTC, datetime

    return OtpExhaustedOut(
        day=datetime.now(UTC).date().isoformat(),
        phones=await otp_limits.exhausted_today(redis),
    )


# ------------------------------------------------------------- سجل التدقيق


@router.get("/audit-logs", response_model=list[AuditLogOut])
async def list_audit_logs(
    _staff: StaffUser,
    session: DbSession,
    entity_type: str | None = None,
    action: AuditAction | None = None,
    actor_id: uuid.UUID | None = None,
    entity_id: uuid.UUID | None = None,
    q: str | None = Query(
        default=None, max_length=120, description="اسمُ المشرف أو نوعُ العنصر"
    ),
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
    # **مرشِّحٌ فقط** (`services/admin_search.py`): `User` مضمومٌ هنا أصلاً
    # بـ`outerjoin` واحدٍ لواحد، فالشرطُ عليه لا يضاعف صفّاً.
    # **وقيدٌ بلا مشرفٍ لا يطابق اسماً** — وهو الصحيح: من يبحث باسمٍ يريد فعلَ
    # إنسانٍ لا فعلَ النظام
    term = admin_search.normalize(q)
    if term is not None:
        pattern = admin_search.like(term)
        stmt = stmt.where(
            or_(User.name.ilike(pattern), AdminAuditLog.entity_type.ilike(pattern))
        )

    rows = (await session.execute(stmt.limit(limit).offset(offset))).all()
    return [
        AuditLogOut.model_validate(entry).model_copy(update={"actor_name": name})
        for entry, name in rows
    ]


@router.put("/payments/{country_code}/cliq-qr", response_model=PaymentSettingOut)
async def upload_cliq_qr(
    country_code: CountryCode,
    admin: SettingsWriter,
    session: DbSession,
    file: UploadFile = File(...),
) -> PaymentSettingOut:
    """**صورةُ رمز كليك لهذا السوق — تُرفع ولا تُولَّد** (قرارُ المالك 2026-08-29).

    **ولمَ لا تُولَّد**: رمزُ كليك **يصدره القابض** بحقوله المعيارية —
    `cliq/acquirer.py` يأخذه من جوابه ويرمي إن غاب، **والمحاكي يصنع صيغةً
    مخترعةً للفحص**. فاشتقاقُه من alias يعطي رمزاً **قد لا يقبله أيُّ بنك**،
    **وباركودٌ لا يعمل أسوأُ من غيابه**.

    **وتمرّ بـ`storage.save`** كبقيّة ما يُرفع: يشمّ النوعَ من البايتات ويحدّ
    الحجمَ — **ولا بابَ ثانياً لبايتاتٍ تصل من الشبكة**.
    """
    setting = await settings_service.get_or_create_payment_settings(
        session, country_code
    )
    stored = await storage.save(file, folder=str(setting.id))
    # **`relative_path` لا `path`** — و`StoredFile` لا تحمل الثانيَ أصلاً،
    # فكان هذا السطرُ يرمي `AttributeError` **بعد كتابة الملفّ على القرص**:
    # ٥٠٠ للمشرف، وملفٌّ يتيمٌ لا صفَّ يشير إليه. (قِيس 2026-08-31؛ كلُّ
    # مستدعٍ آخرَ في المشروع يكتب `relative_path`.)
    setting.cliq_qr_path = stored.relative_path
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="payment_setting",
        entity_id=setting.id,
        # **ملفٌّ لا قيمة**: المسارُ تفصيلُ تخزينٍ لا يُكتب في السجلّ
        details={"country_code": country_code.value},
        changes={"cliq_qr_path": {"before": "ملفٌّ سابق", "after": "ملفٌّ جديد"}},
    )
    # **و`_commit` لا `session.commit`** — عطبٌ ثانٍ كان الأولُ يستره: بعد
    # تحديثٍ يبقى `updated_at` منتهياً (يُحسب في SQL بـ`onupdate`)، **فيقرؤه
    # المخطَّطُ خارج السياق** بـ`MissingGreenlet`. ولم يظهر يوماً لأن السطرَ
    # قبله كان يرمي قبل أن يبلغه. **وعطبان يستر أحدهما الآخر يعيشان أطولَ
    # من عطبٍ مفرد.**
    await _commit(session, setting)
    return PaymentSettingOut.model_validate(setting)


# ------------------------------------------------- إعدادات التوزيع (§5.3)


@router.get("/dispatch", response_model=list[DispatchSettingOut])
async def list_dispatch_settings(
    _staff: StaffUser, session: DbSession
) -> list[DispatchSettingOut]:
    """صفوفُ الأسواق المضبوطة — **والغائبُ يعمل بالافتراضيّ ولا يُخترع له صفّ**."""
    rows = (
        await session.scalars(
            select(DispatchSetting).order_by(DispatchSetting.country_code)
        )
    ).all()
    return [DispatchSettingOut.model_validate(row) for row in rows]


@router.patch("/dispatch/{country_code}", response_model=DispatchSettingOut)
async def update_dispatch_settings(
    country_code: CountryCode,
    payload: DispatchSettingUpdate,
    admin: SettingsWriter,
    session: DbSession,
) -> DispatchSettingOut:
    """نمطُ التوزيع ومهلتُه وتبريدُه (§5.3، قرارُ المالك 2026-08-30).

    **وما يُعدَّل هنا لا يمسّ رحلةً جارية**: القواعدُ تُقرأ مرّةً عند بدء
    توزيع الرحلة. **ونصفُ متغيّرٍ أسوأُ من أيِّ الحالين** — رحلةٌ بدأت بثّاً
    فصارت تسلسليّةً في منتصفها تترك دفعةً تحمل بطاقةً لا يُقرأ قبولُها.
    """
    setting = await session.scalar(
        select(DispatchSetting).where(DispatchSetting.country_code == country_code)
    )
    if setting is None:
        setting = DispatchSetting(country_code=country_code)
        session.add(setting)
        await session.flush()

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(setting, field, value)
    await session.flush()

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="dispatch_settings",
        entity_id=setting.id,
        details=payload.model_dump(exclude_unset=True, mode="json"),
    )
    await session.commit()
    return DispatchSettingOut.model_validate(setting)


# ─────────────────── بلاطاتُ الخدمات واللافتات (الترحيلة `0063`) ───────────────
#
# **والحذفُ للمسوّدة وحدَها** (قرارُ المالك 2026-08-31، الترحيلة `0064`):
# **ما عُرض مرّةً يُخفى ولا يُحذف** — حذفُه يمحو شاهداً على ما رآه الناس، ومن
# يقرأ بعد شهرٍ «لمَ ارتفعت الضغطاتُ ذلك الأسبوع» يجد فراغاً.
#
# **وكان مكتوباً هنا «ولا حذفَ» مطلقاً** — وهو ما جعل كلَّ خطأِ كتابةٍ صفّاً
# أبديّاً في جدولٍ يقرؤه المشرف. **والمسوّدةُ ليست شاهداً**: `first_shown_at`
# فارغةٌ تعني أن إنساناً لم يرَها قطّ، **وذلك هو الإذنُ بالحذف**.


@router.get("/service-tiles", response_model=list[AdminServiceTileOut])
async def list_service_tiles(
    _staff: StaffUser, session: DbSession, country: CountryCode | None = None
) -> list[AdminServiceTileOut]:
    """كلُّها **بما فيها المخفيّة** — فالمشرفُ يرى ما أخفاه."""
    return [
        AdminServiceTileOut.model_validate(row)
        for row in await storefront.list_tiles(session, country=country)
    ]


@router.post("/service-tiles", response_model=AdminServiceTileOut, status_code=201)
async def create_service_tile(
    payload: ServiceTileIn, admin: SettingsWriter, session: DbSession
) -> AdminServiceTileOut:
    """**والإشعالُ بلا مقصدٍ مبنيٍّ يُمنع هنا** لا عند ضغط المستخدم.

    **والأيقونةُ من القائمة المقرَّرة**: اسمٌ خارجها كان يرسم `LayoutGrid`
    **صامتاً** — لا خطأَ ولا تحذير — **فلا يعلم المشرفُ أنه أخطأ حتى يفتح
    التطبيق**، وهو «بديلٌ يعمل ويخفي العطبَ الذي بُني له».
    """
    storefront.require_icon(payload.icon)
    storefront.require_destination(
        payload.destination, status=payload.status, audience=payload.audience
    )
    tile = ServiceTile(**payload.model_dump())
    # **وتُختم إن وُلدت فعّالة** — والإنشاءُ إشعالٌ كالتعديل
    storefront.stamp_if_shown(tile)
    session.add(tile)
    await _flush(session, conflict_message="مفتاحُ البلاطة مستعملٌ في هذا السوق")
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="service_tile",
        entity_id=tile.id,
        details=payload.model_dump(mode="json"),
    )
    await session.commit()
    return AdminServiceTileOut.model_validate(tile)


@router.patch("/service-tiles/{tile_id}", response_model=AdminServiceTileOut)
async def update_service_tile(
    tile_id: uuid.UUID,
    payload: ServiceTilePatch,
    admin: SettingsWriter,
    session: DbSession,
) -> AdminServiceTileOut:
    tile = await storefront.get_tile(session, tile_id)
    changes = payload.model_dump(exclude_unset=True)
    storefront.require_icon(changes.get("icon", tile.icon))
    # **يُقاس على ما ستصير إليه لا على ما هي** — فتعديلُ الحال وحدَها إلى
    # `active` بلا مقصدٍ يمرّ لو قِيس على القديم
    storefront.require_destination(
        changes.get("destination", tile.destination),
        status=changes.get("status", tile.status),
        # **والجمهورُ على ما سيصير إليه أيضاً**: تحويلُ بلاطةٍ فعّالةٍ من
        # الراكب إلى الكبتن **يبدّل الجوابَ وحدَه بلا أن يمسّ المقصد**
        audience=changes.get("audience", tile.audience),
    )
    changed = _apply_updates(tile, changes)
    # **بعد التطبيق لا قبله** — الختمُ على ما صارت إليه، والإشعالُ هو القرار
    storefront.stamp_if_shown(tile)
    await session.flush()
    if changed:
        await audit.record(
            session,
            actor=admin,
            action=AuditAction.UPDATE,
            entity_type="service_tile",
            entity_id=tile.id,
            changes=changed,
        )
    await session.commit()
    return AdminServiceTileOut.model_validate(tile)


@router.get("/promo-banners", response_model=list[AdminPromoBannerOut])
async def list_promo_banners(
    _staff: StaffUser, session: DbSession, country: CountryCode | None = None
) -> list[AdminPromoBannerOut]:
    """كلُّها **ومنها المنتهية** — فالمشرفُ يرى ما مضى ويعيد استعماله."""
    return [
        AdminPromoBannerOut.model_validate(row)
        for row in await storefront.list_banners(session, country=country)
    ]


@router.post("/promo-banners", response_model=AdminPromoBannerOut, status_code=201)
async def create_promo_banner(
    payload: PromoBannerIn, admin: SettingsWriter, session: DbSession
) -> AdminPromoBannerOut:
    """**ولافتةٌ مقصدُها غير مبنيٍّ لا تُقبل** — والنافذةُ إلزاميّةٌ بالعقد."""
    storefront.require_icon(payload.icon)
    storefront.require_banner_link(payload.link_kind, payload.link)
    banner = PromoBanner(**payload.model_dump())
    storefront.stamp_if_shown(banner)
    session.add(banner)
    await _flush(session, conflict_message="تعذّر حفظ اللافتة")
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="promo_banner",
        entity_id=banner.id,
        details=payload.model_dump(mode="json"),
    )
    await session.commit()
    return AdminPromoBannerOut.model_validate(banner)


@router.patch("/promo-banners/{banner_id}", response_model=AdminPromoBannerOut)
async def update_promo_banner(
    banner_id: uuid.UUID,
    payload: PromoBannerPatch,
    admin: SettingsWriter,
    session: DbSession,
) -> AdminPromoBannerOut:
    banner = await storefront.get_banner(session, banner_id)
    changes = payload.model_dump(exclude_unset=True)
    storefront.require_icon(changes.get("icon", banner.icon))
    storefront.require_banner_link(
        changes.get("link_kind", banner.link_kind),
        changes.get("link", banner.link),
    )
    changed = _apply_updates(banner, changes)
    # **بعد التطبيق** — فإشعالُ لافتةٍ داخل نافذتها هو ما يُختم
    storefront.stamp_if_shown(banner)
    await session.flush()
    if changed:
        await audit.record(
            session,
            actor=admin,
            action=AuditAction.UPDATE,
            entity_type="promo_banner",
            entity_id=banner.id,
            changes=changed,
        )
    await session.commit()
    return AdminPromoBannerOut.model_validate(banner)


@router.get("/service-icons", response_model=list[str])
async def list_service_icons(_staff: StaffUser) -> list[str]:
    """**قائمةُ الأيقونات المقرَّرة — بيتُها واحدٌ يقرؤه المنتقي**.

    **ولا نسخةٌ ثانيةٌ تُكتب في اللوحة**: نسختان تفترقان بحرفٍ يوماً، **فيَعرض
    المنتقي ما يرفضه الباب** — والمشرفُ يختار من قائمةٍ ثم يُمنع، ولا يفهم لمَ.

    **ولا قاعدةَ تُسأل**: القائمةُ ثابتةُ شيفرةٍ يقابلها ما تعرفه lucide في
    التطبيقين، **فسؤالُ القاعدة عنها يخترع بيتاً ثالثاً**.
    """
    return list(storefront.SERVICE_ICONS)


@router.delete("/service-tiles/{tile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service_tile(
    tile_id: uuid.UUID, admin: SettingsWriter, session: DbSession
) -> None:
    """**المسوّدةُ وحدَها تُحذف** — وما عُرض مرّةً يُخفى (قرارُ المالك 2026-08-31).

    **والرفضُ من الخدمة لا من هنا**: `require_draft` بيتُ القاعدة، **وشرطان
    لقاعدةٍ واحدةٍ يفترقان** أوّلَ باب ثالث.
    """
    tile = await storefront.get_tile(session, tile_id)
    storefront.require_draft(tile)
    # **قيدُ التدقيق قبل الحذف** — فالصفُّ يحمل مفتاحَه، وقيدٌ بعد اختفائه
    # لا يعرف ما اختفى
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.DELETE,
        entity_type="service_tile",
        entity_id=tile.id,
        details={"key": tile.key, "country_code": tile.country_code.value},
    )
    await session.delete(tile)
    await session.commit()


@router.delete("/promo-banners/{banner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_promo_banner(
    banner_id: uuid.UUID, admin: SettingsWriter, session: DbSession
) -> None:
    """**المسوّدةُ وحدَها** — ومعها ملفُّ صورتها إن رُفع.

    **والملفُّ يُحذف بعد الإيداع لا قبله**: ملفٌّ يتيمٌ نفايةٌ تُكنس، **وصفٌّ
    يشير إلى ملفٍّ محذوفٍ عطلٌ يراه المستخدم** — وهي قاعدةُ `documents` نفسُها.
    """
    banner = await storefront.get_banner(session, banner_id)
    storefront.require_draft(banner)
    image_path = banner.image_path
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.DELETE,
        entity_type="promo_banner",
        entity_id=banner.id,
        details={"title": banner.title, "country_code": banner.country_code.value},
    )
    await session.delete(banner)
    await session.commit()
    if image_path:
        await storage.delete(image_path)


@router.put("/promo-banners/{banner_id}/image", response_model=AdminPromoBannerOut)
async def upload_banner_image(
    banner_id: uuid.UUID,
    admin: SettingsWriter,
    session: DbSession,
    file: UploadFile = File(...),
) -> AdminPromoBannerOut:
    """**صورةُ اللافتة — تُرفع وتُخزَّن ويخدمها بابٌ** (قرارُ المالك 2026-08-31).

    **والأربعةُ تُبنى معاً**: العمودُ · والرفعُ · والبابُ الذي يخدمها ·
    والعرضُ في البطاقة. **وواحدٌ منها ناقصاً يعيد العطبَ الذي نُزع له العمودُ
    في 2026-08-30**: عنوانٌ يُنشر لمسارٍ لا خادمَ له **يرسم صورةً مكسورة**،
    وهي أسوأُ من لا صورة.

    **وتمرّ بـ`storage.save`** كبقيّة ما يُرفع: يشمّ النوعَ من البايتات لا من
    ترويسةٍ يكتبها العميل، ويحدّ الحجمَ بالقراءة لا بـ`Content-Length`.

    **والقديمةُ تُحذف بعد الإيداع** — وترتيبُ الاثنين ليس تفصيلاً.
    """
    banner = await storefront.get_banner(session, banner_id)
    previous = banner.image_path
    stored = await storage.save(file, folder=str(banner.id))
    banner.image_path = stored.relative_path
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="promo_banner",
        entity_id=banner.id,
        changes={"image_path": {"before": "ملفٌّ سابق", "after": "ملفٌّ جديد"}},
    )
    await session.commit()
    if previous and previous != stored.relative_path:
        await storage.delete(previous)
    return AdminPromoBannerOut.model_validate(banner)


@router.delete("/promo-banners/{banner_id}/image", response_model=AdminPromoBannerOut)
async def delete_banner_image(
    banner_id: uuid.UUID, admin: SettingsWriter, session: DbSession
) -> AdminPromoBannerOut:
    """**نزعُ الصورة وحدَها** — واللافتةُ تبقى.

    **وهي ليست حذفَ الصفّ**: لافتةٌ عُرضت لا تُحذف، **لكنّ صورتَها قد تكون
    خطأً يُنزع** — ولافتةٌ بلا صورةٍ ترسمها الأيقونةُ كما كانت قبل العمود.
    """
    banner = await storefront.get_banner(session, banner_id)
    previous = banner.image_path
    if previous is None:
        raise NotFound("لا صورةَ على هذه اللافتة")
    banner.image_path = None
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="promo_banner",
        entity_id=banner.id,
        changes={"image_path": {"before": "ملفٌّ سابق", "after": "ملفٌّ جديد"}},
    )
    await session.commit()
    await storage.delete(previous)
    return AdminPromoBannerOut.model_validate(banner)


@router.get("/promo-banners/{banner_id}/image")
async def read_banner_image(
    banner_id: uuid.UUID, _staff: StaffUser, session: DbSession
) -> FileResponse:
    """**بابُ اللوحة إلى الصورة — ولا يسأل عن سوق القارئ**.

    **ولمَ بابٌ ثانٍ**: بابُ التطبيق يشترط أن يكون السوقُ سوقَ صاحبِ الحساب،
    **والمشرفُ يعدّ سوقاً قبل أن يُفتح** — فيبدّل السوقَ في ترويسة اللوحة
    ويقرأ لافتاتِ سوقٍ ليس سوقَه. **وهي علّةُ `GET /admin/countries` نفسُها**:
    من يهيّئ سوقاً مخفيّاً يحتاج أن يراه وهو مطفأ.

    **ولا يُوسَّع بابُ التطبيق ليخدم الاثنين**: شرطُ السوق هناك هو ما يمنع
    تسريبَ خطّةِ إطلاق، **ونزعُه لأجل اللوحة يفتحه لكلِّ حساب**.
    """
    banner = await storefront.get_banner(session, banner_id)
    if not banner.image_path:
        raise NotFound("لا صورةَ لهذه اللافتة")
    return FileResponse(
        storage.resolve(banner.image_path),
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/service-destinations", response_model=dict[str, list[str]])
async def list_service_destinations(_staff: StaffUser) -> dict[str, list[str]]:
    """**المقاصدُ المبنيّةُ ومن يراها** — واللوحةُ تعرضها ولا تكتبها بيد.

    **وهي أختُ `service-icons` بالعلّة نفسِها**: مسارٌ يُكتب بيدٍ في اللوحة
    **يُرفض في الباب** — والمشرفُ كتب شيئاً معقولاً ولا يعرف لمَ مُنع. **وقد
    كان الحقلُ نصّاً حرّاً** حتى اليوم.

    **والأدوارُ جزءُ الجواب لا زينة** (عطبٌ قِيس 2026-08-30): `/account/bookings`
    مبنيٌّ **عند الراكب وحدَه**، فبلاطةُ كبتنٍ تشير إليه تقع على `path="*"`.
    **فتُنشر الأدوارُ معه**، واللوحةُ تعرض لكلِّ جمهورٍ ما يصلح له.
    """
    return {
        destination: [role.value for role in roles]
        for destination, roles in storefront.SERVICE_DESTINATIONS.items()
    }
