"""سلفُ الكباتن — الأهليةُ والسقفُ والصرفُ والاقتطاعُ والإيقاف (البند ١٥).

`design/DRIVER-ADVANCES.md` هي المواصفة، وقراراتُ المالك الثمانية فيها
(2026-08-14). وستُّ قواعدَ تحكم هذا الملف:

- **الدَّينُ ليس رصيداً سالباً**: جدولٌ مستقلٌّ وقيدان في الدفتر — والحارسُ
  `balance_after >= 0` يبقى غيرَ ممسوس (انظر `models/advance.py`).
- **والأهليةُ مقاييسُ مسمّاةٌ لا نقاطُ مصداقية** (القرار ١): كلُّ شرطٍ يُعاد إلى
  الشاشة باسمه ورقمِه وحالِه، فمن مُنع يعرف ماذا يفعل. و«مصداقية ٣٫٢» لا يقول
  لصاحبه شيئاً.
- **والشرطُ الذي لا يُعطَّل: اشتراكٌ أسبوعيٌّ أو شهريٌّ *مضى*** (القرار ٣) — لا
  «قائمٌ الآن». الشرطُ يقيس **تاريخاً** لا حالة: من اشترى شهرياً قبل ساعةٍ
  وطلب سلفةً لم يُثبت شيئاً بعد.
- **والصرفُ تلقائيٌّ داخل السقف** (القرار ٢)، وما فوقه بموافقة مشرف. طابورُ
  موافقاتٍ على مبالغَ بقيمة اشتراكٍ يوميٍّ يموت بعد أسبوعٍ فيصير البابُ مغلقاً
  بلا أن يقرّر أحدٌ إغلاقَه.
- **والاقتطاعُ خصمٌ من أرباحٍ داخلة لا سحبٌ من رصيدٍ قائم**: موضعُه
  `payments.settle` بعد العمولة تماماً، فلا يقع الرصيدُ تحت الصفر ولا يُلمس
  حارس. **ومن لا أرباحَ له داخلةً لا يُقتطع منه**: الكاشُ وكليكٌ لا يمرّان
  بالمحفظة (القسم 9)، فالمالُ الذي يُقتطع منه ليس هنا أصلاً.
- **والإيقافُ يقرؤه التوزيعُ من عمودٍ محضَّر** لا من جمعِ دفترٍ في المسار
  الحرج — **ويُطفأ في مسار السداد نفسِه**، لا بدورةٍ تالية: من سدَّد وبقي
  ممنوعاً عشر دقائق يقرأ السدادَ بلا أثر.

**وترتيبُ الأقفال**: صفُّ السلفة، ثم صفُّ الكبتن، ثم قفلُ المحفظة الاستشاري
داخل `wallet.record` — وهو موضعُها من الترتيب العامّ في `CLAUDE.md` بلا
اختراعِ ترتيبٍ ثانٍ.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.exceptions import Conflict, InsufficientBalance, NotFound
from app.models.advance import (
    DEFAULT_DEDUCTION_PERCENT,
    DEFAULT_MIN_COMPLETED_RIDES,
    DEFAULT_TERM_DAYS,
    AdvanceSetting,
    DriverAdvance,
)
from app.models.driver import Driver
from app.models.enums import (
    AdvanceStatus,
    CountryCode,
    DriverStatus,
    FeatureKey,
    PaymentStatus,
    RideStatus,
    SubscriptionDurationType,
    WalletTransactionType,
)
from app.models.payment import Payment
from app.models.ride import Ride
from app.models.subscription import DriverSubscription, SubscriptionPlan
from app.models.user import User
from app.services import settings_service, wallet
from app.services.pricing import round_money

logger = logging.getLogger(__name__)

# **مدّةُ الشطب** (القرار ٧): تسعون يوماً من انقضاء المهلة، ثم **قرارٌ إداريٌّ
# مسجَّل** — لا شطبَ آليّ. وهي ثابتٌ في الوحدة لا حقلٌ في اللوحة: رقمٌ محاسبيٌّ
# لا يراه مستخدمٌ ولا يختلف عليه سوقان، وحقلٌ له حالةٌ ثانيةٌ يمكن أن تخالف
# سلوكاً لا يقيسه أحد — قاعدةُ مدّة تقليم صندوق الوارد نفسُها
WRITEOFF_AFTER_DAYS = 90

# الاشتراكاتُ التي تُثبت التاريخَ المطلوب — واليوميُّ ليس منها بنصِّ الشرط
QUALIFYING_DURATIONS = (
    SubscriptionDurationType.WEEKLY,
    SubscriptionDurationType.MONTHLY,
)


class AdvanceUnavailable(Conflict):
    code = "advance_unavailable"
    message = "السلف غير متاحة الآن"


class AdvanceNotAllowed(Conflict):
    code = "advance_not_allowed"
    message = "لا تنطبق عليك شروط السلفة"


def _now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------- السياسة


@dataclass(frozen=True, slots=True)
class Policy:
    """سياسةُ دولةٍ كما تُقرأ لحظةَ السؤال — لا يُجمَّد منها إلا ما صُرف."""

    enabled: bool
    deduction_percent: int
    min_kept_amount: Decimal
    term_days: int
    min_completed_rides: int
    min_rating: Decimal
    growth_percent_per_repaid: int
    max_multiplier_percent: int


async def policy_for(session: AsyncSession, country: CountryCode) -> Policy:
    row = await session.scalar(
        select(AdvanceSetting).where(AdvanceSetting.country_code == country)
    )
    return Policy(
        enabled=await settings_service.is_feature_enabled(
            session, country, FeatureKey.DRIVER_ADVANCES_ENABLED
        ),
        deduction_percent=row.deduction_percent if row else DEFAULT_DEDUCTION_PERCENT,
        # **مُكمَّمٌ**: صفرٌ مُنشأٌ في بايثون يُسلسَل `"0"` حيث تُسلسَل بقيةُ
        # المال `"0.000"` — الشكلُ السابع، وأمسكه الحارسُ في هذا السطر بعينه
        min_kept_amount=row.min_kept_amount if row else Decimal("0.000"),
        term_days=row.term_days if row else DEFAULT_TERM_DAYS,
        min_completed_rides=(
            row.min_completed_rides if row else DEFAULT_MIN_COMPLETED_RIDES
        ),
        min_rating=row.min_rating if row else Decimal("0"),
        growth_percent_per_repaid=row.growth_percent_per_repaid if row else 0,
        max_multiplier_percent=row.max_multiplier_percent if row else 100,
    )


async def daily_plan_price(
    session: AsyncSession, country: CountryCode
) -> Decimal | None:
    """أساسُ السقف: **سعرُ الخطة اليومية** بنصِّ قرار المالك.

    ولا رقمَ جديدٌ يُخترع له: سعرٌ ثانٍ للاشتراك اليوميِّ يتقادم أوَّلَ مرةٍ
    تُعدَّل فيها الأسعار، فيقرأ الكبتنُ سقفاً لا يساوي ما يشتريه.

    و`None` تعني «لا خطةَ يوميةً مفعّلةً في هذا السوق» — فلا سقفَ يُحسب، ولا
    تُعرض السلفُ ولو أُشعل المفتاح.
    """
    return await session.scalar(
        select(func.min(SubscriptionPlan.price)).where(
            SubscriptionPlan.country_code == country,
            SubscriptionPlan.duration_type == SubscriptionDurationType.DAILY,
            SubscriptionPlan.is_active.is_(True),
        )
    )


# ------------------------------------------------------------- المقاييس


@dataclass(frozen=True, slots=True)
class Requirement:
    """شرطٌ **باسمه ورقمه وحاله** — هذا هو القرار ١ في شكله النهائي.

    الشاشةُ ترسم هذه القائمة كما هي: «رحلاتٌ مكتملة ٣١/٥٠ ✗». ورقمٌ مركَّبٌ
    واحدٌ («مصداقيتك ٣٫٢») يُخفي أيَّ شرطٍ نقص، فلا يعرف صاحبُه ماذا يفعل.
    """

    key: str
    met: bool
    value: Decimal | None = None
    needed: Decimal | None = None


async def _completed_rides(session: AsyncSession, driver_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count(Ride.id)).where(
                Ride.driver_id == driver_id, Ride.status == RideStatus.COMPLETED
            )
        )
        or 0
    )


async def _has_qualifying_subscription(
    session: AsyncSession, driver_id: uuid.UUID
) -> bool:
    """اشتراكٌ أسبوعيٌّ أو شهريٌّ **انقضت مدّتُه** — لا «قائمٌ الآن» (القرار ٣).

    **والشرطُ `expires_at <= now` لا `starts_at`**، وهو حرفُ القرار: «من يشتري
    اشتراكاً شهرياً اليوم ويطلب سلفةً بعد ساعةٍ لم يُثبت شيئاً بعد». فقراءةُ
    البداية وحدَها تجعل اشتراكاً عمرُه ساعةٌ يؤهِّل — وهي بالضبط الحالُ التي
    وُضع الشرطُ ليمنعها. **والمقيسُ مدّةٌ عملٍ اكتملت**، لا نيّةٌ أُعلنت.

    **ولا تُقرأ الحالةُ (`status`) أصلاً**: كنسُ الاشتراكات يعلّم المنتهيَ كل
    بضع دقائق، فصفٌّ انقضى وقتُه ولم تمرّ عليه الدورةُ بعدُ لا يجوز أن يقرأه
    هذا الشرط «غيرَ منقضٍ» — نفسُ سببِ قراءة `coverage_condition` للساعة لا
    للعمود.

    والصفُّ نفسُه دليلُ الدفع: `driver_subscriptions` لا يُنشأ إلا وقد وصل
    مالُه — فلا حاجةَ لسؤال الدفتر عن قناةٍ لا تمرّ به أصلاً (كاشٌ أو كليك).
    """
    return (
        await session.scalar(
            select(DriverSubscription.id)
            .join(SubscriptionPlan, SubscriptionPlan.id == DriverSubscription.plan_id)
            .where(
                DriverSubscription.driver_id == driver_id,
                SubscriptionPlan.duration_type.in_(QUALIFYING_DURATIONS),
                DriverSubscription.expires_at <= _now(),
            )
            .limit(1)
        )
    ) is not None


async def _has_open_dispute(session: AsyncSession, driver_id: uuid.UUID) -> bool:
    return (
        await session.scalar(
            select(Payment.id)
            .join(Ride, Ride.id == Payment.ride_id)
            .where(
                Ride.driver_id == driver_id,
                Payment.status == PaymentStatus.DISPUTED,
            )
            .limit(1)
        )
    ) is not None


async def repaid_count(session: AsyncSession, driver_id: uuid.UUID) -> int:
    """كم سلفةً سدَّدها — **وهو وحدَه ما يُنمّي السقف**.

    «الحمايةُ في الحجم لا في التحصيل» (القرار ٧): أسوأُ خسارةٍ ممكنةٍ لكبتنٍ
    جديدٍ هي اشتراكٌ يوميٌّ واحد، ولا يكبر ما نُقرضه إلا بعد سدادٍ مُثبَت.
    """
    return int(
        await session.scalar(
            select(func.count(DriverAdvance.id)).where(
                DriverAdvance.driver_id == driver_id,
                DriverAdvance.status == AdvanceStatus.REPAID,
            )
        )
        or 0
    )


# ------------------------------------------------------------- الدَّين


async def repaid_amount(session: AsyncSession, advance_id: uuid.UUID) -> Decimal:
    """ما سُدِّد من سلفةٍ بعينها — **مجموعٌ من الدفتر لا عمودٌ عليها**."""
    total = await session.scalar(
        select(func.coalesce(func.sum(wallet.WalletTransaction.amount), 0)).where(
            wallet.WalletTransaction.advance_id == advance_id,
            wallet.WalletTransaction.type == WalletTransactionType.ADVANCE_REPAYMENT,
        )
    )
    return round_money(-Decimal(total or 0))


async def outstanding_for(
    session: AsyncSession, driver_id: uuid.UUID, *, for_update: bool = False
) -> DriverAdvance | None:
    """سلفتُه القائمة إن وُجدت — مقفولةً حين يُكتب على أساسها مال."""
    query = select(DriverAdvance).where(
        DriverAdvance.driver_id == driver_id,
        DriverAdvance.status == AdvanceStatus.OUTSTANDING,
    )
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    return await session.scalar(query)


@dataclass(frozen=True, slots=True)
class Debt:
    advance: DriverAdvance
    remaining: Decimal
    overdue: bool


async def debt_for(session: AsyncSession, driver_id: uuid.UUID) -> Debt | None:
    advance = await outstanding_for(session, driver_id)
    if advance is None:
        return None
    remaining = round_money(advance.amount - await repaid_amount(session, advance.id))
    return Debt(
        advance=advance, remaining=remaining, overdue=advance.due_at <= _now()
    )


# ------------------------------------------------------------- الأهلية


@dataclass(frozen=True, slots=True)
class Eligibility:
    """جوابُ «هل أستطيع؟» كما تعرضه الشاشة — بشروطه لا بحكمٍ مجرَّد."""

    offered: bool
    requirements: list[Requirement]
    cap: Decimal
    currency: str
    debt: Debt | None
    # **شرطُ السداد يُنشر مع العرض** (قرارُ المالك 2026-08-19): السلفةُ تُنشئ
    # **ديناً** لا تُنفق رصيداً، فمن يوافق يجب أن يرى كيف يُسترجَع **قبل** لا
    # بعد. وكانت الشاشةُ تطلب ولا تقول شيئاً عن الاقتطاع.
    deduction_percent: int = 0
    min_kept_amount: Decimal = Decimal("0.000")
    term_days: int = 0

    @property
    def eligible(self) -> bool:
        return (
            self.offered
            and self.cap > 0
            and self.debt is None
            and all(item.met for item in self.requirements)
        )


async def eligibility(
    session: AsyncSession, *, driver: Driver, country: CountryCode
) -> Eligibility:
    """الأهليةُ والسقفُ في نداءٍ واحد — تُحسب لحظةَ السؤال ولا تُخزَّن.

    ومنحُ السلفة ليس مساراً حرجاً (بخلاف التوزيع)، فلا قيمةَ محضَّرةً لها.
    """
    policy = await policy_for(session, country)
    base = await daily_plan_price(session, country)
    currency = currency_for_country(country).value
    debt = await debt_for(session, driver.id)

    if not policy.enabled or base is None:
        return Eligibility(
            offered=False, requirements=[], cap=Decimal("0"),
            currency=currency, debt=debt,
            deduction_percent=policy.deduction_percent,
            min_kept_amount=policy.min_kept_amount,
            term_days=policy.term_days,
        )

    rides = await _completed_rides(session, driver.id)
    requirements = [
        Requirement(key="approved", met=driver.status is DriverStatus.APPROVED),
        Requirement(
            key="past_subscription",
            met=await _has_qualifying_subscription(session, driver.id),
        ),
        Requirement(
            key="completed_rides",
            met=rides >= policy.min_completed_rides,
            value=Decimal(rides),
            needed=Decimal(policy.min_completed_rides),
        ),
        Requirement(
            key="rating",
            met=driver.rating_avg >= policy.min_rating,
            value=driver.rating_avg,
            needed=policy.min_rating,
        ),
        Requirement(
            key="no_open_dispute",
            met=not await _has_open_dispute(session, driver.id),
        ),
        Requirement(key="no_outstanding_advance", met=debt is None),
    ]
    return Eligibility(
        offered=True,
        requirements=requirements,
        cap=await cap_for(session, driver=driver, policy=policy, base=base),
        currency=currency,
        deduction_percent=policy.deduction_percent,
        min_kept_amount=policy.min_kept_amount,
        term_days=policy.term_days,
        debt=debt,
    )


async def cap_for(
    session: AsyncSession, *, driver: Driver, policy: Policy, base: Decimal
) -> Decimal:
    """سقفُ هذا الكبتن — **طبقتان، والأدنى منهما يحكم** (§٣ من المواصفة).

    والمحسوبُ يبدأ من قيمة الاشتراك اليوميِّ وينمو بما سدَّد، محدوداً بسقفِ
    النموّ. **وتخصيصُ الإدارة يخفض ولا يرفع**: `NULL` لا تخصيص، وصفرٌ منعٌ —
    وهما حالتان لا يجوز أن يحملهما رقمٌ واحد (درسُ أصفار `wallet_settings`).
    """
    multiplier = 100 + policy.growth_percent_per_repaid * await repaid_count(
        session, driver.id
    )
    multiplier = min(multiplier, policy.max_multiplier_percent)
    computed = round_money(base * Decimal(multiplier) / 100)
    if driver.advance_cap_override is None:
        return computed
    return min(computed, driver.advance_cap_override)


# ------------------------------------------------------------- الصرف


async def disburse(
    session: AsyncSession,
    *,
    driver: Driver,
    user: User,
    country: CountryCode,
    amount: Decimal,
    approved_by: User | None = None,
) -> DriverAdvance:
    """يصرف سلفةً ويكتب دائنَها في الدفتر — الـcommit للمستدعي.

    **يُستدعى وصفُّ الكبتن مقفولاً**: بغير القفل يقرأ طلبان متزامنان «لا سلفةَ
    قائمة» معاً فيمرّان، ويخرج مالٌ مرتين بسقفٍ واحد. والفهرسُ الجزئيُّ
    (`uq_advance_outstanding`) هو الحارسُ الأخير تحت أي سباق.

    **و`approved_by` هو الفرقُ بين البابين** (القرار ٢): داخل السقف يفتح الطلبُ
    نفسَه البابَ، وفوقه لا يفتحه إلا مشرف — واسمُه يبقى على الصف.
    """
    amount = round_money(amount)
    if amount <= 0:
        raise AdvanceNotAllowed("المبلغ غير صحيح")

    state = await eligibility(session, driver=driver, country=country)
    if not state.offered:
        raise AdvanceUnavailable()
    if state.debt is not None:
        raise AdvanceNotAllowed("لديك سلفةٌ قائمةٌ لم تُسدَّد")
    if not all(item.met for item in state.requirements):
        raise AdvanceNotAllowed("لا تنطبق عليك شروط السلفة بعد")
    # **السقفُ يحكم التلقائيَّ وحدَه**: ما فوقه بابٌ ثانٍ يفتحه مشرفٌ باسمه
    if amount > state.cap and approved_by is None:
        raise AdvanceNotAllowed("المبلغ يتجاوز سقفك — يحتاج موافقة الإدارة")

    policy = await policy_for(session, country)
    advance = DriverAdvance(
        driver_id=driver.id,
        amount=amount,
        currency=currency_for_country(country),
        status=AdvanceStatus.OUTSTANDING,
        # **المهلةُ تُجمَّد هنا** ولا تُقرأ من الإعدادات بعدها
        due_at=_now() + timedelta(days=policy.term_days),
        approved_by=approved_by.id if approved_by else None,
    )
    session.add(advance)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AdvanceNotAllowed("لديك سلفةٌ قائمةٌ لم تُسدَّد") from exc

    await wallet.record(
        session,
        owner=user,
        tx_type=WalletTransactionType.ADVANCE,
        amount=amount,
        advance_id=advance.id,
        created_by=approved_by.id if approved_by else None,
        idempotency_key=f"advance:{advance.id}",
    )
    await session.flush()
    return advance


# ------------------------------------------------------------- السداد


async def _settle_if_clear(
    session: AsyncSession, *, advance: DriverAdvance, driver: Driver, remaining: Decimal
) -> bool:
    """يُغلق السلفةَ ويرفع الإيقافَ **في المسار نفسِه** حين يبلغ المتبقّي صفراً.

    ولا ينتظر دورةً: من سدَّد وبقي ممنوعاً من العمل عشر دقائق يقرأ السدادَ بلا
    أثر، فيسدّد مرةً أخرى أو يتّصل بالدعم.
    """
    if remaining > 0:
        return False
    advance.status = AdvanceStatus.REPAID
    advance.settled_at = _now()
    driver.advance_blocked = False
    await session.flush()
    return True


def deduction_for(
    *, earning: Decimal, remaining: Decimal, policy: Policy
) -> Decimal:
    """كم يُقتطع من أرباح رحلةٍ واحدة — **ثلاثةُ سقوفٍ لا واحد**.

    النسبةُ، والمتبقّي (فلا يُقتطع أكثرُ من الدَّين)، **وما يجب أن يبقى له**:
    اقتطاعٌ يستنزف أرباحَ الرحلة يوقفه عن العمل فيمتنع السدادُ الذي أُريد
    أصلاً — وهو نصُّ قرار المالك في النسبة والحدّ الأدنى.
    """
    if earning <= 0 or remaining <= 0:
        return Decimal("0")
    by_percent = round_money(earning * Decimal(policy.deduction_percent) / 100)
    room = round_money(earning - policy.min_kept_amount)
    return max(Decimal("0"), min(by_percent, remaining, room))


#: **نصُّ الاقتطاع — في سجلٍّ لا في موضع النداء.** جملةٌ تُكتب حيث تُستعمل
#: تُنسخ عند ثاني مُستعمِل، فتفترق النسختان أوّلَ تعديل.
_REPAYMENT_NOTE = "اقتطاع سداد سلفة — المتبقّي {remaining}"
#: **وحين يكون البابُ مغلقاً يُقال ذلك صراحةً**: السدادُ مستمرٌّ لأن الدَّينَ
#: قائم، **وطلبُ سلفةٍ جديدة موقوف** — والجملتان معاً تمنعان قراءةَ النقص
#: عطباً أو ظلماً.
_REPAYMENT_NOTE_WHILE_CLOSED = (
    "اقتطاع سداد سلفة — المتبقّي {remaining}. "
    "السداد مستمرّ، وطلبُ سلفةٍ جديدة موقوفٌ في سوقك حالياً"
)


async def deduct_from_earning(
    session: AsyncSession,
    *,
    driver: Driver,
    user: User,
    country: CountryCode,
    earning: Decimal,
    ride_id: uuid.UUID,
    payment_id: uuid.UUID,
) -> Decimal:
    """اقتطاعُ رحلةٍ — يُنادى من `payments.settle` بعد العمولة.

    **ولا يُفشِل التسويةَ أبداً**: محفظةٌ لا تكفي تعني اقتطاعاً يؤجَّل إلى
    الرحلة التالية، لا دفعةً تُرفض — الدَّينُ باقٍ في جدوله ولم يضع منه شيء.
    وهي قاعدةُ «لا تُفشل رحلةً لأجل أثر» نفسُها، غير أن هذا مالٌ فلا يُبتلع
    صامتاً بل يُسجَّل في اللوج.
    """
    advance = await outstanding_for(session, driver.id, for_update=True)
    if advance is None:
        return Decimal("0")

    policy = await policy_for(session, country)
    remaining = round_money(advance.amount - await repaid_amount(session, advance.id))
    amount = deduction_for(earning=earning, remaining=remaining, policy=policy)
    if amount <= 0:
        return Decimal("0")

    # **والإطفاءُ يمنع الجديدَ ولا يمحو القائم** (SPEC §4، قرارُ المالك
    # 2026-08-23): الدَّينُ حقٌّ نشأ **قبل** الإطفاء، وإيقافُ سداده يجعل
    # المفتاحَ **باباً للتهرّب** — من عليه دَينٌ يستفيد من إطفاءٍ لم يُقرَّر
    # لأجله. **فالاقتطاعُ يمضي.**
    #
    # **والعطبُ ليس الاقتطاع بل صمتُه**: كبتنٌ يُقتطع منه وبابُ السلف مغلقٌ
    # **لا يجد ما يفسّر النقص** — ولا شاشةَ يسأل منها لأن قسمَ السلف مخفيّ.
    # **فالسببُ يسافر مع القيد** ولا تخترعه الشاشة: `reference` يُقرأ في
    # المحفظة **وفي تفصيل الرحلة** (القيدُ يحمل `ride_id`)، ومن يسأل «لماذا
    # نقص هذا المبلغ؟» يسأل عن **رحلةٍ بعينها**.
    note = _REPAYMENT_NOTE if policy.enabled else _REPAYMENT_NOTE_WHILE_CLOSED

    try:
        await wallet.record(
            session,
            owner=user,
            tx_type=WalletTransactionType.ADVANCE_REPAYMENT,
            amount=-amount,
            ride_id=ride_id,
            advance_id=advance.id,
            reference=note.format(remaining=round_money(remaining - amount)),
            idempotency_key=f"advance_repay:{payment_id}",
        )
    except InsufficientBalance:
        logger.warning(
            "تعذّر اقتطاع السلفة من الرحلة %s — الرصيد لا يكفي، ويؤجَّل", ride_id
        )
        return Decimal("0")

    await _settle_if_clear(
        session,
        advance=advance,
        driver=driver,
        remaining=round_money(remaining - amount),
    )
    return amount


async def repay_in_full(
    session: AsyncSession, *, driver: Driver, user: User
) -> DriverAdvance:
    """سدادٌ يدويٌّ كامل — والصفُّ مقفولٌ قبل قراءة المتبقّي.

    بغير القفل تقرأ ضغطتان متزامنتان المتبقّي نفسَه فتخصمان مرتين، وتصير
    سلفةٌ واحدةٌ مسدَّدةً مرتين بمالٍ حقيقيٍّ من محفظته.
    """
    advance = await outstanding_for(session, driver.id, for_update=True)
    if advance is None:
        raise NotFound("لا سلفةَ قائمة")

    remaining = round_money(advance.amount - await repaid_amount(session, advance.id))
    if remaining <= 0:  # pragma: no cover - يُغلق الصفُّ لحظةَ بلوغه صفراً
        await _settle_if_clear(
            session, advance=advance, driver=driver, remaining=remaining
        )
        return advance

    await wallet.record(
        session,
        owner=user,
        tx_type=WalletTransactionType.ADVANCE_REPAYMENT,
        amount=-remaining,
        advance_id=advance.id,
        created_by=user.id,
        reference="سدادٌ يدويٌّ كامل",
        idempotency_key=f"advance_repay_manual:{advance.id}",
    )
    await _settle_if_clear(
        session, advance=advance, driver=driver, remaining=Decimal("0")
    )
    return advance


# ------------------------------------------------------------- الإيقاف


async def overdue_drivers(session: AsyncSession) -> list[DriverAdvance]:
    """السلفُ التي انقضت مهلتُها ولم يُوقَف أصحابُها بعد.

    والمهمّةُ الدوريةُ هي ما يكتب العمودَ المحضَّر — فلا يقرأ التوزيعُ ساعةً
    ولا يجمع دفتراً في مساره الحرج.
    """
    rows = await session.scalars(
        select(DriverAdvance)
        .join(Driver, Driver.id == DriverAdvance.driver_id)
        .where(
            DriverAdvance.status == AdvanceStatus.OUTSTANDING,
            DriverAdvance.due_at <= _now(),
            Driver.advance_blocked.is_(False),
        )
        .order_by(DriverAdvance.due_at)
    )
    return list(rows)


async def driver_user_id(
    session: AsyncSession, driver_id: uuid.UUID
) -> uuid.UUID | None:
    """صاحبُ محفظة الكبتن: `users.id` لا `drivers.id` (SPEC القسم 4)."""
    return await session.scalar(select(Driver.user_id).where(Driver.id == driver_id))


async def due_soon(
    session: AsyncSession, within: timedelta
) -> list[tuple[DriverAdvance, uuid.UUID]]:
    """سلفٌ تقترب مهلتُها ولم تنقضِ بعد — للتنبيه قبل الإيقاف.

    والإزالةُ بمفتاح Redis في المهمّة لا بعمودٍ هنا: التنبيهُ حدثٌ لا سجلّ.
    """
    rows = await session.execute(
        select(DriverAdvance, Driver.user_id)
        .join(Driver, Driver.id == DriverAdvance.driver_id)
        .where(
            DriverAdvance.status == AdvanceStatus.OUTSTANDING,
            DriverAdvance.due_at > _now(),
            DriverAdvance.due_at <= _now() + within,
        )
        .order_by(DriverAdvance.due_at)
    )
    return [(row[0], row[1]) for row in rows.all()]


async def block_for_overdue(
    session: AsyncSession, advance: DriverAdvance
) -> Driver | None:
    """يرفع الإيقافَ عن العمل — **ولا يقطع رحلةً جارية**.

    قاعدةُ كنسِ الاشتراكات نفسُها: `eligible_driver_ids` تمنع الطلبَ التالي،
    ولا شيءَ هنا يمسّ رحلةً في الطريق. وقطعُها يترك راكباً على الرصيف ويُطلق
    تنبيهَ «انقطع اتصال الكبتن» على من لم ينقطع.
    """
    driver = await session.get(
        Driver, advance.driver_id, with_for_update=True, populate_existing=True
    )
    if driver is None or driver.advance_blocked:  # pragma: no cover - سباقُ دورتين
        return None
    if advance.status is not AdvanceStatus.OUTSTANDING:  # pragma: no cover
        return None
    driver.advance_blocked = True
    await session.flush()
    return driver


async def blocks_daily_subscription(
    session: AsyncSession, driver_id: uuid.UUID
) -> bool:
    """هل يُمنع من شراء اشتراكٍ يوميٍّ الآن؟ (القرار ٥)

    **وإلا موّلت السلفةُ نفسَها**: سلفةٌ بقيمة اشتراكٍ يوميٍّ تُشترى بها
    اشتراكاتٌ يوميةٌ إلى ما لا نهاية، فلا يُسدَّد شيءٌ ولا يتوقف أحد. والمنعُ
    يبدأ **بانقضاء المهلة** لا بالصرف: من سلفتُه في مهلتها يعمل بها كما ينبغي.
    """
    debt = await debt_for(session, driver_id)
    return debt is not None and debt.overdue


async def write_off(
    session: AsyncSession, *, advance_id: uuid.UUID, admin: User, reason: str
) -> DriverAdvance:
    """شطبُ دَينٍ بقرارٍ إداريٍّ مسجَّل (القرار ٧) — والـcommit للمستدعي.

    **ولا شطبَ آليّ بعد التسعين**: المدّةُ تجعله *مقترحاً*، والاعترافُ بالخسارة
    فعلُ إنسانٍ باسمه — وهو نصُّ القرار. **ولا قيدَ يُكتب في الدفتر**: لم يتحرك
    مالٌ في محفظة أحد، والشطبُ اعترافٌ محاسبيٌّ بأن ما خرج لن يعود. وكتابةُ
    «تسويةٍ» وهميةٍ تجعل الدفترَ يقول إن الكبتنَ سدَّد، وهو لم يفعل.

    **ويرفع الإيقاف**: إبقاءُ الحساب موقوفاً بعد الشطب عقوبةٌ على دَينٍ لم يعد
    قائماً في دفاترنا.
    """
    advance = await session.get(
        DriverAdvance, advance_id, with_for_update=True, populate_existing=True
    )
    if advance is None:
        raise NotFound("السلفة غير موجودة")
    if advance.status is not AdvanceStatus.OUTSTANDING:
        raise AdvanceNotAllowed("هذه السلفة ليست قائمة")

    advance.status = AdvanceStatus.WRITTEN_OFF
    advance.written_off_at = _now()
    advance.written_off_by = admin.id
    advance.writeoff_reason = reason.strip()

    driver = await session.get(
        Driver, advance.driver_id, with_for_update=True, populate_existing=True
    )
    if driver is not None:
        driver.advance_blocked = False

    from app.models.enums import AuditAction
    from app.services import audit

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="driver_advance",
        entity_id=advance.id,
        # **السببُ المكتوبُ هو محتوى القيد نفسُه** — استثناءُ «أسماءُ الحقول لا
        # قيمُها»، كسبب إيقاف الكبتن وسببِ إطفاء حارس
        details={"status": advance.status.value, "reason": advance.writeoff_reason},
    )
    await session.flush()
    return advance


def is_writeoff_candidate(advance: DriverAdvance, *, now: datetime | None = None) -> bool:
    """هل مضى على انقضاء مهلتها ما يجعل الشطبَ مطروحاً؟ (القرار ٧)"""
    moment = now or _now()
    return (
        advance.status is AdvanceStatus.OUTSTANDING
        and advance.due_at + timedelta(days=WRITEOFF_AFTER_DAYS) <= moment
    )
