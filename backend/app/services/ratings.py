"""التقييم المتبادل بعد الرحلة (SPEC القسم 5.9).

كل طرف يقيّم الآخر مرة واحدة، وبعد `completed` وحدها: تقييمُ رحلةٍ ملغاة
تقييمٌ لما لم يقع. التقييم اختياري فلا شيء يحجبه عن الطرف الآخر إن امتنع أحدهما.

`drivers.rating_avg` **مشتق لا مُراكَم**: يُعاد حسابه من الجدول كله بعد كل
تقييم يكتبه راكب، لا يُحدَّث بمتوسطٍ متدحرج. المتوسط المتدحرج يعتمد على عدد
سابقٍ يُخزَّن، وأيُّ قيدٍ ضاع أو أُعيد يجعله ينحرف انحرافاً لا يُكتشف — تماماً
كسبب حساب رصيد المحفظة من دفترها في `services/wallet.py`.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AlreadyRated, RatingNotAllowed
from app.models.driver import Driver
from app.models.enums import RatingRaterType, RideStatus, UserRole
from app.models.rating import Rating
from app.models.ride import Ride
from app.models.user import User

_RATING_STEP = Decimal("0.01")  # دقة `drivers.rating_avg` — NUMERIC(3,2)


async def list_for_ride(session: AsyncSession, ride_id: uuid.UUID) -> Sequence[Rating]:
    return (
        await session.scalars(
            select(Rating).where(Rating.ride_id == ride_id).order_by(Rating.created_at)
        )
    ).all()


def rater_type_for(ride: Ride, user: User) -> RatingRaterType:
    """أيّ الطرفين هذا المستخدم — ومن ليس طرفاً لا يقيّم.

    الدورُ وحده لا يكفي: كبتنٌ آخر دورُه `driver` ليس طرفاً في هذه الرحلة.
    """
    if ride.rider_id == user.id:
        return RatingRaterType.RIDER
    if (
        user.role == UserRole.DRIVER
        and ride.driver is not None
        and ride.driver.user_id == user.id
    ):
        return RatingRaterType.DRIVER
    raise RatingNotAllowed("لست طرفاً في هذه الرحلة")


async def rate(
    session: AsyncSession,
    *,
    ride: Ride,
    rater: User,
    stars: int,
    comment: str | None,
) -> Rating:
    """يسجّل تقييم طرفٍ ويحدّث متوسط الكبتن إن كان المقيِّم راكباً."""
    if ride.status != RideStatus.COMPLETED:
        raise RatingNotAllowed("التقييم بعد اكتمال الرحلة")

    rater_type = rater_type_for(ride, rater)
    rating = Rating(
        ride_id=ride.id,
        rater_type=rater_type,
        rater_id=rater.id,
        stars=stars,
        comment=(comment or "").strip() or None,
    )
    session.add(rating)

    try:
        await session.flush()
    except IntegrityError as exc:
        # القيد الفريد `(ride_id, rater_type)` — ضغطتان متزامنتان لا تنتجان
        # تقييمين، والحارس في القاعدة لا في فحصٍ سابقٍ يمكن أن يُسبَق
        await session.rollback()
        raise AlreadyRated() from exc

    if rater_type == RatingRaterType.RIDER and ride.driver_id is not None:
        await refresh_driver_average(session, ride.driver_id)

    return rating


async def refresh_driver_average(
    session: AsyncSession, driver_id: uuid.UUID
) -> Decimal:
    """يعيد حساب `rating_avg` من كل تقييمات الركاب لرحلات هذا الكبتن."""
    average = await session.scalar(
        select(func.avg(Rating.stars))
        .join(Ride, Ride.id == Rating.ride_id)
        .where(
            Ride.driver_id == driver_id,
            Rating.rater_type == RatingRaterType.RIDER,
        )
    )
    value = (
        Decimal("0.00")
        if average is None
        else Decimal(str(average)).quantize(_RATING_STEP, rounding=ROUND_HALF_UP)
    )

    driver = await session.get(Driver, driver_id)
    if driver is not None:
        driver.rating_avg = value
    return value
