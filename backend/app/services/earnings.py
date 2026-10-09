"""ملخّصُ أرباح الكبتن (SPEC القسم 9 و12/7، `FUTURE-FEATURES` بند 17).

**والقسم 9 يكتب الرصيد جملةً واحدة**: «أرباح − عمولات − الاشتراكات المدفوعة
منها − سحوبات». وهذه الشاشة تعرض أولَ حدّين على نافذةٍ زمنية، ولذلك تُقرأ من
**الدفتر** لا من الرحلات: القيدُ هو ما وقع فعلاً، والرحلةُ قد تكون بلا قيد.

**وثلاثةُ أرقامٍ لا رقمان، لأن الكاش وكليك لا يمرّان بالمحفظة** (القسم 9):

- **ما دخل المحفظة**: مجموع `ride_earning` — وهو بطاقةٌ ومحفظةٌ فقط.
- **ما خرج منها عمولةً**: مجموع `commission`، ويُخصم في الحالتين — حتى على
  رحلةٍ نقدية حين يكون النطاق `all_rides`. فقد تكون العمولةُ أكبر من الأرباح
  في يومٍ كلُّه كاش، والصافي سالباً. **ولا يُخفى ذلك**: رقمٌ يُقصّ عند الصفر
  يخفي عن الكبتن أن يومه كلّفه.
- **وما قبضه بيده**: مجموع الدفعات المؤكدة كاشاً وكليكاً. والقسم 9 يوجب
  إظهاره **موسوماً «مُحصَّل مباشرة»** — لا لأنه يزيد رصيده، بل لأن كشفاً
  يخفي نصف دخله كشفٌ لا يُصدَّق.

**والنافذةُ يومُ الدولة** بمِنطقتها المخزَّنة، كنافذة «نظرة عامة» تماماً: لا
يقصّ خادمُ UTC ثلاث ساعاتٍ من أول اليوم في عمّان.

**وأيّامُ النافذة ونسبةُ تغيّرها منذ §٦٢-ج/٣٨** (رسمُ C09): صافي كلِّ يومٍ بيوم
الدولة — **وأيّامُها تُجمع إلى `net` نفسِه** لا إلى رقمٍ ثانٍ، فعمودٌ لا يطابق
الرقمَ فوقه يُقرأ عطباً — ونسبةٌ عن **النافذة السابقة المساوية لها حتى الساعة
نفسِها**: اليومُ إلى التاسعة يُقارَن بأمسِ إلى التاسعة لا بأمسِ كاملاً، وإلّا
قرأ الكبتنُ كلَّ صباحٍ هبوطاً لم يقع.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.driver import Driver
from app.models.enums import (
    CountryCode,
    PaymentStatus,
    RideStatus,
    WalletOwnerType,
    WalletTransactionType,
)
from app.models.payment import DIRECTLY_COLLECTED_METHODS, Payment
from app.models.ride import Ride
from app.models.wallet import WalletTransaction
from app.services import pricing
from app.services.stats import PERIOD_DAYS, _days_in, _window, _zone

# نوافذُ الشاشة الثلاث كما يسمّيها القسم 12/7 — نفس مفاتيح «نظرة عامة»
PERIODS = tuple(PERIOD_DAYS)

# **أركانُ الصافي بإشاراتها** — هي هي حدودُ `net` في `summary` (دخلٌ يزيده وخصمٌ
# ينقصه)، فيُجمع اليومُ بالقاعدة نفسِها لا بقاعدةٍ ثانيةٍ تفترق عنها أوّلَ ركنٍ يُضاف
NET_SIGN: dict[WalletTransactionType, int] = {
    WalletTransactionType.RIDE_EARNING: 1,
    WalletTransactionType.TIP: 1,
    WalletTransactionType.COMMISSION: -1,
    WalletTransactionType.ADVANCE_REPAYMENT: -1,
}


@dataclass(frozen=True, slots=True)
class EarningsDay:
    """يومٌ من النافذة **بيوم الدولة** (§٦٢-ج/٣٨)."""

    day: date
    net: Decimal
    # **حصّةُ اليوم من أكبر أيّام النافذة، بإشارته** (−١…١): العمودُ يُرسم بها
    # كما تصل، فلا قسمةَ مالٍ في الواجهة (§14) — ويومٌ سالبٌ يتدلّى تحت الخطّ
    peak_share: float


@dataclass(frozen=True, slots=True)
class Earnings:
    period: str
    from_at: datetime
    to_at: datetime
    currency: str

    wallet_earnings: Decimal
    commission: Decimal
    # **سطرٌ ثالثٌ مستقل** (المرحلة 12-و): البقشيشُ دخلٌ دخل المحفظة **بلا
    # عمولةٍ عليه**، وهو الوحيد كذلك. ودمجُه في `wallet_earnings` يجعل الكبتن
    # يرى «ما دخل» يزيد بلا أن يزيد «ما خرج عمولةً» فلا يتّسق الرقمان لمن
    # يجمعهما بيده — والسطرُ هو ما يفسّر الفرق
    tips: Decimal
    # **سطرٌ خامسٌ منذ البند ١٥**: ما اقتُطع سداداً لسلفة. ورقمٌ ينقص من
    # الأرباح بلا سببٍ مكتوبٍ في الكشف يُقرأ عطباً، فيُسأل عنه الدعمُ مرةً
    # واحدةً لكل كبتن — نفسُ سببِ إفراد سطر البقشيش
    advance_repaid: Decimal
    net: Decimal
    directly_collected: Decimal
    completed_rides: int
    # **صافي كلِّ يومٍ في النافذة** (§٦٢-ج/٣٨) — يومٌ بلا قيدٍ صفٌّ بصفر،
    # ومجموعُها `net` بعينه
    days: tuple[EarningsDay, ...]
    # **التغيّرُ عن النافذة السابقة المساوية لها حتى الساعة نفسِها**، بالمئة
    # مقرَّباً — و`None` حين لا أساسَ له (انظر `_change_percent`)
    change_percent: int | None
    # **دقائقُ اتصاله في أيّام النافذة** (§٦٢-ج/٣٧، C04 «4:10 ساعة» · C09 «31 ساعة») — و`None` حيث مفتاحُ
    # `work_hours_enabled` مطفأ: «لم يُقَس» لا «صفرُ ساعة»
    online_minutes: int | None = None


async def _ledger_sum(
    session: AsyncSession,
    user_id: uuid.UUID,
    kind: WalletTransactionType,
    from_at: datetime,
    to_at: datetime,
) -> Decimal:
    """مجموعُ نوعٍ من القيود على النافذة — **بالقيمة المطلقة**.

    إشارةُ المبلغ يمليها النوع (قيدُ فحصٍ في القاعدة)، فالعمولةُ سالبةٌ دائماً.
    والشاشةُ تعرض «كم اقتُطع» لا «سالب كم» — والطرحُ يقع هنا مرةً واحدة.
    """
    total = await session.scalar(
        select(func.coalesce(func.sum(func.abs(WalletTransaction.amount)), 0)).where(
            WalletTransaction.owner_id == user_id,
            WalletTransaction.owner_type == WalletOwnerType.DRIVER,
            WalletTransaction.type == kind,
            WalletTransaction.created_at >= from_at,
            WalletTransaction.created_at <= to_at,
        )
    )
    # **ثلاثُ منازل دائماً**: `Decimal(0)` يخرج «0» فتعرضه الشاشة «٠» بينما
    # كلُّ مالٍ آخر فيها «٠.٠٠٠». والتقريبُ في الخدمة لا في الواجهة —
    # تنسيقُ المال قرارُ عرض، لكن **عددَ منازله جزءٌ من القيمة** هنا
    return pricing.round_money(Decimal(total or 0))


async def _net_by_day(
    session: AsyncSession,
    user_id: uuid.UUID,
    zone: ZoneInfo,
    from_at: datetime,
    to_at: datetime,
) -> dict[date, Decimal]:
    """صافي كلِّ يومٍ فيه قيد — **استعلامٌ واحدٌ مجمَّعٌ بيوم الدولة** لا صفوفٌ تُنقل.

    `timezone(المِنطقة، created_at)` يقلب اللحظةَ إلى ساعة الدولة قبل أن يُؤخذ
    يومُها: قيدُ الحادية عشرة ليلاً في عمّان يومُه يومُ عمّان، لا الغدُ الذي
    يراه خادمُ UTC — قاعدةُ `stats.reports` نفسُها.
    """
    day = func.date(func.timezone(str(zone), WalletTransaction.created_at)).label("day")
    rows = await session.execute(
        select(day, WalletTransaction.type, func.sum(func.abs(WalletTransaction.amount)))
        .where(
            WalletTransaction.owner_id == user_id,
            WalletTransaction.owner_type == WalletOwnerType.DRIVER,
            WalletTransaction.type.in_(tuple(NET_SIGN)),
            WalletTransaction.created_at >= from_at,
            WalletTransaction.created_at <= to_at,
        )
        .group_by(day, WalletTransaction.type)
    )
    by_day: dict[date, Decimal] = {}
    for value, kind, total in rows.all():
        by_day[value] = by_day.get(value, Decimal(0)) + NET_SIGN[kind] * Decimal(total)
    # **وزائدُ تقريب سداد السلفة المردودُ يُنقص سدادَها** (SPEC §٧٠-ج/٦، `advances.repay_in_full`) — قيدُ `rounding` بمعرّف
    # السلفة. ومطفأً لا قيدَ منه فلا صفَّ هنا
    returned = await session.execute(
        select(day, func.sum(WalletTransaction.amount))
        .where(
            WalletTransaction.owner_id == user_id,
            WalletTransaction.owner_type == WalletOwnerType.DRIVER,
            WalletTransaction.type == WalletTransactionType.ROUNDING,
            WalletTransaction.advance_id.is_not(None),
            WalletTransaction.created_at >= from_at,
            WalletTransaction.created_at <= to_at,
        )
        .group_by(day)
    )
    for value, total in returned.all():
        by_day[value] = by_day.get(value, Decimal(0)) + Decimal(total)
    return by_day


async def _advance_rounding_returned(
    session: AsyncSession, user_id: uuid.UUID, from_at: datetime, to_at: datetime
) -> Decimal:
    """**زائدُ تقريب سداد السلفة المردود** في النافذة — يُطرح من «سُدِّد للسلفة» فيُقرأ المسدَّدُ لا المقرَّب."""
    total = await session.scalar(
        select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
            WalletTransaction.owner_id == user_id,
            WalletTransaction.owner_type == WalletOwnerType.DRIVER,
            WalletTransaction.type == WalletTransactionType.ROUNDING,
            WalletTransaction.advance_id.is_not(None),
            WalletTransaction.created_at >= from_at,
            WalletTransaction.created_at <= to_at,
        )
    )
    return Decimal(total or 0)


def _change_percent(current: Decimal, previous: Decimal) -> int | None:
    """التغيّرُ بالمئة مقرَّباً — **ولا رقمَ حيث لا أساسَ له**.

    - **سابقٌ صفرٌ أو سالب**: لا يُقسم عليه؛ و«+٣٠٠٪» عن أسبوعٍ خسر فيه الكبتن
      عمولةً لا يقول شيئاً يصدق.
    - **حاضرٌ سالب**: «−١٥٠٪» صحيحٌ حساباً ولا يُقرأ — وتنبيهُ الشاشة القائم
      («العمولة تجاوزت أرباح المحفظة») هو ما يقول ذلك اليوم.
    """
    if previous <= 0 or current < 0:
        return None
    return int(((current - previous) * 100 / previous).to_integral_value(ROUND_HALF_UP))


async def summary(
    session: AsyncSession,
    *,
    driver: Driver,
    user_id: uuid.UUID,
    country: CountryCode,
    period: str,
    now: datetime,
) -> Earnings:
    """أرقامُ الشاشة — **مجموعةً في القاعدة** لا صفوفاً تُجمع في التطبيق.

    نفس قاعدة `services/stats.py`: تطبيقٌ يجمع صفحةً مسقوفة يعرض رقماً لا
    يطابق الدفتر، ويختلف بين جهازين.
    """
    from app.core.currency import currency_for_country

    zone = await _zone(session, country)
    from_at, to_at = _window(zone, period, now)

    wallet_earnings = await _ledger_sum(
        session, user_id, WalletTransactionType.RIDE_EARNING, from_at, to_at
    )
    commission = await _ledger_sum(
        session, user_id, WalletTransactionType.COMMISSION, from_at, to_at
    )
    tips = await _ledger_sum(
        session, user_id, WalletTransactionType.TIP, from_at, to_at
    )
    advance_repaid = await _ledger_sum(
        session, user_id, WalletTransactionType.ADVANCE_REPAYMENT, from_at, to_at
    )
    # **ناقصَ زائد التقريب المردود** (§٧٠-ج/٦) — ومطفأً صفرٌ فالرقمُ كما كان حرفاً
    returned = await _advance_rounding_returned(session, user_id, from_at, to_at)
    if returned:
        advance_repaid = pricing.round_money(advance_repaid - returned)

    # ما قبضه بيده: دفعاتٌ مؤكدة بقناةٍ لا تمر بالمنصة، على رحلاته هو
    directly_collected = await session.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .select_from(Payment)
        .join(Ride, Payment.ride_id == Ride.id)
        .where(
            Ride.driver_id == driver.id,
            Payment.status == PaymentStatus.CONFIRMED,
            Payment.method.in_(DIRECTLY_COLLECTED_METHODS),
            Payment.created_at >= from_at,
            Payment.created_at <= to_at,
        )
    )

    completed = await session.scalar(
        select(func.count())
        .select_from(Ride)
        .where(
            Ride.driver_id == driver.id,
            Ride.status == RideStatus.COMPLETED,
            Ride.completed_at.is_not(None),
            Ride.completed_at >= from_at,
            Ride.completed_at <= to_at,
        )
    )

    # ── أيّامُ النافذة، ثمّ النافذةُ السابقةُ المساويةُ لها (§٦٢-ج/٣٨) ──
    found = await _net_by_day(session, user_id, zone, from_at, to_at)
    nets = [
        (value, pricing.round_money(found.get(value, Decimal(0))))
        for value in _days_in(zone, from_at, to_at)
    ]
    peak = max((abs(net) for _, net in nets), default=Decimal(0))
    days = tuple(
        EarningsDay(
            day=value,
            net=net,
            peak_share=float(round(net / peak, 4)) if peak else 0.0,
        )
        for value, net in nets
    )
    # **بساعة الحائط في مِنطقة الدولة** لا بطرح ساعاتٍ من UTC: النافذةُ السابقة
    # تبدأ من منتصف ليلٍ محلّيٍّ وتنتهي عند الساعة نفسِها قبل فترةٍ بطولها
    span = timedelta(days=PERIOD_DAYS.get(period, 1))
    previous = await _net_by_day(
        session,
        user_id,
        zone,
        (from_at.astimezone(zone) - span).astimezone(from_at.tzinfo),
        (to_at.astimezone(zone) - span).astimezone(to_at.tzinfo),
    )
    current_net = pricing.round_money(
        wallet_earnings + tips - commission - advance_repaid
    )
    # **ساعاتُ العمل بأيّام النافذة نفسِها** (§٦٢-ج/٣٧) — من يوم السوق الأول فيها إلى آخره
    from app.models.enums import FeatureKey
    from app.services import activity, settings_service

    online_minutes = (
        await activity.minutes_between(
            session, driver.id, from_at.astimezone(zone).date(), to_at.astimezone(zone).date()
        )
        if await settings_service.is_feature_enabled(session, country, FeatureKey.WORK_HOURS_ENABLED)
        else None
    )

    return Earnings(
        period=period,
        from_at=from_at,
        to_at=to_at,
        currency=currency_for_country(country).value,
        wallet_earnings=wallet_earnings,
        commission=commission,
        tips=tips,
        # **قد يكون سالباً** ولا يُقصّ عند الصفر: يومٌ كلُّه كاش بعمولةٍ
        # `all_rides` يترك على الكبتن عمولةً بلا أرباحَ تقابلها، وإخفاءُ ذلك
        # يجعله يكتشف نقصان رصيده بلا سبب ظاهر
        # والبقشيشُ داخلٌ في الصافي: هو مالٌ **دخل المحفظة فعلاً**، وصافيٌّ لا
        # يشمله لا يطابق ما يراه صاحبُه في رصيده
        advance_repaid=advance_repaid,
        # **والاقتطاعُ يدخل الصافي**: مالٌ خرج من المحفظة فعلاً، وصافيٌّ لا
        # يطرحه لا يطابق ما يراه صاحبُه في رصيده — نفسُ حجّة إدخال البقشيش
        net=current_net,
        directly_collected=pricing.round_money(Decimal(directly_collected or 0)),
        completed_rides=int(completed or 0),
        days=days,
        change_percent=_change_percent(
            current_net, pricing.round_money(sum(previous.values(), Decimal(0)))
        ),
        online_minutes=online_minutes,
    )
