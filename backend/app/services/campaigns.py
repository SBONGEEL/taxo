"""حملات الإشعارات الإدارية/التسويقية (SPEC القسم 13 — المرحلة 8).

الفئة (ب) من نظام الإشعارات: بنيتُها تُبنى الآن وواجهتُها في اللوحة في
المرحلة 11. وكلُّ ما يميّزها عن المعاملاتي مكتوبٌ هنا لا هناك:

- **يملك المستخدم إطفاءها** (`users.marketing_push_enabled`). والمعاملاتي لا
  يقرأ هذا الحقل إطلاقاً.
- **ساعات هدوء per-country**: لا إرسال تسويقي داخلها، ويُؤجَّل إلى النافذة
  التالية — لا يُلغى ولا يُرسل ناقصاً. والتقسيم بالدولة لا بالحملة: حملةٌ
  للسوقين تُرسل في الأردن الآن وفي ليبيا بعد ساعة إن اختلفت نافذتاهما، وصفُّها
  يبقى `scheduled` حتى تنتهي كلُّ دولةٍ في نطاقها.
- **أولوية عادية**: إعلانٌ يوقظ هاتفاً في وضع توفير الطاقة إعلانٌ يُطفئه
  صاحبه ثم لا يعود.
- **على دفعات**: حملةٌ وطنية بحلقةٍ واحدة تحجز عاملاً طوال إرسالها وتسقط كلها
  إن سقط في منتصفها.

**عدم التكرار في القاعدة لا في المنطق**: `(campaign_id, user_id)` فريد، فمهمةٌ
أُعيد تشغيلها بعد سقوطٍ لا ترسل لمن وصله.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    Conflict,
    FeatureNotAvailable,
    InvalidInput,
    NotFound,
)
from app.models.device import DeviceToken
from app.models.enums import (
    AuditAction,
    CampaignAudience,
    CampaignStatus,
    CountryCode,
    DeliveryStatus,
    UserRole,
)
from app.models.notification import (
    OPEN_CAMPAIGN_STATUSES,
    NotificationCampaign,
    NotificationDelivery,
    NotificationSetting,
)
from app.models.user import User
from app.models.user_role_grant import has_role_clause
from app.services import admin_search, audit, devices, inbox
from app.services.push import PushMessage, PushProvider, get_push_provider_or_none

logger = logging.getLogger(__name__)

# دفعةُ مستخدمين واحدة. صغيرةٌ عمداً: كل مستخدمٍ نداءٌ للمزود، والمهمة يجب أن
# تُنهي دفعتها قبل `task_time_limit` وتترك أثرها في القاعدة قبل أي سقوط
BATCH_SIZE = 200

# نوعُ صفِّ صندوق الوارد وحمولةِ Push للحملات — قيمةٌ واحدة فلا يفترق ما
# يفتحه الضغط على الإشعار عمّا يفتحه الضغط على صفّه في الصندوق
CAMPAIGN_KIND = "campaign"

# نافذة الهدوء الافتراضية، بتوقيت الدولة لا بـ UTC
DEFAULT_QUIET_START = time(22, 0)
DEFAULT_QUIET_END = time(8, 0)
DEFAULT_TIMEZONES: dict[CountryCode, str] = {
    CountryCode.JO: "Asia/Amman",
    CountryCode.LY: "Africa/Tripoli",
}
_FALLBACK_TIMEZONE = "UTC"


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class DispatchResult:
    """حصيلةُ دورةٍ واحدة على حملة."""

    sent: int = 0
    skipped: int = 0
    failed: int = 0
    # دولٌ كانت في ساعات هدوئها فتُركت للنافذة التالية
    deferred_countries: list[CountryCode] = field(default_factory=list)
    completed: bool = False

    @property
    def deferred(self) -> bool:
        return bool(self.deferred_countries)


# ------------------------------------------------------------ ساعات الهدوء


async def get_settings(
    session: AsyncSession, country_code: CountryCode
) -> NotificationSetting | None:
    """قراءة فقط — `GET /config` مسارٌ عام لا يجوز أن يكتب صفَّ إعدادات."""
    return await session.scalar(
        select(NotificationSetting).where(
            NotificationSetting.country_code == country_code
        )
    )


async def get_or_create_settings(
    session: AsyncSession, country_code: CountryCode
) -> NotificationSetting:
    setting = await session.scalar(
        select(NotificationSetting).where(
            NotificationSetting.country_code == country_code
        )
    )
    if setting is None:
        setting = NotificationSetting(
            country_code=country_code,
            quiet_hours_start=DEFAULT_QUIET_START,
            quiet_hours_end=DEFAULT_QUIET_END,
            timezone=DEFAULT_TIMEZONES.get(country_code, _FALLBACK_TIMEZONE),
        )
        session.add(setting)
        await session.flush()
    return setting


def local_time(setting: NotificationSetting, moment: datetime) -> time:
    try:
        zone = ZoneInfo(setting.timezone)
    except (ZoneInfoNotFoundError, ValueError):  # pragma: no cover - إعداد خاطئ
        logger.warning("مِنطقة زمنية غير معروفة: %s", setting.timezone)
        zone = ZoneInfo(_FALLBACK_TIMEZONE)
    return moment.astimezone(zone).timetz().replace(tzinfo=None)


def within_quiet_hours(setting: NotificationSetting, moment: datetime) -> bool:
    """هل نحن داخل نافذة الهدوء بتوقيت الدولة؟

    النافذة الافتراضية تعبر منتصف الليل (22:00 → 08:00)، فلا تُقرأ بمقارنةِ
    مجالٍ واحد: `start <= t < end` تصف نافذةً نهارية، والليليةُ نقيضُها.
    وتساوي الطرفين يعني «لا هدوء» لا «هدوءٌ دائم» — إعدادٌ فارغ لا يُسكت
    المنصة إلى الأبد.
    """
    if setting.quiet_hours_start == setting.quiet_hours_end:
        return False

    now = local_time(setting, moment)
    if setting.quiet_hours_start < setting.quiet_hours_end:
        return setting.quiet_hours_start <= now < setting.quiet_hours_end
    return now >= setting.quiet_hours_start or now < setting.quiet_hours_end


# ------------------------------------------------------------------ القراءة


async def get_campaign(
    session: AsyncSession, campaign_id: uuid.UUID, *, for_update: bool = False
) -> NotificationCampaign:
    """`for_update` إلزامي لكل مسار يغيّر الحالة أو يرسل.

    بلا القفل قد تقرأ مهمتان دوريتان (أو مهمةٌ ومشرفٌ يلغي) نفسَ `scheduled`
    فترسلان معاً — والفريدُ على التسليم يمنع الإشعار المكرر لكنه لا يمنع
    حملةً أُلغيت من أن تُرسل.
    """
    stmt = select(NotificationCampaign).where(NotificationCampaign.id == campaign_id)
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    campaign = await session.scalar(stmt)
    if campaign is None:
        raise NotFound("الحملة غير موجودة")
    return campaign


async def list_campaigns(
    session: AsyncSession,
    *,
    status: CampaignStatus | None,
    limit: int,
    offset: int,
    q: str | None = None,
) -> Sequence[NotificationCampaign]:
    stmt = select(NotificationCampaign).order_by(
        NotificationCampaign.created_at.desc()
    )
    if status is not None:
        stmt = stmt.where(NotificationCampaign.status == status)
    # **مرشِّحٌ فقط** (`services/admin_search.py`): العنوانُ والنصّ — ولا صاحبَ
    # لحملةٍ يُبحث باسمه
    term = admin_search.normalize(q)
    if term is not None:
        stmt = stmt.where(
            admin_search.text_clause(
                term, NotificationCampaign.title, NotificationCampaign.body
            )
        )
    return (await session.scalars(stmt.limit(limit).offset(offset))).all()


async def list_deliveries(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
    q: str | None = None,
) -> Sequence[NotificationDelivery]:
    # **مرشِّحٌ فقط** (`services/admin_search.py`) — من وصله الإشعار باسمه أو رقمه
    term = admin_search.normalize(q)
    extra = (
        [admin_search.user_clause(term, NotificationDelivery.user_id)]
        if term is not None
        else []
    )
    return (
        await session.scalars(
            select(NotificationDelivery)
            .where(NotificationDelivery.campaign_id == campaign_id, *extra)
            .order_by(NotificationDelivery.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()


# ------------------------------------------------------------------ الكتابة


def _validate(
    *,
    audience: CampaignAudience,
    country_code: CountryCode | None,
    scheduled_at: datetime | None,
    status: CampaignStatus,
) -> None:
    if audience is CampaignAudience.SEGMENT:
        # الشرائح تُعرَّف مع ميزات المرحلة 12 — لا يُخترع لها معنى اليوم
        raise FeatureNotAvailable("الحملات حسب الشريحة تأتي مع ميزات المرحلة 12")
    if audience is CampaignAudience.BY_COUNTRY and country_code is None:
        raise InvalidInput("حدّد الدولة لجمهور «مستخدمو دولة»")
    if status is CampaignStatus.SCHEDULED and scheduled_at is None:
        raise InvalidInput("حملة مجدولة بلا موعد لا تُرسل أبداً")


async def create(
    session: AsyncSession,
    *,
    actor: User,
    title: str,
    body: str,
    audience: CampaignAudience,
    country_code: CountryCode | None,
    scheduled_at: datetime | None,
) -> NotificationCampaign:
    """حملة جديدة — مسودّةٌ أو مجدولة. الـ commit مسؤولية الراوتر."""
    status = (
        CampaignStatus.SCHEDULED if scheduled_at is not None else CampaignStatus.DRAFT
    )
    _validate(
        audience=audience,
        country_code=country_code,
        scheduled_at=scheduled_at,
        status=status,
    )

    campaign = NotificationCampaign(
        title=title.strip(),
        body=body.strip(),
        audience=audience,
        country_code=country_code,
        status=status,
        scheduled_at=scheduled_at,
        created_by=actor.id,
    )
    session.add(campaign)
    await session.flush()

    await audit.record(
        session,
        actor=actor,
        action=AuditAction.CREATE,
        entity_type="notification_campaign",
        entity_id=campaign.id,
        details={"status": campaign.status.value, "audience": audience.value},
    )
    return campaign


async def update(
    session: AsyncSession,
    *,
    campaign: NotificationCampaign,
    actor: User,
    title: str | None = None,
    body: str | None = None,
    audience: CampaignAudience | None = None,
    country_code: CountryCode | None = None,
    scheduled_at: datetime | None = None,
) -> NotificationCampaign:
    """تعديلٌ قبل الإرسال وحده — ما أُرسل لا يُعدَّل نصُّه بعد وصوله."""
    if campaign.status not in OPEN_CAMPAIGN_STATUSES:
        raise Conflict("لا تُعدَّل حملة أُرسلت أو أُلغيت")

    if title is not None:
        campaign.title = title.strip()
    if body is not None:
        campaign.body = body.strip()
    if audience is not None:
        campaign.audience = audience
    if country_code is not None:
        campaign.country_code = country_code
    if scheduled_at is not None:
        campaign.scheduled_at = scheduled_at
        campaign.status = CampaignStatus.SCHEDULED

    _validate(
        audience=campaign.audience,
        country_code=campaign.country_code,
        scheduled_at=campaign.scheduled_at,
        status=campaign.status,
    )
    await session.flush()

    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="notification_campaign",
        entity_id=campaign.id,
        # أسماء الحقول المتغيّرة فقط لا قيمها (SPEC القسم 4)
        details={
            "changed_fields": sorted(
                key
                for key, value in {
                    "title": title,
                    "body": body,
                    "audience": audience,
                    "country_code": country_code,
                    "scheduled_at": scheduled_at,
                }.items()
                if value is not None
            )
        },
    )
    return campaign


async def cancel(
    session: AsyncSession, *, campaign: NotificationCampaign, actor: User
) -> NotificationCampaign:
    if campaign.status not in OPEN_CAMPAIGN_STATUSES:
        raise Conflict("لا تُلغى حملة أُرسلت أو أُلغيت")

    campaign.status = CampaignStatus.CANCELLED
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="notification_campaign",
        entity_id=campaign.id,
        details={"status": campaign.status.value},
    )
    return campaign


# ------------------------------------------------------------------ الإرسال


def _audience_filters(campaign: NotificationCampaign) -> list:
    """شروطُ جمهور الحملة على `users`.

    المحظورون خارج كل جمهور: حسابٌ موقوف لا يُسوَّق له.
    """
    filters = [User.is_blocked.is_(False)]

    # **الجمهورُ من يملك الدور** — ومن يحمل الدورين يدخل الحملتين معاً، وهو
    # الصواب: الحملةُ تخاطب صفةً لا تصنّف أشخاصاً
    if campaign.audience is CampaignAudience.ALL_RIDERS:
        filters.append(has_role_clause(UserRole.RIDER))
    elif campaign.audience is CampaignAudience.ALL_DRIVERS:
        filters.append(has_role_clause(UserRole.DRIVER))
    else:
        # مستخدمو دولة: الركاب والكباتن دون حسابات الموظفين
        filters.append(has_role_clause(UserRole.RIDER, UserRole.DRIVER))

    if campaign.country_code is not None:
        filters.append(User.country_code == campaign.country_code)
    return filters


async def target_countries(
    session: AsyncSession, campaign: NotificationCampaign
) -> list[CountryCode]:
    """الدول التي فيها جمهورٌ فعلي لهذه الحملة.

    تُقرأ من المستخدمين لا من قائمة الدول: نافذةُ هدوءٍ لدولةٍ لا مستخدم لها
    تؤجّل الحملة كلها بلا سبب.
    """
    rows = await session.scalars(
        select(User.country_code).where(*_audience_filters(campaign)).distinct()
    )
    return list(rows)


async def _batch_user_ids(
    session: AsyncSession,
    campaign: NotificationCampaign,
    country_code: CountryCode,
    *,
    limit: int,
) -> list[uuid.UUID]:
    """دفعةُ من لم يُسجَّل لهم تسليمٌ بعد — التقدّم محفوظٌ في القاعدة.

    لا `offset`: كل دورةٍ تبدأ من حيث انتهت لأن الصفوف المُسلَّمة تخرج من
    النتيجة. فمهمةٌ سقطت في منتصف حملةٍ تُكملها التالية بلا عدٍّ محفوظٍ في
    الذاكرة.
    """
    delivered = select(NotificationDelivery.user_id).where(
        NotificationDelivery.campaign_id == campaign.id
    )
    stmt = (
        select(User.id)
        .where(
            *_audience_filters(campaign),
            User.country_code == country_code,
            User.id.not_in(delivered),
        )
        .order_by(User.created_at)
        .limit(limit)
    )
    return list(await session.scalars(stmt))


async def _tokens_by_user(
    session: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[str]]:
    rows = await session.execute(
        select(DeviceToken.user_id, DeviceToken.token).where(
            DeviceToken.user_id.in_(user_ids), DeviceToken.is_active.is_(True)
        )
    )
    grouped: dict[uuid.UUID, list[str]] = {}
    for user_id, token in rows:
        grouped.setdefault(user_id, []).append(token)
    return grouped


async def _send_batch(
    session: AsyncSession,
    provider: PushProvider,
    campaign: NotificationCampaign,
    user_ids: list[uuid.UUID],
    result: DispatchResult,
) -> None:
    """يرسل لدفعةٍ ويكتب سطر تسليمٍ لكل مستخدم فيها.

    السطر يُكتب حتى لمن لم يُرسل إليه: `skipped` تعني «لم نُرسل عمداً» —
    أطفأ التسويق أو لا جهاز مسجّل له. وهو ما يجعل احترامَ الإطفاء **مُثبَتاً**
    لا مزعوماً، ويمنع أن تُعاد محاولةُ من لا جهاز له في كل دورة.
    """
    opted_out = set(
        await session.scalars(
            select(User.id).where(
                User.id.in_(user_ids), User.marketing_push_enabled.is_(False)
            )
        )
    )
    tokens = await _tokens_by_user(
        session, [user_id for user_id in user_ids if user_id not in opted_out]
    )
    message = PushMessage(
        title=campaign.title,
        body=campaign.body,
        data={"type": CAMPAIGN_KIND, "campaign_id": str(campaign.id)},
    )
    now = _now()

    for user_id in user_ids:
        user_tokens = tokens.get(user_id) or []
        if user_id in opted_out or not user_tokens:
            status = DeliveryStatus.SKIPPED
            sent_at = None
        else:
            outcome = await provider.send(user_tokens, message)
            if outcome.invalid_tokens:
                await devices.deactivate_tokens(session, outcome.invalid_tokens)
            delivered = outcome.delivered > 0
            status = DeliveryStatus.SENT if delivered else DeliveryStatus.FAILED
            sent_at = now if delivered else None

        session.add(
            NotificationDelivery(
                campaign_id=campaign.id,
                user_id=user_id,
                status=status,
                sent_at=sent_at,
            )
        )
        if status is DeliveryStatus.SENT:
            # صندوق الوارد **لمن أُرسل إليه فعلاً وحده** (المرحلة 9-ب): من
            # أطفأ إشعارات العروض أطفأها، وإدخالُها صندوقَه من بابٍ آخر
            # التفافٌ على إطفاءٍ صريح — و`skipped` تعني بالضبط «لم نُرسل
            # عمداً»
            await inbox.record(
                session,
                user_id=user_id,
                kind=CAMPAIGN_KIND,
                title=campaign.title,
                body=campaign.body,
                data=dict(message.data),
            )
            result.sent += 1
        elif status is DeliveryStatus.SKIPPED:
            result.skipped += 1
        else:
            result.failed += 1


async def dispatch(
    session: AsyncSession,
    campaign: NotificationCampaign,
    *,
    batch_size: int = BATCH_SIZE,
    now: datetime | None = None,
) -> DispatchResult:
    """يرسل ما يمكن إرساله الآن من حملةٍ مجدولة. الـ commit مسؤولية المستدعي.

    يُستدعى والصفُّ **مقفول** (`get_campaign(for_update=True)`)، فمهمتان
    متزامنتان لا تتقاسمان حملةً واحدة.
    """
    result = DispatchResult()
    if campaign.status is not CampaignStatus.SCHEDULED:
        raise Conflict("لا تُرسل إلا حملة مجدولة")

    provider = await get_push_provider_or_none(session)
    if provider is None:
        # لا عقد FCM: الحملة تبقى مجدولة حتى يُدخل العقد — تعليمُها «مُرسلة»
        # بصفر متلقٍّ كذبٌ في سجلٍّ يُقرأ لاحقاً
        logger.warning("حملة %s مؤجلة: لا مزود إشعارات مفعّل", campaign.id)
        result.deferred_countries = await target_countries(session, campaign)
        return result

    moment = now or _now()
    for country_code in await target_countries(session, campaign):
        setting = await get_or_create_settings(session, country_code)
        if within_quiet_hours(setting, moment):
            result.deferred_countries.append(country_code)
            continue

        while True:
            batch = await _batch_user_ids(
                session, campaign, country_code, limit=batch_size
            )
            if not batch:
                break
            await _send_batch(session, provider, campaign, batch, result)
            await session.flush()

    campaign.sent_count += result.sent
    if not result.deferred_countries:
        campaign.status = CampaignStatus.SENT
        campaign.sent_at = moment
        result.completed = True

    await session.flush()
    return result


async def due_campaign_ids(
    session: AsyncSession, *, now: datetime | None = None, limit: int = 10
) -> list[uuid.UUID]:
    """الحملات التي حان موعدها — مُعرِّفاتٌ فقط.

    الصفوف تُقرأ ثم تُقفل واحدةً واحدة في `dispatch`: قراءةٌ مقفولةٌ لعشر
    حملاتٍ تحجزها كلها طوال إرسال أولاها.
    """
    stmt = (
        select(NotificationCampaign.id)
        .where(
            NotificationCampaign.status == CampaignStatus.SCHEDULED,
            NotificationCampaign.scheduled_at <= (now or _now()),
        )
        .order_by(NotificationCampaign.scheduled_at)
        .limit(limit)
    )
    return list(await session.scalars(stmt))
