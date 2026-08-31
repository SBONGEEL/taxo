"""حملةُ تأكيد الأرقام — **تُبنى ولا تُطلق** (قرارُ المالك 2026-08-31).

## ما تفعله بالضبط

سوقٌ يُطلق فيه المالكُ حملةً، فيدخلها **كلُّ حسابٍ رقمُه غير مؤكَّد** —
الراكبُ كالكبتن، **فرقمُه هو ما يتّصل به الكبتن**. ويُمهَل **أربعةَ عشرَ
يوماً**، تصله فيها **ثلاثةُ تذكيرات**، ثم **يُوقَف حسابُه آلياً** حتى يؤكّده.

**والفعلُ الذي يُطلب منه واحد**: يفتح التطبيق ← يرى سطر «أكّد رقمك» ← يضغطه ←
يدخل رقمه ← يصله رمزٌ بالقناة العاملة ← يدخله. **ولا شاشةَ جديدةٌ تُبنى** —
سطرُ جولة البريد هو نفسُه، **والحملةُ تضيف إليه مهلةً ونصّاً**.

## أربعُ قواعدَ يحملها هذا الملفّ

**١) الموظّفون خارج النطاق — ومقيسٌ لا محتاط.** قِيس على الإنتاج
(2026-08-31): كلُّ الركاب والكباتن أرقامُهم مؤكَّدة، **والوحيدان غيرُ
المؤكَّدَين حسابا مشرف** لا رقمَ لهما أصلاً. **فحملةٌ لا تستثنيهم توقف
اللوحةَ عن نفسها**: من يفكّ الإيقافَ يحتاج لوحةً، واللوحةُ موقوفة.

**٢) والتجمّدُ آليٌّ حين تسقط قناةُ السوق.** **ولا يُعاقَب أحدٌ على عطبٍ
عندنا**: من لا يستطيع أن يستقبل رمزاً لا تجري عليه مهلة. **والمهلُ تُمدَّد
بمقدار ما تجمّدت** — «تستأنف بما بقي» بحرفها، **لا بما مضى من التقويم**.

**٣) والفكُّ بتأكيد الرقم وحدَه، فوراً وبلا مشرف.** ولا شرطَ آخر.

**٤) والمحفظةُ تبقى ولا تُمسّ**، **والاشتراكُ يُمدَّد بأيام الإيقاف**: أوقفناه
عن العمل، **فيومٌ لم يعمل فيه لا يُحسب عليه من شهرٍ دفع ثمنَه**.

## والنصوصُ مُحقَنةٌ لا مكتوبة

**التاريخُ يُحقن ولا يُكتب، وتُقاس المدّةُ من الحقل لا من نصّ** (قرارُ
المالك). فنصٌّ يقول «١٤ يوماً» وحقلٌ يقول غيرَها **يفترقان أوّلَ تعديل** —
والمستخدمُ يصدّق النصَّ ويُوقَف بالحقل.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, InvalidInput, NotFound
from app.models.enums import (
    CountryCode,
    UserRole,
    VerificationCampaignStatus,
)
from app.models.subscription import DriverSubscription
from app.models.user import User
from app.models.verification_campaign import (
    BATCH_SIZE,
    DEFAULT_DEADLINE_DAYS,
    REMINDER_DAYS,
    SUSPENSION_CODE,
    SUSPENSION_MESSAGE,
    VerificationCampaign,
    VerificationEnforcement,
)
from app.services import verification

LIVE_STATUSES = (
    VerificationCampaignStatus.DRAFT,
    VerificationCampaignStatus.RUNNING,
    VerificationCampaignStatus.PAUSED,
)

#: **نصوصُ التذكيرات الثلاثة بلفظ المالك** — **والمدّةُ مُحقَنة**.
#:
#: **ولا `title`/`body` مؤلَّفان في `data`**: القاعدةُ المسجَّلة أن الإشعار
#: يحمل قيماً خاماً في `data`، **و`title`/`body` للنظام حين يكون التطبيق
#: مغلقاً** — وهما وحدَهما المستثنيان.
REMINDER_TEXTS: tuple[str, ...] = (
    "أكّد رقم هاتفك ليبقى حسابك فعّالاً. لديك {days} يوماً.",
    "بقي {days} أيام لتأكيد رقمك. بعدها يُوقَف حسابك حتى تؤكّده.",
    "غداً يُوقَف حسابك إن لم تؤكّد رقمك.",
)

# **والسببُ يُقرأ من بيته الواحد** في `models/verification_campaign.py` —
# يقرؤه معه الخطأُ الذي يَردّ والحقلُ المنشور. **ولا «حسابك مجمَّد» مجرّدة**:
# يقول السببَ والطريقَ كما في الدَّين، و«رفضٌ بلا مخرجٍ ليس رفضاً».


@dataclass(frozen=True, slots=True)
class Outgoing:
    """إشعارٌ **قُرِّر ولم يُرسل بعد** — تودعه المهمّةُ ثم ترسله.

    **والقيمُ خامٌ في `data`** والجملةُ في `body` وحدَها: القاعدةُ المسجَّلة
    أن `title`/`body` **للنظام حين يكون التطبيقُ مغلقاً**، وما ترسمه الشاشةُ
    بنفسها يُؤلَّف من `data`.
    """

    user_id: uuid.UUID
    title: str
    body: str
    data: dict[str, str] = field(default_factory=dict)


def _now() -> datetime:
    return datetime.now(UTC)


# ───────────────────────────────────────────────────── ما يراه صاحبُ الحساب


# ─────────────────────────────────────────────────────────── حياةُ الحملة


async def live_for(
    session: AsyncSession, country: CountryCode
) -> VerificationCampaign | None:
    return await session.scalar(
        select(VerificationCampaign).where(
            VerificationCampaign.country_code == country,
            VerificationCampaign.status.in_(LIVE_STATUSES),
        )
    )


async def create_draft(
    session: AsyncSession,
    *,
    country: CountryCode,
    deadline_days: int = DEFAULT_DEADLINE_DAYS,
) -> VerificationCampaign:
    """**تُنشأ مسوّدةً ولا تُطلق** — والإطلاقُ ضغطةُ المالك وحدَه."""
    if deadline_days < 1 or deadline_days > 90:
        raise InvalidInput("المهلة بين يومٍ وتسعين")
    if await live_for(session, country) is not None:
        raise Conflict("توجد حملةٌ حيّةٌ في هذا السوق — أنهِها أو ألغِها أولاً")
    campaign = VerificationCampaign(
        country_code=country, deadline_days=deadline_days
    )
    session.add(campaign)
    await session.flush()
    return campaign


async def get(session: AsyncSession, campaign_id: uuid.UUID) -> VerificationCampaign:
    campaign = await session.get(VerificationCampaign, campaign_id)
    if campaign is None:
        raise NotFound("الحملة غير موجودة")
    return campaign


async def _locked(
    session: AsyncSession, campaign_id: uuid.UUID
) -> VerificationCampaign:
    """الصفُّ **مقفولاً** قبل فحص حالته — كبقيّة انتقالات الحالة في المشروع.

    **وبلا القفل يمرّ إطلاقان متزامنان**: كلاهما يقرأ `draft`، وكلاهما يكتب
    `running`، **وكلاهما يسجّل قيدَ تدقيق** — فتبدو الحملةُ أُطلقت مرّتين.
    """
    campaign = await session.scalar(
        select(VerificationCampaign)
        .where(VerificationCampaign.id == campaign_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if campaign is None:
        raise NotFound("الحملة غير موجودة")
    return campaign


async def start(
    session: AsyncSession, *, campaign_id: uuid.UUID, actor: User
) -> VerificationCampaign:
    """**الإطلاقُ فعلُ إنسانٍ دائماً** — ولا تُطلق حملةٌ على أحدٍ بلا ضغطته."""
    campaign = await _locked(session, campaign_id)
    if campaign.status is not VerificationCampaignStatus.DRAFT:
        raise Conflict("لا تُطلق إلا مسوّدة")
    campaign.status = VerificationCampaignStatus.RUNNING
    campaign.started_at = _now()
    campaign.started_by_id = actor.id
    return campaign


async def cancel(
    session: AsyncSession, *, campaign_id: uuid.UUID
) -> VerificationCampaign:
    """**إلغاءٌ قرارُ إنسانٍ لا يعود** — ويفكّ ما أوقفته.

    **ولا يُترك الموقوفون موقوفين**: الحملةُ التي أوقفتهم أُلغيت، **وإيقافٌ
    بلا حملةٍ تحكمه إيقافٌ لا يعرف أحدٌ متى ينتهي**.
    """
    campaign = await _locked(session, campaign_id)
    if campaign.status in (
        VerificationCampaignStatus.DONE,
        VerificationCampaignStatus.CANCELLED,
    ):
        raise Conflict("الحملة منتهيةٌ أصلاً")
    campaign.status = VerificationCampaignStatus.CANCELLED
    campaign.finished_at = _now()

    rows = list(
        await session.scalars(
            select(VerificationEnforcement).where(
                VerificationEnforcement.campaign_id == campaign.id,
                VerificationEnforcement.suspended_at.is_not(None),
                VerificationEnforcement.resolved_at.is_(None),
            )
        )
    )
    for row in rows:
        user = await session.get(User, row.user_id)
        if user is not None:
            await release(session, user=user, note="أُلغيت الحملة")
    return campaign


# ─────────────────────────────────────────────────────── من تشمله الحملة


def _scope_conditions():
    """**رقمٌ غير مؤكَّد، وحسابٌ ليس موظّفاً، وله رقمٌ أصلاً.**

    **والشروطُ الثلاثةُ ضرورية**، وثالثُها هو ما قِيس: حسابا المشرف على
    الإنتاج **لا رقمَ لهما** ويدخلان باسمِ مستخدم — **فهما «غيرُ مؤكَّدَين»
    بالمعنى الحرفيِّ ولا شيءَ لهما ليؤكّداه**.
    """
    return (
        User.phone_verified_at.is_(None),
        User.phone.is_not(None),
        User.role.in_((UserRole.RIDER, UserRole.DRIVER)),
        User.is_blocked.is_(False),
    )


async def scope_size(session: AsyncSession, country: CountryCode) -> int:
    """كم حساباً تشمله حملةُ هذا السوق **الآن** — تقرؤه اللوحةُ قبل الإطلاق.

    **ورقمٌ يُقرأ قبل الضغط هو الفرق** بين إطلاقٍ يعرف صاحبُه على من يطلق
    وإطلاقٍ يكتشفه بعده.
    """
    return int(
        await session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.country_code == country, *_scope_conditions())
        )
        or 0
    )


# ────────────────────────────────────────────────────────── دورةُ المهمّة


async def _channel_is_up(session: AsyncSession, country: CountryCode) -> bool:
    """أثمّة قناةُ تحقّقٍ عاملةٌ في هذا السوق؟ — **وبها يحيا الوقت**."""
    return bool(await verification.available_methods(session, country))


async def tick(session: AsyncSession) -> tuple[dict[str, int], list[Outgoing]]:
    """دورةٌ واحدةٌ على كلِّ حملةٍ حيّة — **تُستدعى من المهمّة الدورية**.

    **ولا تُرسل شيئاً**: تعيد ما يجب إرسالُه، **والمهمّةُ تودع ثم ترسل**.

    **وهي قاعدةُ المشروع لا احتياط**: «الإشعاراتُ تُنشر بعد `commit`» —
    فحالٌ أُعلنت ثم تراجعت معاملتُها **تصل صاحبَها ولا تقع**. ومن أرسل داخل
    المعاملة أرسل «حسابك موقوف» لمن لم يُوقَف.
    """
    counters = {"enrolled": 0, "reminded": 0, "suspended": 0, "paused": 0}
    outbox: list[Outgoing] = []
    campaigns = list(
        await session.scalars(
            select(VerificationCampaign).where(
                VerificationCampaign.status.in_(
                    (
                        VerificationCampaignStatus.RUNNING,
                        VerificationCampaignStatus.PAUSED,
                    )
                )
            )
        )
    )
    for campaign in campaigns:
        moved = await _advance(session, campaign, outbox)
        for key, value in moved.items():
            counters[key] += value
    return counters, outbox


async def _advance(
    session: AsyncSession,
    campaign: VerificationCampaign,
    outbox: list[Outgoing],
) -> dict[str, int]:
    moved = {"enrolled": 0, "reminded": 0, "suspended": 0, "paused": 0}
    now = _now()
    up = await _channel_is_up(session, campaign.country_code)

    # ── التجمّدُ والاستئنافُ **بلا مشرف** ──────────────────────────────────
    if not up:
        if campaign.status is VerificationCampaignStatus.RUNNING:
            campaign.status = VerificationCampaignStatus.PAUSED
            campaign.paused_at = now
            moved["paused"] += 1
        # **ولا شيءَ يجري وهي متجمّدة**: لا تذكيرَ يُرسل في قناةٍ ساقطة،
        # **ولا مهلةَ تنقضي على من لا يستطيع أن يستقبل**
        return moved

    if campaign.status is VerificationCampaignStatus.PAUSED:
        # **تستأنف بما بقي**: تُمدَّد المهلُ بمقدار ما تجمّدت — **لا بما مضى
        # من التقويم**، فمن أُمهل أربعةَ عشرَ يوماً يبقى له ما بقي منها
        frozen = int((now - (campaign.paused_at or now)).total_seconds())
        campaign.paused_seconds += max(frozen, 0)
        campaign.paused_at = None
        campaign.status = VerificationCampaignStatus.RUNNING
        if frozen > 0:
            await session.execute(
                VerificationEnforcement.__table__.update()
                .where(
                    VerificationEnforcement.campaign_id == campaign.id,
                    VerificationEnforcement.resolved_at.is_(None),
                )
                .values(
                    deadline_at=VerificationEnforcement.deadline_at
                    + timedelta(seconds=frozen)
                )
            )

    moved["enrolled"] += await _enrol(session, campaign, now)
    moved["reminded"] += await _remind(session, campaign, now, outbox)
    moved["suspended"] += await _suspend_due(session, campaign, now, outbox)
    return moved


async def _enrol(
    session: AsyncSession, campaign: VerificationCampaign, now: datetime
) -> int:
    """**دفعةُ مئتين** — والتقدّمُ في صفٍّ لا في ذاكرة المهمّة."""
    enrolled = select(VerificationEnforcement.user_id).where(
        VerificationEnforcement.campaign_id == campaign.id
    )
    users = list(
        await session.scalars(
            select(User)
            .where(
                User.country_code == campaign.country_code,
                User.id.not_in(enrolled),
                *_scope_conditions(),
            )
            .limit(BATCH_SIZE)
        )
    )
    for user in users:
        session.add(
            VerificationEnforcement(
                campaign_id=campaign.id,
                user_id=user.id,
                deadline_at=now + timedelta(days=campaign.deadline_days),
            )
        )
    return len(users)


async def _remind(
    session: AsyncSession,
    campaign: VerificationCampaign,
    now: datetime,
    outbox: list[Outgoing],
) -> int:
    """التذكيراتُ الثلاثةُ بأيّامها — **والمدّةُ من الحقل لا من نصّ**."""
    rows = list(
        await session.scalars(
            select(VerificationEnforcement)
            .where(
                VerificationEnforcement.campaign_id == campaign.id,
                VerificationEnforcement.resolved_at.is_(None),
                VerificationEnforcement.suspended_at.is_(None),
                VerificationEnforcement.reminders_sent < len(REMINDER_TEXTS),
            )
            .limit(BATCH_SIZE)
        )
    )
    sent = 0
    for row in rows:
        index = row.reminders_sent
        due_after = timedelta(days=REMINDER_DAYS[index])
        opened = row.deadline_at - timedelta(days=campaign.deadline_days)
        if now < opened + due_after:
            continue
        # **الأيامُ المتبقيةُ تُحسب من الحقل** — ويُجبر أدنى يومٍ واحد فلا
        # يُقال «بقي ٠ أيام» لمن لم تنقضِ مهلتُه بعد
        remaining = max(int((row.deadline_at - now).total_seconds() // 86400), 1)
        outbox.append(
            Outgoing(
                user_id=row.user_id,
                title="أكّد رقم هاتفك",
                body=REMINDER_TEXTS[index].format(days=remaining),
                data={
                    "type": "verification_campaign_reminder",
                    "reminder": str(index + 1),
                    "days_left": str(remaining),
                    "deadline_at": row.deadline_at.isoformat(),
                },
            )
        )
        row.reminders_sent = index + 1
        row.last_reminder_at = now
        sent += 1
    return sent


async def _suspend_due(
    session: AsyncSession,
    campaign: VerificationCampaign,
    now: datetime,
    outbox: list[Outgoing],
) -> int:
    """**الإيقافُ آليٌّ بلا مشرف** — ومعه سببُه المنشور."""
    rows = list(
        await session.scalars(
            select(VerificationEnforcement)
            .where(
                VerificationEnforcement.campaign_id == campaign.id,
                VerificationEnforcement.resolved_at.is_(None),
                VerificationEnforcement.suspended_at.is_(None),
                VerificationEnforcement.deadline_at <= now,
            )
            .limit(BATCH_SIZE)
        )
    )
    suspended = 0
    for row in rows:
        user = await session.get(User, row.user_id)
        if user is None:
            continue
        # **ومن أكّد رقمَه بين دورتين لا يُوقَف**: الحقلُ يُقرأ لحظةَ الفعل
        # لا لحظةَ التسجيل — وهو الفخُّ الذي تقع فيه المهامُّ الدورية
        if user.phone_verified:
            row.resolved_at = now
            continue
        user.verification_suspended_at = now
        row.suspended_at = now
        suspended += 1
        outbox.append(
            Outgoing(
                user_id=user.id,
                title="حسابك موقوف",
                body=SUSPENSION_MESSAGE,
                data={
                    "type": "verification_campaign_suspended",
                    "reason_code": SUSPENSION_CODE,
                },
            )
        )
    return suspended


# ─────────────────────────────────────────── الفكُّ — فوراً وبلا مشرف


async def release(
    session: AsyncSession, *, user: User, note: str | None = None
) -> int:
    """**يُفكّ الإيقافُ ويُمدَّد الاشتراكُ بأيام الإيقاف** — ويعيد الأيامَ المُهداة.

    **ويُستدعى من بابِ إثباتِ الرقم نفسِه** — لا من بابٍ ثالثٍ يُكتب له.

    **والمحفظةُ لا تُمسّ** (قرارُ المالك): الإيقافُ منعَ العملَ ولم يأخذ
    مالاً، **ومسُّ محفظةٍ لتصحيح إيقافٍ يخلط دفترين**.
    """
    days = 0
    suspended_at = user.verification_suspended_at
    user.verification_suspended_at = None

    rows = list(
        await session.scalars(
            select(VerificationEnforcement).where(
                VerificationEnforcement.user_id == user.id,
                VerificationEnforcement.resolved_at.is_(None),
            )
        )
    )
    now = _now()
    for row in rows:
        row.resolved_at = now
        if note:
            row.note = note
        if row.suspended_at is None or row.subscription_days_granted is not None:
            continue
        granted = await _extend_subscription(
            session, user=user, since=row.suspended_at, until=now
        )
        row.subscription_days_granted = granted
        days += granted

    # **وحالٌ بلا صفٍّ تُفكّ أيضاً**: حملةٌ حُذفت أو صفٌّ ضاع **لا يترك
    # إنساناً موقوفاً بلا سببٍ يُقرأ** — والعمودُ هو الحقيقة لا الصفّ
    if suspended_at is not None and not rows:
        days += await _extend_subscription(
            session, user=user, since=suspended_at, until=now
        )
    return days


async def _extend_subscription(
    session: AsyncSession, *, user: User, since: datetime, until: datetime
) -> int:
    """**يومٌ لم يعمل فيه لا يُحسب عليه من شهرٍ دفع ثمنَه** (قرارُ المالك).

    **ويُمدَّد الصفُّ الأبعدُ انتهاءً** لا الأحدثُ إنشاءً — وهي قاعدةُ
    `coverage_until` نفسُها: من جدّد مبكّراً يملك صفّين، **وتمديدُ الأقرب
    يضيع في ظلِّ الأبعد**.

    **ولا يُمدَّد لراكب**: لا اشتراكَ له أصلاً — والمنعُ لم يكلّفه شيئاً دفعه.
    """
    from app.models.driver import Driver

    days = max(int((until - since).total_seconds() // 86400), 0)
    if days <= 0:
        return 0

    driver_id = await session.scalar(
        select(Driver.id).where(Driver.user_id == user.id)
    )
    if driver_id is None:
        return 0

    row = await session.scalar(
        select(DriverSubscription)
        .where(
            DriverSubscription.driver_id == driver_id,
            DriverSubscription.expires_at > since,
        )
        .order_by(DriverSubscription.expires_at.desc())
        .with_for_update()
        .limit(1)
    )
    if row is None:
        # **ولا يُخترع اشتراكٌ لمن لم يكن مشتركاً** — التعويضُ عن شهرٍ دُفع
        # ثمنُه، ومن لا شهرَ له لا يُهدى له واحد
        return 0

    row.expires_at = row.expires_at + timedelta(days=days)
    return days


async def list_all(session: AsyncSession) -> list[VerificationCampaign]:
    return list(
        await session.scalars(
            select(VerificationCampaign).order_by(
                VerificationCampaign.created_at.desc()
            )
        )
    )


async def progress(session: AsyncSession, campaign_id: uuid.UUID) -> dict[str, int]:
    """**التقدّمُ يُعدّ من الصفوف لا يُخزَّن** — كرصيدِ المحفظة سواءً بسواء.

    عدّادٌ مخزَّنٌ يفترق عن صفوفه أوّلَ مسارٍ ينسى تحديثَه، **ومهمّةٌ دوريّةٌ
    تكتب في عدّادٍ ثم تسقط تترك رقماً يكذب**.
    """
    row = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(VerificationEnforcement.suspended_at.is_not(None)),
                func.count().filter(VerificationEnforcement.resolved_at.is_not(None)),
            ).where(VerificationEnforcement.campaign_id == campaign_id)
        )
    ).one()
    return {"enrolled": row[0] or 0, "suspended": row[1] or 0, "resolved": row[2] or 0}
