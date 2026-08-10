"""حملات الإشعارات من اللوحة (SPEC القسم 13 — المرحلة 8).

المسارات تُبنى الآن وواجهتُها في اللوحة في المرحلة 11. و`admin` وحده:
حملةٌ تصل عشرات الآلاف ليست إجراءَ دعمٍ فني (SPEC القسم 13/8).

كل كتابةٍ هنا تدخل سجل التدقيق في نفس المعاملة — `services/campaigns.py`.
"""

from __future__ import annotations

import uuid
from datetime import time

from fastapi import APIRouter, Query

from app.core.deps import AdminUser, DbSession
from app.core.exceptions import InvalidInput
from app.models.enums import AuditAction, CampaignStatus, CountryCode
from app.schemas.notification import (
    CampaignCreate,
    CampaignOut,
    CampaignUpdate,
    DeliveryOut,
    NotificationSettingOut,
    NotificationSettingUpdate,
    TestPushRequest,
    TestPushResult,
)
from app.services import audit, campaigns as campaigns_service
from app.services.push import PushMessage, get_push_provider

router = APIRouter(prefix="/admin/campaigns", tags=["admin"])


@router.get("", response_model=list[CampaignOut])
async def list_campaigns(
    _admin: AdminUser,
    session: DbSession,
    status_filter: CampaignStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[CampaignOut]:
    rows = await campaigns_service.list_campaigns(
        session, status=status_filter, limit=limit, offset=offset
    )
    return [CampaignOut.model_validate(row) for row in rows]


@router.post("", response_model=CampaignOut, status_code=201)
async def create_campaign(
    payload: CampaignCreate, admin: AdminUser, session: DbSession
) -> CampaignOut:
    campaign = await campaigns_service.create(
        session,
        actor=admin,
        title=payload.title,
        body=payload.body,
        audience=payload.audience,
        country_code=payload.country_code,
        scheduled_at=payload.scheduled_at,
    )
    await session.commit()
    await session.refresh(campaign)
    return CampaignOut.model_validate(campaign)


@router.patch("/{campaign_id}", response_model=CampaignOut)
async def update_campaign(
    campaign_id: uuid.UUID,
    payload: CampaignUpdate,
    admin: AdminUser,
    session: DbSession,
) -> CampaignOut:
    """تعديلٌ أو جدولة — إرسالُ `scheduled_at` وحده يجدول الحملة."""
    campaign = await campaigns_service.get_campaign(
        session, campaign_id, for_update=True
    )
    campaign = await campaigns_service.update(
        session,
        campaign=campaign,
        actor=admin,
        title=payload.title,
        body=payload.body,
        audience=payload.audience,
        country_code=payload.country_code,
        scheduled_at=payload.scheduled_at,
    )
    await session.commit()
    await session.refresh(campaign)
    return CampaignOut.model_validate(campaign)


@router.post("/{campaign_id}/cancel", response_model=CampaignOut)
async def cancel_campaign(
    campaign_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> CampaignOut:
    campaign = await campaigns_service.get_campaign(
        session, campaign_id, for_update=True
    )
    campaign = await campaigns_service.cancel(
        session, campaign=campaign, actor=admin
    )
    await session.commit()
    await session.refresh(campaign)
    return CampaignOut.model_validate(campaign)


@router.get("/{campaign_id}/deliveries", response_model=list[DeliveryOut])
async def list_deliveries(
    campaign_id: uuid.UUID,
    _admin: AdminUser,
    session: DbSession,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[DeliveryOut]:
    """من وصله الإشعار ومن تُخطّي ولماذا — سجلٌّ يُقرأ بعد كل حملة."""
    rows = await campaigns_service.list_deliveries(
        session, campaign_id, limit=limit, offset=offset
    )
    return [DeliveryOut.model_validate(row) for row in rows]


# ------------------------------------------------------- إشعار تجريبي


@router.post("/test-push", response_model=TestPushResult)
async def send_test_push(
    payload: TestPushRequest, admin: AdminUser, session: DbSession
) -> TestPushResult:
    """يرسل إشعاراً إلى **رمز جهازٍ يكتبه المشرف** — تحقّقٌ من العقد الحقيقي.

    لماذا رمزٌ مكتوب لا مستخدمٌ مختار؟ لأن السلسلة تُختبر **قبل** أن يوجد
    تطبيقٌ يسجّل أجهزته: بيدك رمزٌ من صفحة اختبار FCM أو من أول نسخة تجريبية،
    فتعرف أن العقد وتوكن OAuth والشبكة والجهاز تعمل كلها — قبل أن يُبنى
    الراكب والكبتن على افتراض أنها تعمل.

    ولا يمر بقاعدة الاستثناء (`presence`) ولا بجدول الأجهزة: ذاك مسارُ
    الإشعارات الحقيقية، وهذا مِجَسّ.
    """
    provider = await get_push_provider(session)
    result = await provider.send(
        [payload.token],
        PushMessage(
            title=payload.title,
            body=payload.body,
            data={"type": "test_push"},
            high_priority=payload.high_priority,
        ),
    )

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="push_test",
        # لا رمز في السجل: به يُرسل إشعارٌ باسم المنصة إلى جهاز صاحبه
        details={"delivered": result.delivered, "failed": result.failed},
    )
    await session.commit()

    invalid = bool(result.invalid_tokens)
    if result.delivered:
        detail = "أُرسل الإشعار — إن لم يظهر على الجهاز فالمشكلة في التطبيق لا في العقد"
    elif invalid:
        detail = "رفض المزود الرمز: غير مسجَّل أو غير صالح — راجع نسخ الرمز"
    else:
        detail = "لم يقبل المزود الإرسال — راجع سجل الخلفية"

    return TestPushResult(
        delivered=result.delivered,
        failed=result.failed,
        invalid_token=invalid,
        provider=provider.provider_name,
        detail=detail,
    )


# --------------------------------------------------------- ساعات الهدوء


@router.get("/settings/{country_code}", response_model=NotificationSettingOut)
async def read_settings(
    country_code: CountryCode, _admin: AdminUser, session: DbSession
) -> NotificationSettingOut:
    setting = await campaigns_service.get_or_create_settings(session, country_code)
    await session.commit()
    return NotificationSettingOut.model_validate(setting)


@router.put("/settings/{country_code}", response_model=NotificationSettingOut)
async def update_settings(
    country_code: CountryCode,
    payload: NotificationSettingUpdate,
    _admin: AdminUser,
    session: DbSession,
) -> NotificationSettingOut:
    setting = await campaigns_service.get_or_create_settings(session, country_code)
    setting.quiet_hours_start = _parse_time(payload.quiet_hours_start)
    setting.quiet_hours_end = _parse_time(payload.quiet_hours_end)
    setting.timezone = _valid_timezone(payload.timezone)
    await session.commit()
    await session.refresh(setting)
    return NotificationSettingOut.model_validate(setting)


def _parse_time(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _valid_timezone(name: str) -> str:
    """مِنطقةٌ زمنية لا تُعرف تجعل كل حساب هدوءٍ بعدها خاطئاً بصمت."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise InvalidInput(f"مِنطقة زمنية غير معروفة: {name}") from exc
    return name


__all__ = ["router"]
