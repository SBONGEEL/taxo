"""اشتراكات الكباتن: الشراء والسريان والانتهاء (SPEC القسم 8).

**لا اشتراك ساري = لا رحلات.** الحكم يقع في `dispatch.eligible_driver_ids`
لا في الواجهة، وسؤالُه هو سؤال هذا الملف الأول: هل يغطي هذا الكبتنَ صفٌّ
الآن؟ الجواب من الجدول مباشرةً وبالوقت الحاضر — لا من عمودٍ محفوظ ولا من
عدّادٍ في الذاكرة، تماماً كما يُحسب رصيد المحفظة من دفترها.

**التجديد سجلٌّ جديد** (القسم 4)، ومن تجدّد قبل انتهاء اشتراكه يبدأ الجديد من
حيث ينتهي القديم لا من الآن: من يجدّد مبكراً لا يُعاقَب بإحراق ما تبقّى له.
ولذلك «متى ينتهي اشتراكي» = **أقصى** `expires_at` بين صفوفه لا أحدثُها.

أربع قنوات وسلوكان:

- **فوريّتان**: المحفظة (خصمٌ من الدفتر في نفس المعاملة) والبطاقة (لا يُنشأ
  الصف إلا بعد أن يقول المزود «دُفع» — `card_payments.apply_state`).
- **يدويّتان**: الكاش وكليك، يسجّلهما الموظف من اللوحة **بعد قبض المال**. لا
  صفَّ لاشتراكٍ لم يصل ماله، كما لا يتغيّر رصيدٌ قبل تأكيد شحنته (القسم 7).

**قيدُ الدفتر للمحفظة وحدها**: القسم 9 يكتب رصيد الكبتن «أرباح − عمولات −
الاشتراكات المدفوعة **منها** − سحوبات». كاشٌ وكليكٌ وبطاقةٌ لا يمر مالها
بالمحفظة، فقيدُ خصمٍ عليها يخصم من الكبتن مرتين.

**ترتيب الأقفال: صف الرحلة ← صف الدفعة ← صف طلب المزود ← صف الكبتن ← القفل
الاستشاري للمحفظة.** صفُّ الكبتن يلعب هنا دور صف الرحلة في الدفعات: بغير قفله
يقرأ شراءان متزامنان نفس «نهاية التغطية» فيبنيان عليها فترتين متطابقتين —
يدفع الكبتن مرتين ويأخذ شهراً واحداً. ومسار البطاقة يقفله **بعد** صف الطلب لا
قبله، لأن الإشعار يبدأ من الطلب؛ فلو عكس أحدُ المسارين لتقابلا في جمود.

الـ commit مسؤولية الراوتر: اشتراكٌ وقيدُه لا يُثبَّت نصفهما.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import logging

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import SessionLocal
from app.core.exceptions import (
    AppError,
    Conflict,
    InvalidInput,
    NotFound,
    PermissionDenied,
    SubscriptionAlreadyPurchased,
)
from app.models.driver import Driver
from app.models.enums import (
    AuditAction,
    CountryCode,
    DriverStatus,
    PaymentMethod,
    SubscriptionDurationType,
    SubscriptionStatus,
    WalletTransactionType,
)
from app.models.ride import ACTIVE_DRIVER_STATUSES, Ride
from app.models.subscription import DriverSubscription, SubscriptionPlan
from app.models.user import User
from app.services import audit, geo, notifications, wallet
from app.ws import events

# مدة كل نوع خطة. أرقامٌ لا إعدادات: أسماء الخطط الثلاثة في SPEC القسم 4 هي
# مددها، فخطةٌ «شهرية» مدتها ثلاثون يوماً حيثما اشتُريت. الشهر ثلاثون يوماً لا
# شهرٌ تقويمي: التقويمي يعطي مشتري الأول من فبراير ثمانيةً وعشرين يوماً بنفس
# الثمن، وليس في النظام مِنطقةٌ زمنية لكل دولة يُبنى عليها حدُّ يومٍ أصلاً.
PLAN_DURATIONS: dict[SubscriptionDurationType, timedelta] = {
    SubscriptionDurationType.DAILY: timedelta(days=1),
    SubscriptionDurationType.WEEKLY: timedelta(days=7),
    SubscriptionDurationType.MONTHLY: timedelta(days=30),
}

# ما يسجّله الموظف نيابةً عن الكبتن بعد قبضه. القناتان الأخريان (المحفظة
# والبطاقة) يفتحهما صاحبهما ويشهد عليهما الدفترُ أو المزود، فلا تُسجَّل يدوياً.
STAFF_METHODS: tuple[PaymentMethod, ...] = (PaymentMethod.CASH, PaymentMethod.CLIQ)

# «إشعار قبل الانتهاء بـ 24 ساعة» (SPEC القسم 8)
EXPIRY_NOTICE_WINDOW = timedelta(hours=24)

# **ونافذةٌ ثانيةٌ قبلها بثلاثة أيام** (قرارُ المالك 2026-08-14، البند ١٢):
# «تنبيهُ 24 ساعة قد يصل والكبتن نائمٌ أو مشغول». والأوسعُ أولاً في الترتيب
# لأن `sweep` تمرّ عليها من الأوسع إلى الأضيق.
EARLY_NOTICE_WINDOW = timedelta(days=3)

# **كلُّ نافذةٍ تُطلق في نطاقها وحدَه**: من بقي له عشرون ساعةً هو داخلَ نافذة
# الثلاثة أيام أيضاً — وبلا حدٍّ أدنى لكلِّ نطاق يصله التنبيهان في اللحظة
# نفسِها، فيُقرأ الأول كذباً («ثلاثة أيام» وقد بقي يوم). فالنطاقُ (أدنى، أقصى].
EXPIRY_NOTICE_WINDOWS: tuple[tuple[timedelta, timedelta | None], ...] = (
    (EARLY_NOTICE_WINDOW, EXPIRY_NOTICE_WINDOW),
    (EXPIRY_NOTICE_WINDOW, None),
)

# **محاولاتُ التجديد التلقائي ثلاثٌ داخل نافذة اليوم** (قرارُ المالك 2026-08-14،
# البند ١٤): عند التنبيه، ثم بعد ثماني ساعات، ثم قبل الانتهاء بساعتين.
# **وواحدةٌ لا تكفي**: الرصيدُ قد يصل بينها — دفعةُ بطاقة، أو شحنٌ تأكّد، أو سحبٌ
# أُلغي — ومحاولةٌ واحدة تعني كبتناً كان يملك المال بعدها بساعة.
# وتُقاس **من نهاية التغطية** لا من لحظة التنبيه، فلا تنزلق مع دورة الكنس.
RENEWAL_ATTEMPTS: tuple[timedelta, ...] = (
    EXPIRY_NOTICE_WINDOW,       # قبل الانتهاء بـ24 ساعة — مع التنبيه نفسِه
    timedelta(hours=16),        # بعده بثماني ساعات
    timedelta(hours=2),         # آخرُ فرصة
)

# الإشعار حدثٌ لا سجلٌّ محاسبي، فأثرُه مفتاحُ Redis لا عمودٌ في الجدول: المهمة
# الدورية تعمل كل بضع دقائق، وبغير أثرٍ يُنبَّه الكبتن في كل دورة حتى ينتهي
# اشتراكه. وعمرُ المفتاح أطول من النافذة نفسها فلا يُعاد التنبيه داخلها.
_NOTICE_TTL_SECONDS = int(EARLY_NOTICE_WINDOW.total_seconds()) * 2


logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def renewal_key(subscription_id: uuid.UUID, before: timedelta) -> str:
    """أثرُ محاولةٍ واحدة — **بمفتاحٍ لكلِّ موعد**، كالتنبيه سواءً بسواء.

    والمهمّةُ تعمل كلَّ خمس دقائق، فبغير أثرٍ تُعاد المحاولةُ اثنتَي عشرةَ مرةً
    في الساعة على محفظةٍ لا يكفي رصيدُها — ضجيجٌ في الدفتر وفي صندوق الوارد.
    """
    return f"subscription:renew_tried:{subscription_id}:{int(before.total_seconds())}"


def notice_key(subscription_id: uuid.UUID, within: timedelta) -> str:
    """مفتاحٌ **لكل نافذة**: مفتاحٌ واحدٌ للاثنتين يجعل الأولى تبتلع الثانية،
    فمن أُخطر قبل ثلاثة أيام لا يُخطر قبل يوم — وهو أشدُّ التنبيهين لزوماً."""
    return f"subscription:expiry_notified:{subscription_id}:{int(within.total_seconds())}"


# ------------------------------------------------------------------ القراءة


def coverage_condition(now: datetime | None = None):
    """شرط «هذا الصف يغطي اللحظة الحاضرة» — تعبيرٌ واحد يقرأه الجميع.

    الحالة **والوقت** معاً وليس الحالة وحدها: المهمة الدورية تعلّم المنتهي كل
    بضع دقائق، وبين دورتين يبقى صفٌّ انقضى وقتُه محمولاً على `active`. من يوزّع
    رحلةً في تلك الدقائق يجب أن يقرأ الساعة لا العمود (SPEC القسم 5.3: الفحص في
    الخلفية عند التوزيع). والعكس ليس صحيحاً — العمود بلا الوقت يكفي للتقارير.
    """
    moment = now or func.now()
    return (
        DriverSubscription.status == SubscriptionStatus.ACTIVE,
        DriverSubscription.starts_at <= moment,
        DriverSubscription.expires_at > moment,
    )


def covered_driver_ids_subquery():
    """استعلامٌ فرعي بالكباتن المغطّين الآن — يستعمله التوزيع وخريطة الراكب."""
    return select(DriverSubscription.driver_id).where(
        DriverSubscription.driver_id == Driver.id, *coverage_condition()
    )


async def current_subscription(
    session: AsyncSession, driver_id: uuid.UUID
) -> DriverSubscription | None:
    """الصف الذي يغطي هذه اللحظة، وأبعدُها انتهاءً إن تداخل صفّان."""
    return await session.scalar(
        select(DriverSubscription)
        .where(DriverSubscription.driver_id == driver_id, *coverage_condition())
        .options(selectinload(DriverSubscription.plan))
        .order_by(DriverSubscription.expires_at.desc())
        .limit(1)
    )


async def coverage_until(
    session: AsyncSession, driver_id: uuid.UUID
) -> datetime | None:
    """آخر لحظة يغطيها ما اشتراه هذا الكبتن — أساسُ تكديس التجديد المبكر.

    **أقصى** انتهاءٍ لا آخرُ صفٍّ أُنشئ: من جدّد اليوم اشتراكاً يبدأ بعد أسبوع
    يبقى غطاؤه ممتداً إلى ما بعده، فالصفُّ الأحدث ليس بالضرورة الأبعد.
    """
    return await session.scalar(
        select(func.max(DriverSubscription.expires_at)).where(
            DriverSubscription.driver_id == driver_id,
            DriverSubscription.status == SubscriptionStatus.ACTIVE,
            DriverSubscription.expires_at > func.now(),
        )
    )


async def history(
    session: AsyncSession, driver_id: uuid.UUID, *, limit: int, offset: int
) -> Sequence[DriverSubscription]:
    return (
        await session.scalars(
            select(DriverSubscription)
            .where(DriverSubscription.driver_id == driver_id)
            .options(selectinload(DriverSubscription.plan))
            .order_by(DriverSubscription.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()


async def list_all(
    session: AsyncSession,
    *,
    status: SubscriptionStatus | None = None,
    driver_id: uuid.UUID | None = None,
    country_code: CountryCode | None = None,
    limit: int,
    offset: int,
) -> Sequence[DriverSubscription]:
    """تقارير الاشتراكات في اللوحة (SPEC القسم 13.5)."""
    stmt = (
        select(DriverSubscription)
        .options(selectinload(DriverSubscription.plan))
        .order_by(DriverSubscription.created_at.desc())
    )
    if status is not None:
        stmt = stmt.where(DriverSubscription.status == status)
    if driver_id is not None:
        stmt = stmt.where(DriverSubscription.driver_id == driver_id)
    if country_code is not None:
        stmt = stmt.where(
            DriverSubscription.plan_id.in_(
                select(SubscriptionPlan.id).where(
                    SubscriptionPlan.country_code == country_code
                )
            )
        )
    return (await session.scalars(stmt.limit(limit).offset(offset))).all()


async def available_plans(
    session: AsyncSession, country_code: CountryCode
) -> Sequence[SubscriptionPlan]:
    """الخطط المعروضة على الكبتن — المفعّلة في بلده وحدها."""
    return (
        await session.scalars(
            select(SubscriptionPlan)
            .where(
                SubscriptionPlan.country_code == country_code,
                SubscriptionPlan.is_active.is_(True),
            )
            .order_by(SubscriptionPlan.price)
        )
    ).all()


async def get_plan(
    session: AsyncSession, plan_id: uuid.UUID, country_code: CountryCode
) -> SubscriptionPlan:
    """خطةٌ يجوز شراؤها في هذه الدولة الآن.

    الدولة شرطٌ لا زينة: أسعار الخطط بعملة بلدها، وشراءُ كبتنٍ أردنيٍّ خطةً
    ليبية يعني خصماً بعملةٍ ودفتراً بأخرى.
    """
    plan = await session.get(SubscriptionPlan, plan_id)
    if plan is None or plan.country_code != country_code:
        # 404 لا 403: خطةُ بلدٍ آخر ليست معلومة يستحقها من يجرّب مُعرّفات
        raise NotFound("خطة الاشتراك غير موجودة")
    if not plan.is_active:
        raise Conflict("هذه الخطة موقوفة — اختر خطة أخرى")
    return plan


def days_remaining(until: datetime | None, *, now: datetime | None = None) -> int:
    """عدّاد الأيام المتبقية في تطبيق الكبتن (SPEC القسم 12.5).

    يُقرَّب **لأعلى**: من بقيت له ست ساعات في يومه لم ينتهِ اشتراكه بعد، فعرضُ
    «صفر» عليه يقول إنه خارج الخدمة وهو فيها.
    """
    if until is None:
        return 0
    remaining = until - (now or _now())
    if remaining <= timedelta(0):
        return 0
    return -(-int(remaining.total_seconds()) // 86400)


# ------------------------------------------------------------------ الإنشاء


async def _locked_driver(session: AsyncSession, driver_id: uuid.UUID) -> Driver:
    """يقفل صف الكبتن قبل قراءة تغطيته — بغيره يتراكب شراءان على فترة واحدة."""
    driver = await session.scalar(
        select(Driver)
        .where(Driver.id == driver_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if driver is None:  # pragma: no cover - يمنعه المفتاح الأجنبي
        raise NotFound("ملف الكبتن غير موجود")
    return driver


async def _find_by_idempotency_key(
    session: AsyncSession, key: str
) -> DriverSubscription | None:
    return await session.scalar(
        select(DriverSubscription)
        .where(DriverSubscription.idempotency_key == key)
        # الخطة معها: الردّ على المفتاح المكرر هو نفس الردّ على الأول، وتحميلٌ
        # كسول بعد الـ commit في سياقٍ لا متزامن يرفع `MissingGreenlet`
        .options(selectinload(DriverSubscription.plan))
    )


def require_purchasable(driver: Driver) -> None:
    """اشتراكٌ يبدأ عدُّه فوراً، فلا يُباع لمن لا يستطيع أن يعمل به.

    ترتيب القسم 16.13 نفسه: تسجيل ← موافقة ← اشتراك. بيعُه لحسابٍ معلّق يحرق
    أيامه في الانتظار.
    """
    if driver.status != DriverStatus.APPROVED:
        raise PermissionDenied("لا يمكن الاشتراك قبل اعتماد حسابك")


async def _create(
    session: AsyncSession,
    *,
    driver: Driver,
    plan: SubscriptionPlan,
    method: PaymentMethod,
    amount_paid: Decimal,
    reference: str | None = None,
    idempotency_key: str | None = None,
    transaction_id: uuid.UUID | None = None,
) -> DriverSubscription:
    """يكتب صف الاشتراك — **يُستدعى وصفُّ الكبتن مقفول**.

    بدايته من حيث تنتهي تغطيته القائمة إن وُجدت، وإلا فمن الآن.
    """
    starts_at = await coverage_until(session, driver.id) or _now()
    subscription = DriverSubscription(
        driver_id=driver.id,
        # العلاقة لا المُعرّف: الردّ يعرض اسم الخطة ومدتها، وتحميلٌ كسول بعد
        # الـ commit في سياقٍ لا متزامن يرفع `MissingGreenlet`
        plan=plan,
        starts_at=starts_at,
        expires_at=starts_at + PLAN_DURATIONS[plan.duration_type],
        amount_paid=amount_paid,
        payment_method=method,
        status=SubscriptionStatus.ACTIVE,
        reference=reference,
        idempotency_key=idempotency_key,
        transaction_id=transaction_id,
    )
    session.add(subscription)
    try:
        await session.flush()
    except IntegrityError as exc:
        # القيد الفريد على المفتاح — سباقٌ عبر عمليتين لا تتقاسمان قفل الصف
        await session.rollback()
        raise SubscriptionAlreadyPurchased() from exc
    return subscription


async def purchase_with_wallet(
    session: AsyncSession,
    *,
    driver: Driver,
    user: User,
    plan_id: uuid.UUID,
    idempotency_key: str,
) -> DriverSubscription:
    """شراءٌ من رصيد الكبتن — فوريٌّ في معاملة واحدة (SPEC القسم 8).

    المفتاح يُفحص **بعد** قفل صف الكبتن لا قبله: ضغطتان بنفس المفتاح تتسلسلان
    هنا فتجد الثانيةُ اشتراكَ الأولى بدل أن تصطدم بالقيد الفريد.
    """
    await wallet.require_wallet_enabled(session, user.country_code)
    wallet.require_not_frozen(user)

    locked = await _locked_driver(session, driver.id)
    require_purchasable(locked)

    existing = await _find_by_idempotency_key(session, idempotency_key)
    if existing is not None:
        return existing

    plan = await get_plan(session, plan_id, user.country_code)

    # خطةٌ بلا ثمن (القسم 4 يجيز `price >= 0`) لا قيد لها: الدفتر يرفض قيداً
    # بصفر عن حق — لم يتحرك مال. والاشتراك يُفتح كما لو دُفع لأنه دُفع بثمنه
    entry = (
        await wallet.record(
            session,
            owner=user,
            tx_type=WalletTransactionType.SUBSCRIPTION_PAYMENT,
            amount=-plan.price,
            reference=plan.name,
            created_by=user.id,
            idempotency_key=idempotency_key,
        )
        if plan.price > 0
        else None
    )
    return await _create(
        session,
        driver=locked,
        plan=plan,
        method=PaymentMethod.WALLET,
        amount_paid=plan.price,
        idempotency_key=idempotency_key,
        transaction_id=entry.id if entry is not None else None,
    )


async def record_manual(
    session: AsyncSession,
    *,
    driver: Driver,
    user: User,
    plan_id: uuid.UUID,
    method: PaymentMethod,
    amount_paid: Decimal | None,
    reference: str | None,
    actor: User,
) -> DriverSubscription:
    """اشتراكٌ قبضته الإدارة كاشاً أو كليكاً فسجّلته (SPEC القسم 8/13.5).

    يُنشأ مؤكداً لأنه لا يُنشأ إلا بعد وصول المال — كما ينشئ الموظفُ شحنةَ
    الكاش مؤكدةً في `topups.create_confirmed`. `amount_paid` يقبل قيمةً مغايرةً
    لسعر الخطة (خصمٌ أو تسويةُ فرقٍ يقرّرها المشرف) ويبقى ما دُفع فعلاً
    مسجّلاً، والقيدُ في سجل التدقيق يقول من قرّره.
    """
    if method not in STAFF_METHODS:
        raise InvalidInput("هذه القناة لا تُسجَّل من اللوحة")

    locked = await _locked_driver(session, driver.id)
    require_purchasable(locked)
    plan = await get_plan(session, plan_id, user.country_code)

    subscription = await _create(
        session,
        driver=locked,
        plan=plan,
        method=method,
        amount_paid=plan.price if amount_paid is None else amount_paid,
        reference=(reference or "").strip() or None,
    )
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.CREATE,
        entity_type="driver_subscription",
        entity_id=subscription.id,
        # أسماء الحقول وقنواتها لا مبالغها (SPEC القسم 14)
        details={"driver_id": str(driver.id), "method": method.value},
    )
    return subscription


async def activate_paid_order(
    session: AsyncSession,
    *,
    driver_user: User,
    plan_id: uuid.UUID,
    amount: Decimal,
    reference: str | None,
    idempotency_key: str,
) -> DriverSubscription:
    """اشتراكٌ دفعه المزود بالبطاقة — يُستدعى من `card_payments.apply_state`.

    **لا قيد في الدفتر**: مال الكبتن خرج من بطاقته لا من محفظته، فقيدُ خصمٍ
    عليها يخصم منه مرتين — نفس ما تفعله دفعة الرحلة بالبطاقة مع الراكب.
    """
    driver = await session.scalar(
        select(Driver).where(Driver.user_id == driver_user.id)
    )
    if driver is None:  # pragma: no cover - لا يُفتح الطلب أصلاً بلا كبتن
        raise NotFound("ملف الكبتن غير موجود")

    locked = await _locked_driver(session, driver.id)
    existing = await _find_by_idempotency_key(session, idempotency_key)
    if existing is not None:
        return existing

    # الخطة تُقرأ بمُعرّفها لا بشروط العرض: عقدُ الشراء انعقد لحظة فتح الطلب،
    # فإيقافُ الخطة بين الدفع والإشعار لا يجوز أن يبتلع مالاً وصل فعلاً
    plan = await session.get(SubscriptionPlan, plan_id)
    if plan is None:  # pragma: no cover - يمنعه المفتاح الأجنبي
        raise NotFound("خطة الاشتراك غير موجودة")

    return await _create(
        session,
        driver=locked,
        plan=plan,
        method=PaymentMethod.CARD,
        amount_paid=amount,
        reference=reference,
        idempotency_key=idempotency_key,
    )


# ------------------------------------------------------------------ الانتهاء


@dataclass(frozen=True, slots=True)
class SubscriptionNotice:
    """ما يلزم لإخطار كبتنٍ بعد الـ commit — بلا صفٍّ تنتهي جلسته قبل البث."""

    driver_id: uuid.UUID
    driver_user_id: uuid.UUID
    subscription_id: uuid.UUID
    expires_at: datetime
    country_code: CountryCode
    went_offline: bool = False


@dataclass(frozen=True, slots=True)
class RenewalCandidate:
    """كبتنٌ رفع مفتاحَ التجديد وغطاؤه ينتهي داخل النافذة."""

    driver_id: uuid.UUID
    driver_user_id: uuid.UUID
    subscription_id: uuid.UUID
    plan_id: uuid.UUID
    expires_at: datetime
    country_code: CountryCode
    #: موعدُ المحاولة الذي استحقّ الآن — يميّز أثرَها في Redis
    attempt: timedelta
    #: أهي الأخيرة؟ فشلُها يُقال صراحةً لا يُبتلع
    last: bool


async def due_renewals(session: AsyncSession) -> list[RenewalCandidate]:
    """من استحقّت لهم محاولةُ تجديدٍ الآن (البند ١٤).

    **ولا مهمّةَ ثالثة**: تُقرأ في دورة الكنس نفسِها التي تُخطر — قرارُ المالك،
    وسببُه أن النافذة واحدة والصفوفَ هي هي، ومهمّةٌ ثانيةٌ على الجدول نفسِه
    تعني جدولين يقرآن حالةً واحدةً ويفترقان يومَ يتأخر أحدهما.
    """
    now = _now()
    candidates: list[RenewalCandidate] = []
    for index, before in enumerate(RENEWAL_ATTEMPTS):
        # الموعدُ يُقاس من **نهاية التغطية**: كلُّ من بقي له أقلُّ من `before`
        # ولم تُسجَّل له محاولةُ هذا الموعد بعد
        horizon = now + before
        rows = (
            await session.scalars(
                select(DriverSubscription)
                .join(Driver, Driver.id == DriverSubscription.driver_id)
                .where(
                    *coverage_condition(now),
                    DriverSubscription.expires_at <= horizon,
                    Driver.auto_renew.is_(True),
                )
            )
        ).all()
        for subscription in rows:
            until = await coverage_until(session, subscription.driver_id)
            if until is None or until > horizon:
                continue  # جدّد فعلاً — لا شأن لهذا الموعد به
            context = await _driver_context(session, subscription.driver_id)
            if context is None:  # pragma: no cover - يمنعه المفتاح الأجنبي
                continue
            candidates.append(
                RenewalCandidate(
                    driver_id=subscription.driver_id,
                    driver_user_id=context[0],
                    subscription_id=subscription.id,
                    plan_id=subscription.plan_id,
                    expires_at=until,
                    country_code=context[1],
                    attempt=before,
                    last=index == len(RENEWAL_ATTEMPTS) - 1,
                )
            )
    return candidates


@dataclass(frozen=True, slots=True)
class SweepResult:
    expired: list[SubscriptionNotice]
    # **مع نافذتها**: النصُّ يختلف بين «ثلاثة أيام» و«أقل من يوم»، والمفتاحُ
    # الذي يمنع التكرار يحمل النافذةَ كذلك (البند ١٢)
    expiring: list[tuple[timedelta, SubscriptionNotice]]


async def _driver_context(
    session: AsyncSession, driver_id: uuid.UUID
) -> tuple[uuid.UUID, CountryCode] | None:
    row = (
        await session.execute(
            select(User.id, User.country_code)
            .join(Driver, Driver.user_id == User.id)
            .where(Driver.id == driver_id)
        )
    ).first()
    return (row[0], row[1]) if row else None


async def _has_active_ride(session: AsyncSession, driver_id: uuid.UUID) -> bool:
    return bool(
        await session.scalar(
            select(Ride.id)
            .where(
                Ride.driver_id == driver_id, Ride.status.in_(ACTIVE_DRIVER_STATUSES)
            )
            .limit(1)
        )
    )


async def expire_due(session: AsyncSession) -> list[SubscriptionNotice]:
    """يعلّم ما انقضى وقته ويُخرج صاحبه من التوزيع (SPEC القسم 8).

    التعليم لا يغيّر الأهلية — `coverage_condition` تقرأ الساعة فالكبتن خرج من
    التوزيع لحظة انقضاء وقته لا لحظة مرور المهمة. غرضُ التعليم أن يقول الجدول
    ما تقوله الساعة، فتُقرأ التقارير بلا حساب.

    **وإخراجٌ من التوزيع لمن لا رحلة له**: من كان في رحلة يبقى فيها إلى نهايتها
    — إسقاطُ حضوره يقطع خريطةَ راكبه ويوقظ تنبيه «انقطع الكبتن» (القسم 5) على
    كبتنٍ لم ينقطع. ولا رحلة جديدة تصله على أي حال.
    """
    due = (
        await session.scalars(
            select(DriverSubscription)
            .where(
                DriverSubscription.status == SubscriptionStatus.ACTIVE,
                DriverSubscription.expires_at <= func.now(),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).all()

    notices: list[SubscriptionNotice] = []
    for subscription in due:
        subscription.status = SubscriptionStatus.EXPIRED
        context = await _driver_context(session, subscription.driver_id)
        if context is None:  # pragma: no cover - يمنعه المفتاح الأجنبي
            continue
        user_id, country_code = context

        # اشترى تجديداً يبدأ الآن؟ إذاً انقضى صفٌّ لا تغطيةٌ — لا إخطار ولا إخراج
        if await coverage_until(session, subscription.driver_id) is not None:
            continue

        driver = await session.get(Driver, subscription.driver_id)
        went_offline = False
        if driver.is_online and not await _has_active_ride(
            session, subscription.driver_id
        ):
            driver.is_online = False
            went_offline = True

        notices.append(
            SubscriptionNotice(
                driver_id=subscription.driver_id,
                driver_user_id=user_id,
                subscription_id=subscription.id,
                expires_at=subscription.expires_at,
                country_code=country_code,
                went_offline=went_offline,
            )
        )
    return notices


async def expiring_soon(
    session: AsyncSession,
    *,
    within: timedelta = EXPIRY_NOTICE_WINDOW,
    after: timedelta | None = None,
) -> list[SubscriptionNotice]:
    """من ينتهي غطاؤه خلال النافذة ولم يجدّد بعد (SPEC القسم 8).

    الشرط على **نهاية التغطية** لا على الصف: من اشترى شهرين بصفّين ينتهي أولهما
    غداً، وتنبيهُه أن اشتراكه ينتهي غداً كذبٌ يدفعه لدفعٍ لا يحتاجه.

    و`after` حدُّ النطاق الأدنى (البند ١٢): نافذةُ الثلاثة أيام تستثني من دخل
    نافذةَ الأربع والعشرين ساعة، فلا يصل التنبيهان معاً.
    """
    horizon = _now() + within
    floor = _now() + after if after is not None else None
    rows = (
        await session.scalars(
            select(DriverSubscription).where(
                *coverage_condition(), DriverSubscription.expires_at <= horizon
            )
        )
    ).all()

    notices: list[SubscriptionNotice] = []
    for subscription in rows:
        until = await coverage_until(session, subscription.driver_id)
        if until is None or until > horizon:
            continue  # جدّد فعلاً — غطاؤه يتجاوز النافذة
        if floor is not None and until <= floor:
            continue  # داخلَ نافذةٍ أضيق — تلك صاحبةُ التنبيه
        context = await _driver_context(session, subscription.driver_id)
        if context is None:  # pragma: no cover - يمنعه المفتاح الأجنبي
            continue
        notices.append(
            SubscriptionNotice(
                driver_id=subscription.driver_id,
                driver_user_id=context[0],
                subscription_id=subscription.id,
                expires_at=until,
                country_code=context[1],
            )
        )
    return notices


async def sweep(session: AsyncSession) -> SweepResult:
    """دورة المهمة الخلفية كاملةً — بلا بثٍّ ولا Redis. الـ commit للمستدعي."""
    expiring: list[tuple[timedelta, SubscriptionNotice]] = []
    for within, after in EXPIRY_NOTICE_WINDOWS:
        for notice in await expiring_soon(session, within=within, after=after):
            expiring.append((within, notice))
    return SweepResult(expired=await expire_due(session), expiring=expiring)


async def attempt_renewal(
    session: AsyncSession, candidate: RenewalCandidate
) -> DriverSubscription | None:
    """محاولةُ تجديدٍ واحدة — **من المحفظة وحدَها** (قرارُ المالك).

    الـcommit للمستدعي، ويعيد `None` إن لم يقع التجديد لأيِّ سبب.

    **ولا بابَ ثانٍ للمال**: تمرّ من `purchase_with_wallet` نفسِها التي يضغطها
    الكبتن بيده — فقفلُ صفِّ الكبتن ومفتاحُ التكرار وتراكمُ المدة من
    `coverage_until` كلُّها تعمل كما هي، ولا قاعدةَ تُكتب مرتين لتفترق مرة.

    **ومفتاحُ التكرار من الاشتراك والموعد** لا من الوقت: دورتان متزامنتان على
    الموعد نفسِه تجدان الاشتراكَ الأول بدل أن تخصما مرتين.
    """
    driver = await session.get(Driver, candidate.driver_id)
    user = await session.get(User, candidate.driver_user_id)
    if driver is None or user is None:  # pragma: no cover - يمنعه المفتاح الأجنبي
        return None

    # **تجديدٌ وقع فعلاً لا يُعاد إعلانُه**: مفتاحُ التكرار يجعل `purchase_with_wallet`
    # تعيد الاشتراكَ القائم بلا خصم — وهذا صحيحٌ للمال وخاطئٌ للخبر: من جُدِّد
    # له مرةً يصله إشعارٌ ثانٍ بلا شيءٍ جديد. قِيس على الجهاز: دورةٌ أُعيدت
    # يدوياً فكتبت صفَّ «جُدِّد اشتراكك» مرتين والدفترُ فيه قيدٌ واحد
    key = f"autorenew:{candidate.subscription_id}"
    if await _find_by_idempotency_key(session, key) is not None:
        return None

    try:
        return await purchase_with_wallet(
            session,
            driver=driver,
            user=user,
            plan_id=candidate.plan_id,
            # **المفتاحُ من الاشتراك وحدَه لا من الموعد**: المحاولاتُ الثلاث
            # تجديدٌ **واحد** يُحاول ثلاثاً، لا ثلاثةُ تجديدات. وبمفتاحٍ لكل
            # موعدٍ وقع الخصمُ مرتين حين استحقّ موعدان في دورةٍ واحدة — كشفه
            # `test_it_renews_once_per_attempt_window` قبل أن يُشحن.
            idempotency_key=key,
        )
    except AppError as exc:
        # **يُبتلع خطأُ المجال وحدَه**: رصيدٌ لا يكفي، أو محفظةٌ مجمَّدة، أو خطةٌ
        # أُوقفت، أو كبتنٌ مُعلَّق — كلُّها حالاتٌ عاديةٌ في مهمّةٍ دورية. وما
        # عداها يصعد كي لا يُبتلع عطبٌ في الكود صامتاً (درسُ 12-ط)
        await session.rollback()
        logger.info(
            "تعذّر التجديد التلقائي للاشتراك %s: %s",
            candidate.subscription_id,
            exc.code,
        )
        return None


async def renew_due(redis: Redis) -> int:
    """يحاول التجديدَ لمن استحقّ، ويعيد عددَ من جُدِّد له (البند ١٤).

    **كلُّ محاولةٍ في معاملتها**: فشلُ واحدةٍ لا يُسقط الدورة، ونجاحُ واحدةٍ
    يُثبَّت قبل أن تبدأ التالية — نفسُ شكلِ `referrals.pay_due`.

    **والأثرُ يُكتب قبل المحاولة لا بعدها**: `SET NX` هو ما يمنع دورتين
    متزامنتين من محاولةِ الموعد نفسِه، فكتابتُه بعد النجاح تترك النافذةَ
    مفتوحةً بينهما. وثمنُه أن انهياراً في منتصف المحاولة يُفوّت موعداً واحداً
    من ثلاثة — وذاك أهونُ من خصمين.
    """
    renewed = 0
    async with SessionLocal() as session:
        candidates = await due_renewals(session)

    # **من جُدِّد له في هذه الدورة يُتجاوز**: موعدان قد يستحقّان معاً (من بقي له
    # ثلاثُ ساعاتٍ داخلَ موعدَي 24 و16)، ومفتاحُ التكرار يمنع الخصمَ الثاني —
    # لكنه لا يمنع إشعاراً ثانياً ولا عدّاً ثانياً. والقائمةُ قُرئت مرةً، فحالُها
    # لا تعرف ما وقع بعدها
    done: set[uuid.UUID] = set()

    for candidate in candidates:
        if candidate.driver_id in done:
            continue
        key = renewal_key(candidate.subscription_id, candidate.attempt)
        if not await redis.set(key, "1", nx=True, ex=_NOTICE_TTL_SECONDS):
            continue
        async with SessionLocal() as session:
            subscription = await attempt_renewal(session, candidate)
            if subscription is not None:
                await session.commit()
                renewed += 1
                done.add(candidate.driver_id)
                await notifications.publish_subscription_event(
                    session,
                    redis,
                    driver_user_id=candidate.driver_user_id,
                    event=events.SubscriptionEvent.SUBSCRIPTION_RENEWED,
                    expires_at=subscription.expires_at,
                )
            elif candidate.last:
                # **آخرُ محاولةٍ تفشل تُقال صراحةً** (قرارُ المالك): وما قبلها
                # يصمت — ثلاثةُ إشعاراتٍ بفشلٍ واحدٍ في يومٍ واحد ضجيج،
                # والرصيدُ قد يصل قبل التالية فيصير الإشعارُ الأولُ كذباً
                await notifications.publish_subscription_event(
                    session,
                    redis,
                    driver_user_id=candidate.driver_user_id,
                    event=events.SubscriptionEvent.SUBSCRIPTION_RENEWAL_FAILED,
                    expires_at=candidate.expires_at,
                )
    return renewed


async def publish_sweep(
    session: AsyncSession, redis: Redis, result: SweepResult
) -> None:
    """يبث نتائج الدورة **بعد الـ commit** ويسقط حضور من خرج من التوزيع.

    الإخطار مرة واحدة لكل اشتراك: مفتاحٌ في Redis بعمرٍ أطول من النافذة، فمهمةٌ
    تعمل كل بضع دقائق لا تُغرق الكبتن بنفس التنبيه حتى ينتهي اشتراكه. ولذلك هو
    مفتاحٌ لا عمود: الإخطار حدثٌ عابر لا سجلٌّ يُحاسَب عليه.
    """
    for notice in result.expired:
        if notice.went_offline:
            await geo.go_offline(
                redis, driver_id=notice.driver_id, country_code=notice.country_code
            )
        await notifications.publish_subscription_event(
            session,
            redis,
            driver_user_id=notice.driver_user_id,
            event=events.SubscriptionEvent.SUBSCRIPTION_EXPIRED,
            expires_at=notice.expires_at,
        )

    for within, notice in result.expiring:
        if not await redis.set(
            notice_key(notice.subscription_id, within),
            "1",
            nx=True,
            ex=_NOTICE_TTL_SECONDS,
        ):
            continue
        await notifications.publish_subscription_event(
            session,
            redis,
            driver_user_id=notice.driver_user_id,
            event=events.SubscriptionEvent.SUBSCRIPTION_EXPIRING,
            expires_at=notice.expires_at,
            hours_left=int(within.total_seconds() // 3600),
        )
