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
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

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
from app.services.stats import PERIOD_DAYS, _window, _zone

# نوافذُ الشاشة الثلاث كما يسمّيها القسم 12/7 — نفس مفاتيح «نظرة عامة»
PERIODS = tuple(PERIOD_DAYS)


@dataclass(frozen=True, slots=True)
class Earnings:
    period: str
    from_at: datetime
    to_at: datetime
    currency: str

    wallet_earnings: Decimal
    commission: Decimal
    net: Decimal
    directly_collected: Decimal
    completed_rides: int


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

    return Earnings(
        period=period,
        from_at=from_at,
        to_at=to_at,
        currency=currency_for_country(country).value,
        wallet_earnings=wallet_earnings,
        commission=commission,
        # **قد يكون سالباً** ولا يُقصّ عند الصفر: يومٌ كلُّه كاش بعمولةٍ
        # `all_rides` يترك على الكبتن عمولةً بلا أرباحَ تقابلها، وإخفاءُ ذلك
        # يجعله يكتشف نقصان رصيده بلا سبب ظاهر
        net=pricing.round_money(wallet_earnings - commission),
        directly_collected=pricing.round_money(Decimal(directly_collected or 0)),
        completed_rides=int(completed or 0),
    )
