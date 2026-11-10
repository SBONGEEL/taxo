"""**ملخّصُ أرباح الكبتن الأسبوعيّ** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٧).

**الأسبوعُ الماضي كاملاً** — سبعةُ أيامٍ بيوم الدولة تنتهي بمنتصف ليل اليوم — **ومقارنتُه بالأسبوع الذي قبله كاملاً**. والأرقامُ كلُّها
من `earnings.summary` نفسِه (الدفترُ والدفعاتُ ودقائقُ الاتصال) لا من حسابٍ ثانٍ يفترق عنه: **«ما كسبه فعلاً»** (`earned`) والرحلاتُ
المكتملةُ وساعاتُ الاتصال. **ويضيف ثلاثةً**: أفضلُ يومٍ (أعلى صافٍ)، وأفضلُ ساعاتٍ (أكثرُها رحلاتٍ مكتملةً بساعة الدولة)، والتقييمُ الذي
تلقّاه في الأسبوع. **والنسبةُ تُحسب هنا** — لا قسمةَ مالٍ في التطبيق (§14).

**وإشعارٌ كلَّ سبت** (`tasks/weekly_digest.py`) لمن أكمل رحلةً في الأسبوع — **بلا رقمٍ في نصّه**: الأرقامُ في الشاشة.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.driver import Driver
from app.models.enums import CountryCode, RatingRaterType, RideStatus
from app.models.rating import Rating
from app.models.ride import Ride
from app.services import earnings
from app.services.stats import _zone

#: أفضلُ الساعات — ثلاثٌ تُقرأ، وأربعٌ وعشرون جدول
TOP_HOURS = 3


@dataclass(frozen=True, slots=True)
class HourCount:
    hour: int
    rides: int


@dataclass(frozen=True, slots=True)
class WeeklyDigest:
    from_at: datetime
    to_at: datetime
    currency: str
    earned: Decimal
    previous_earned: Decimal
    #: التغيّرُ في «ما كسبه فعلاً» عن الأسبوع السابق بالمئة — و`None` بلا أساس (أسبوعٌ سابقٌ بصفر)
    earned_change_percent: int | None
    completed_rides: int
    previous_rides: int
    online_minutes: int | None
    commission: Decimal
    directly_collected: Decimal
    best_day: date | None
    best_day_net: Decimal | None
    best_hours: tuple[HourCount, ...]
    rating_average: float | None
    rating_count: int


def _week_end(zone, now: datetime) -> datetime:
    """آخرُ لحظةٍ من أمس بساعة الدولة — فالأسبوعُ سبعةُ أيامٍ كاملةٍ تنتهي به."""
    midnight = datetime.combine(now.astimezone(zone).date(), time.min, tzinfo=zone)
    return (midnight - timedelta(microseconds=1)).astimezone(UTC)


async def _best_hours(
    session: AsyncSession, driver_id: uuid.UUID, zone_name: str, from_at: datetime, to_at: datetime
) -> tuple[HourCount, ...]:
    hour = func.extract("hour", func.timezone(zone_name, Ride.completed_at))
    rows = (
        await session.execute(
            select(hour.label("h"), func.count().label("n"))
            .where(
                Ride.driver_id == driver_id,
                Ride.status == RideStatus.COMPLETED,
                Ride.completed_at >= from_at,
                Ride.completed_at <= to_at,
            )
            .group_by("h")
            .order_by(func.count().desc(), "h")
            .limit(TOP_HOURS)
        )
    ).all()
    return tuple(HourCount(hour=int(h), rides=int(n)) for h, n in rows)


async def _rating(
    session: AsyncSession, driver_id: uuid.UUID, from_at: datetime, to_at: datetime
) -> tuple[float | None, int]:
    average, count = (
        await session.execute(
            select(func.avg(Rating.stars), func.count())
            .select_from(Rating)
            .join(Ride, Rating.ride_id == Ride.id)
            .where(
                Ride.driver_id == driver_id,
                Rating.rater_type == RatingRaterType.RIDER,
                Rating.created_at >= from_at,
                Rating.created_at <= to_at,
            )
        )
    ).one()
    return (round(float(average), 2) if average is not None else None), int(count)


async def weekly(
    session: AsyncSession, *, driver: Driver, user_id: uuid.UUID, country: CountryCode, now: datetime
) -> WeeklyDigest:
    zone = await _zone(session, country)
    end = _week_end(zone, now)
    current = await earnings.summary(
        session, driver=driver, user_id=user_id, country=country, period="week", now=end
    )
    previous = await earnings.summary(
        session, driver=driver, user_id=user_id, country=country, period="week", now=end - timedelta(days=7)
    )
    best = max(current.days, key=lambda item: item.net, default=None)
    if best is not None and best.net <= 0:
        best = None
    average, count = await _rating(session, driver.id, current.from_at, current.to_at)
    return WeeklyDigest(
        from_at=current.from_at,
        to_at=current.to_at,
        currency=current.currency,
        earned=current.earned,
        previous_earned=previous.earned,
        earned_change_percent=earnings._change_percent(current.earned, previous.earned),
        completed_rides=current.completed_rides,
        previous_rides=previous.completed_rides,
        online_minutes=current.online_minutes,
        commission=current.commission,
        directly_collected=current.directly_collected,
        best_day=best.day if best is not None else None,
        best_day_net=best.net if best is not None else None,
        best_hours=await _best_hours(session, driver.id, zone.key, current.from_at, current.to_at),
        rating_average=average,
        rating_count=count,
    )


async def recipients(session: AsyncSession, *, now: datetime) -> list[tuple[uuid.UUID, CountryCode]]:
    """**من أكمل رحلةً في الأيام الثمانية الماضية** — أوسعُ من الأسبوع بيومٍ ليغطّي فرقَ المِنطقتين، والملخّصُ نفسُه يُحسب بيوم دولته."""
    from app.models.user import User

    since = now - timedelta(days=8)
    rows = (
        await session.execute(
            select(Driver.user_id, User.country_code)
            .join(User, User.id == Driver.user_id)
            .where(
                Driver.id.in_(
                    select(Ride.driver_id).where(
                        Ride.status == RideStatus.COMPLETED, Ride.completed_at >= since
                    )
                )
            )
        )
    ).all()
    return [(user_id, country) for user_id, country in rows]
