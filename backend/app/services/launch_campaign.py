"""**حملةُ إطلاق الكباتن** (أمرُ المالك ٢٠٢٦-١١-٢٤ السادس، الجزء ج؛ SPEC §١١٤-ج).

* **من اعتُمد قبل يوم الإطلاق**: `pre_launch_free_days` (٦٠) يوماً مجّانيّةً **بصفر عمولة تبدأ يومَ الإطلاق** (منتصفَ ليله بتوقيت الدولة).
* **من اعتُمد بعده**: `post_launch_free_days` (٧) **تبدأ من اعتماده** (`drivers.first_approved_at`).
* **والمنحةُ اشتراكٌ حقيقيٌّ** في `driver_subscriptions` من البابِ الواحد (`subscriptions._create`): مبلغٌ صفر، عمولةٌ مجمَّدةٌ صفراً، مرجعٌ يقول
  لماذا، **وقيدُ تدقيق** — ومنحةٌ واحدةٌ لكلِّ كبتن (`launch_campaign_grants.driver_id` فريد). **ولا مالَ يتحرّك** فلا قيدَ في الدفتر.
* **«الفترةُ المجّانيّة»** (قاعدةُ «يدفعها الكبتن» §١١٤-د): الحملةُ مشتعلةٌ **و**(قبل الإطلاق والكبتنُ معتمد، **أو** منحتُه ساريةٌ الآن).
* **كلُّ التواريخ والمدد من اللوحة، والمفتاحُ مطفأٌ حتى يؤكّد المالك.** ولا تُنشأ منحةٌ قبل يوم الإطلاق.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, InvalidInput
from app.models.driver import Driver
from app.models.enums import AuditAction, CountryCode, DriverStatus, PaymentMethod, SubscriptionDurationType
from app.models.launch_campaign import GRANT_POST, GRANT_PRE, LaunchCampaign, LaunchCampaignGrant
from app.models.subscription import SubscriptionPlan
from app.models.user import User

#: **نصُّ اللافتة كما كتبه المالك** — والأرقامُ منها تُقرأ من الحملة لا تُكتب هنا
BANNER = "سجّل قبل الإطلاق واحصل على {pre} يوماً مجاناً بدون عمولة — بعد الإطلاق {post} أيام فقط"
#: **إشعارُ «شريك الإطلاق» بنصّ المالك** — يُقرّ به الكبتنُ مرّةً
PARTNER_NOTICE = "خلال فترة الخدمة المجانية تتحمّل خصومات عروض الركاب كشريك TAXO للإطلاق"
REFERENCE = "حملةُ الإطلاق — اشتراكٌ مجّانيٌّ بلا عمولة"
EDITABLE = ("is_enabled", "launch_date", "pre_launch_free_days", "post_launch_free_days", "zero_commission", "show_banner")


def _now() -> datetime:
    return datetime.now(UTC)


async def get(session: AsyncSession, country: CountryCode) -> LaunchCampaign:
    """**حملةُ الدولة — تُنشأ بافتراضاتها مطفأةً أوّلَ قراءة.**"""
    row = await session.scalar(select(LaunchCampaign).where(LaunchCampaign.country_code == country))
    if row is None:
        # **الصفُّ يُضاف داخل نقطة الحفظ لا قبلها**: `begin_nested` يدفع المعلَّقَ قبل أن يفتحها، فيسقط تكرارُ مسحين متزامنين
        # خارجها ويُفسد المعاملةَ كلَّها (قِيس: `PendingRollbackError` في `test_two_concurrent_sweeps_grant_once`)
        try:
            async with session.begin_nested():
                row = LaunchCampaign(country_code=country)
                session.add(row)
                await session.flush()
        except IntegrityError:
            row = await session.scalar(select(LaunchCampaign).where(LaunchCampaign.country_code == country))
            assert row is not None
    return row


async def launch_at(session: AsyncSession, campaign: LaunchCampaign) -> datetime:
    """**منتصفُ ليل يوم الإطلاق بتوقيت الدولة** — بـUTC."""
    from app.services import stats

    zone: ZoneInfo = await stats._zone(session, campaign.country_code)
    return datetime.combine(campaign.launch_date, time(0, 0), zone).astimezone(UTC)


async def update(session: AsyncSession, *, country: CountryCode, changes: dict, actor: User) -> LaunchCampaign:
    from app.services import audit

    row = await get(session, country)
    diff: dict[str, dict] = {}
    for key, value in changes.items():
        if key not in EDITABLE:
            continue
        old = getattr(row, key)
        if old != value:
            diff[key] = {"from": str(old), "to": str(value)}
            setattr(row, key, value)
    if not (0 <= row.pre_launch_free_days <= 365 and 0 <= row.post_launch_free_days <= 365):
        raise InvalidInput("الأيّامُ بين ٠ و٣٦٥", field="pre_launch_free_days")
    if diff:
        await audit.record(
            session,
            actor=actor,
            action=AuditAction.UPDATE,
            entity_type="launch_campaign",
            entity_id=row.id,
            details={"country_code": country.value},
            changes=diff,
        )
    await session.flush()
    return row


async def active_grant(session: AsyncSession, driver_id: uuid.UUID, now: datetime) -> LaunchCampaignGrant | None:
    return await session.scalar(
        select(LaunchCampaignGrant).where(
            LaunchCampaignGrant.driver_id == driver_id,
            LaunchCampaignGrant.starts_at <= now,
            LaunchCampaignGrant.ends_at > now,
        )
    )


async def in_free_period(session: AsyncSession, driver: Driver, now: datetime | None = None) -> bool:
    """**الفترةُ المجّانيّة** — قاعدةُ «يدفعها الكبتن» تقرؤها (§١١٤-د)."""
    moment = now or _now()
    country = await session.scalar(select(User.country_code).where(User.id == driver.user_id))
    if country is None:
        return False
    campaign = await get(session, country)
    if not campaign.is_enabled:
        return False
    if moment < await launch_at(session, campaign):
        return driver.status is DriverStatus.APPROVED
    return await active_grant(session, driver.id, moment) is not None


async def commission_free(session: AsyncSession, driver: Driver, now: datetime | None = None) -> bool:
    """**أيُعفى هذا الكبتنُ من العمولة الآن؟** (أمرُ المالك العاشر ٢٠٢٦-١١-٢٥، SPEC §١١٤-ج)

    العمولةُ **بعد انتهاء فترة كلِّ كبتنٍ وحدَه** لا قبلها — فيُعفى إن كانت الحملةُ تقول «بصفر عمولة» (`zero_commission`) **و**:
    * **قبل منتصف ليل الإطلاق** — كلُّ كبتنٍ (ولو كانت الحملةُ مطفأة: «لا يُحصَّل من كبتنٍ شيءٌ قبل الإطلاق» قرارُ المالك نفسُه،
      والإشعالُ لا يحكم إلا المنحَ واللافتة)؛
    * **أو منحتُه ساريةٌ الآن** — ٦٠ يوماً لمن سبق الإطلاق، و٧ لمن اعتُمد بعده.

    **ولمَ لا يكفي اشتراكُ المنحة وحدَه** (عمولتُه مجمَّدةٌ صفراً): قبل الإطلاق لا منحةَ أصلاً، والكبتنُ الذي اشترى اشتراكاً مدفوعاً
    يحمل نسبةَ السوق مجمَّدة — **فبلا هذا الفحص يُحصَّل ٤٪ من كباتن ما قبل الإطلاق** لحظةَ تُرفع العمولة.
    """
    moment = now or _now()
    country = await session.scalar(select(User.country_code).where(User.id == driver.user_id))
    if country is None:
        return False
    campaign = await get(session, country)
    if not campaign.zero_commission:
        return False
    if moment < await launch_at(session, campaign):
        return True
    return await active_grant(session, driver.id, moment) is not None


async def _plan_for(session: AsyncSession, country: CountryCode) -> SubscriptionPlan | None:
    """**خطّةٌ تحمل الصفّ** — الشهريّةُ الفعّالة، والمدّةُ من الحملة لا منها (`days`)."""
    return await session.scalar(
        select(SubscriptionPlan)
        .where(
            SubscriptionPlan.country_code == country,
            SubscriptionPlan.is_active.is_(True),
            SubscriptionPlan.duration_type == SubscriptionDurationType.MONTHLY,
        )
        .limit(1)
    )


async def _grant(
    session: AsyncSession,
    *,
    campaign: LaunchCampaign,
    driver: Driver,
    kind: str,
    days: int,
    not_before: datetime,
) -> LaunchCampaignGrant | None:
    from app.services import audit, subscriptions

    plan = await _plan_for(session, campaign.country_code)
    if plan is None or days <= 0:
        return None
    locked = await subscriptions._locked_driver(session, driver.id)
    # **المنحةُ تُفحص تحت قفل الكبتن لا قبله**: مسحان متزامنان يقرآن «لا منحة» معاً، فيكتب الثاني اشتراكاً ثانياً
    # ثمّ يصطدم بقيد المنحة الفريد — **والاشتراكُ باقٍ**. بعد القفل يرى الثاني منحةَ الأوّل المودَعة فيقف.
    if await session.scalar(select(LaunchCampaignGrant.id).where(LaunchCampaignGrant.driver_id == driver.id)) is not None:
        return None
    try:
        async with session.begin_nested():
            subscription = await subscriptions._create(
                session,
                driver=locked,
                plan=plan,
                method=PaymentMethod.PROMO,
                amount_paid=Decimal("0.000"),
                reference=REFERENCE,
                days=days,
                commission_override=Decimal("0") if campaign.zero_commission else None,
                starts_not_before=not_before,
            )
    except AppError:
        # **كبتنٌ «دائم» أو مانعٌ آخر** — تُكتب منحتُه بلا اشتراكٍ فلا يُعاد كلَّ دورة، ويراها المشرف
        subscription = None
    starts = subscription.starts_at if subscription is not None else not_before
    ends = subscription.expires_at if subscription is not None else not_before + timedelta(days=days)
    grant = LaunchCampaignGrant(
        driver_id=driver.id,
        country_code=campaign.country_code,
        kind=kind,
        subscription_id=subscription.id if subscription is not None else None,
        starts_at=starts,
        ends_at=ends,
    )
    session.add(grant)
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError:
        return None
    await audit.record(
        session,
        actor=None,
        action=AuditAction.CREATE,
        entity_type="launch_campaign_grant",
        entity_id=grant.id,
        details={"driver_id": str(driver.id), "kind": kind, "days": days, "reason": REFERENCE},
    )
    return grant


async def sweep(session: AsyncSession, now: datetime | None = None, *, batch: int = 200) -> dict[str, int]:
    """**المجدول**: بعد منتصف ليل الإطلاق يمنح من سبقه، ثمّ كلَّ من يُعتمد بعده. **مطفأً أو قبل الإطلاق لا يكتب شيئاً.**"""
    moment = now or _now()
    done: dict[str, int] = {}
    for country in CountryCode:
        campaign = await get(session, country)
        if not campaign.is_enabled:
            continue
        start = await launch_at(session, campaign)
        if moment < start:
            continue
        granted = select(LaunchCampaignGrant.driver_id)
        drivers = (
            await session.execute(
                select(Driver)
                .join(User, User.id == Driver.user_id)
                .where(
                    User.country_code == country,
                    Driver.status == DriverStatus.APPROVED,
                    Driver.first_approved_at.is_not(None),
                    Driver.id.not_in(granted),
                )
                .order_by(Driver.first_approved_at)
                .limit(batch)
            )
        ).scalars().all()
        count = 0
        for driver in drivers:
            assert driver.first_approved_at is not None
            if driver.first_approved_at < start:
                made = await _grant(
                    session, campaign=campaign, driver=driver, kind=GRANT_PRE, days=campaign.pre_launch_free_days,
                    not_before=start,
                )
            else:
                made = await _grant(
                    session, campaign=campaign, driver=driver, kind=GRANT_POST, days=campaign.post_launch_free_days,
                    not_before=driver.first_approved_at,
                )
            if made is not None:
                count += 1
        done[country.value] = count
    return done


@dataclass(frozen=True, slots=True)
class CampaignView:
    enabled: bool
    show_banner: bool
    launch_date: str
    launch_at: str
    pre_launch_free_days: int
    post_launch_free_days: int
    zero_commission: bool
    banner: str
    partner_notice: str
    #: `pre_launch` · `granted` · `ended` · `waiting` — حالُ هذا الكبتن (فارغٌ للزائر)
    status: str | None = None
    grant_starts_at: str | None = None
    grant_ends_at: str | None = None
    ack_required: bool = False


async def view(session: AsyncSession, country: CountryCode, driver: Driver | None = None) -> CampaignView:
    campaign = await get(session, country)
    start = await launch_at(session, campaign)
    status = None
    starts = ends = None
    ack = False
    if driver is not None and campaign.is_enabled:
        grant = await session.scalar(select(LaunchCampaignGrant).where(LaunchCampaignGrant.driver_id == driver.id))
        now = _now()
        if grant is not None:
            status = "granted" if grant.ends_at > now else "ended"
            starts, ends = grant.starts_at.isoformat(), grant.ends_at.isoformat()
        elif now < start:
            status = "pre_launch"
        else:
            status = "waiting"
        ack = driver.launch_partner_ack_at is None
    return CampaignView(
        enabled=bool(campaign.is_enabled),
        show_banner=bool(campaign.show_banner),
        launch_date=campaign.launch_date.isoformat(),
        launch_at=start.isoformat(),
        pre_launch_free_days=campaign.pre_launch_free_days,
        post_launch_free_days=campaign.post_launch_free_days,
        zero_commission=bool(campaign.zero_commission),
        banner=BANNER.format(pre=campaign.pre_launch_free_days, post=campaign.post_launch_free_days),
        partner_notice=PARTNER_NOTICE,
        status=status,
        grant_starts_at=starts,
        grant_ends_at=ends,
        ack_required=ack,
    )


async def acknowledge(session: AsyncSession, driver: Driver) -> datetime:
    """**إقرارُ «شريك الإطلاق»** — مرّةً، ويبقى تاريخُه الأوّل."""
    from app.services import audit

    if driver.launch_partner_ack_at is None:
        driver.launch_partner_ack_at = _now()
        await audit.record(
            session,
            actor=None,
            action=AuditAction.UPDATE,
            entity_type="driver",
            entity_id=driver.id,
            details={"launch_partner_ack": True, "notice": PARTNER_NOTICE},
        )
        await session.flush()
    return driver.launch_partner_ack_at


async def grants(session: AsyncSession, country: CountryCode, limit: int = 500) -> list[dict]:
    rows = (
        await session.execute(
            select(LaunchCampaignGrant, User.name)
            .join(Driver, Driver.id == LaunchCampaignGrant.driver_id)
            .join(User, User.id == Driver.user_id)
            .where(LaunchCampaignGrant.country_code == country)
            .order_by(LaunchCampaignGrant.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "driver_id": str(grant.driver_id),
            "driver_name": name,
            "kind": grant.kind,
            "starts_at": grant.starts_at.isoformat(),
            "ends_at": grant.ends_at.isoformat(),
            "has_subscription": grant.subscription_id is not None,
        }
        for grant, name in rows
    ]


__all__ = ["acknowledge", "in_free_period", "sweep", "view", "date"]
