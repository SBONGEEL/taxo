"""إحصاءات لوحة الإدارة (SPEC القسم 13/1).

**التجميع هنا حصراً.** القسم 14 يحصر الحساب المالي في الخلفية، والمبدأ نفسه
يمتد إلى العدّ: لوحةٌ تجمع صفوفاً بيدها تعرض رقماً لا يطابق قاعدة البيانات
حين تُقصّ الصفحة عند خمسين، ولا يطابق نفسه بين متصفحين. فكلُّ رقمٍ في «نظرة
عامة» يخرج من استعلامٍ واحد أو من Redis، ولا تجمع الواجهة شيئاً.

**واليومُ يومُ الدولة لا يومُ الخادم.** «رحلات اليوم» في عمّان تبدأ منتصف ليل
عمّان، وخادمٌ يعمل بـUTC يقصّ ثلاث ساعاتٍ من أولها ويضم ثلاثاً من أمس. فالنافذة
تُحسب بمِنطقة الدولة المخزَّنة في `notification_settings.timezone` — وهي نفسها
التي تحكم ساعات الهدوء، فلا يفترق تقويمان في نظامٍ واحد.

**والمتصلون الآن من Redis لا من عمود.** `drivers.is_online` يقول «رفع المفتاح»
لا «حاضرٌ الآن»: من أُغلق تطبيقه فجأةً يبقى عموده مرفوعاً حتى ينقضي مفتاح
حضوره. والعدّ الصادق هو عدّ من له مفتاح حضورٍ حيّ (`geo:presence:*`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.driver import Driver, DriverDocument
from app.models.enums import (
    CountryCode,
    DocumentReviewStatus,
    PaymentMethod,
    PaymentStatus,
    RideStatus,
    WithdrawalStatus,
)
from app.models.payment import Payment
from app.models.ride import ACTIVE_RIDER_STATUSES, Ride
from app.models.subscription import DriverSubscription
from app.models.user import User
from app.models.wallet import WithdrawalRequest
from app.services import campaigns, geo, subscriptions

# نوافذ التقرير الثلاث كما في `DESIGN.md` §3.2 (اليوم/الأسبوع/الشهر)
PERIOD_DAYS = {"today": 1, "week": 7, "month": 30}
DEFAULT_TIMEZONE = "Asia/Amman"


@dataclass(frozen=True, slots=True)
class Overview:
    """ما ترسمه «نظرة عامة» — أرقامٌ جاهزة لا صفوفٌ تُجمع في الواجهة."""

    period: str
    from_at: datetime
    to_at: datetime
    completed_rides: int
    cancelled_rides: int
    revenue: Decimal
    online_drivers: int
    active_rides: int
    active_subscriptions: int
    open_disputes: int
    pending_documents: int
    pending_withdrawals: int
    rides_by_hour: list[int]
    payment_mix: dict[str, int]


async def _zone(session: AsyncSession, country: CountryCode) -> ZoneInfo:
    """مِنطقة الدولة من إعداداتها — نفس مصدر ساعات الهدوء."""
    setting = await campaigns.get_settings(session, country)
    name = setting.timezone if setting else DEFAULT_TIMEZONE
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):  # pragma: no cover - إعداد خاطئ
        return ZoneInfo(DEFAULT_TIMEZONE)


def _window(zone: ZoneInfo, period: str, now: datetime) -> tuple[datetime, datetime]:
    """بداية النافذة ونهايتها **بمِنطقة الدولة**، مُعادةً بـUTC للاستعلام."""
    days = PERIOD_DAYS.get(period, 1)
    local_now = now.astimezone(zone)
    start_local = datetime.combine(
        local_now.date() - timedelta(days=days - 1), time.min, tzinfo=zone
    )
    return start_local.astimezone(now.tzinfo or zone), now


async def overview(
    session: AsyncSession,
    redis: Redis,
    *,
    country: CountryCode,
    period: str,
    now: datetime,
) -> Overview:
    """كلُّ أرقام الشاشة — استعلاماتٌ محدودة لا صفوفٌ تُنقل إلى الواجهة."""
    zone = await _zone(session, country)
    from_at, to_at = _window(zone, period, now)

    in_window = (
        Ride.country_code == country,
        Ride.created_at >= from_at,
        Ride.created_at <= to_at,
    )

    completed = await session.scalar(
        select(func.count())
        .select_from(Ride)
        .where(*in_window, Ride.status == RideStatus.COMPLETED)
    )
    cancelled = await session.scalar(
        select(func.count())
        .select_from(Ride)
        .where(
            *in_window,
            Ride.status.in_(
                (
                    RideStatus.CANCELLED_BY_RIDER,
                    RideStatus.CANCELLED_BY_DRIVER,
                )
            ),
        )
    )
    # الإيراد من `final_fare` المحسوب على المسار الفعلي، والمقدَّر احتياطاً
    # لرحلةٍ اكتملت قبل أن يُسجَّل لها مسار
    revenue = await session.scalar(
        select(
            func.coalesce(
                func.sum(func.coalesce(Ride.final_fare, Ride.estimated_fare)), 0
            )
        ).where(*in_window, Ride.status == RideStatus.COMPLETED)
    )

    active_rides = await session.scalar(
        select(func.count())
        .select_from(Ride)
        .where(Ride.country_code == country, Ride.status.in_(ACTIVE_RIDER_STATUSES))
    )

    # الاشتراك سؤالٌ عن الساعة لا عن عمود (القسم 8)
    # ودولةُ الكبتن من حسابه: لا عمودَ دولةٍ على الاشتراك، وخطتُه قد تكون
    # لدولةٍ أخرى نظرياً — والمعتبَر أين يعمل هو
    active_subs = await session.scalar(
        select(func.count())
        .select_from(DriverSubscription)
        .join(Driver, DriverSubscription.driver_id == Driver.id)
        .join(User, Driver.user_id == User.id)
        .where(User.country_code == country, *subscriptions.coverage_condition(now))
    )

    open_disputes = await session.scalar(
        select(func.count())
        .select_from(Payment)
        .join(Ride, Payment.ride_id == Ride.id)
        .where(Ride.country_code == country, Payment.status == PaymentStatus.DISPUTED)
    )

    pending_documents = await session.scalar(
        select(func.count())
        .select_from(DriverDocument)
        .join(Driver, DriverDocument.driver_id == Driver.id)
        .join(User, Driver.user_id == User.id)
        .where(
            User.country_code == country,
            DriverDocument.review_status == DocumentReviewStatus.PENDING,
        )
    )
    pending_withdrawals = await session.scalar(
        select(func.count())
        .select_from(WithdrawalRequest)
        .join(Driver, WithdrawalRequest.driver_id == Driver.id)
        .join(User, Driver.user_id == User.id)
        .where(
            User.country_code == country,
            WithdrawalRequest.status == WithdrawalStatus.PENDING,
        )
    )

    return Overview(
        period=period,
        from_at=from_at,
        to_at=to_at,
        completed_rides=int(completed or 0),
        cancelled_rides=int(cancelled or 0),
        revenue=Decimal(revenue or 0),
        online_drivers=await online_driver_count(redis, country),
        active_rides=int(active_rides or 0),
        active_subscriptions=int(active_subs or 0),
        open_disputes=int(open_disputes or 0),
        pending_documents=int(pending_documents or 0),
        pending_withdrawals=int(pending_withdrawals or 0),
        rides_by_hour=await _rides_by_hour(session, country, zone, to_at),
        payment_mix=await _payment_mix(session, country, from_at, to_at),
    )


async def _rides_by_hour(
    session: AsyncSession,
    country: CountryCode,
    zone: ZoneInfo,
    now: datetime,
) -> list[int]:
    """أربعٌ وعشرون خانة ليوم الدولة — والساعة تُستخرج بمِنطقتها لا بـUTC.

    عمودُ الثامنة صباحاً في عمّان يجب أن يحمل رحلات الثامنة في عمّان؛ ولو
    استُخرجت الساعة من UTC لانزاح الرسم كلُّه ثلاث خانات.
    """
    start_local = datetime.combine(now.astimezone(zone).date(), time.min, tzinfo=zone)
    hour = func.extract(
        "hour", func.timezone(str(zone), Ride.created_at)
    ).label("hour")

    rows = await session.execute(
        select(hour, func.count())
        .where(
            Ride.country_code == country,
            Ride.created_at >= start_local,
            Ride.created_at <= now,
        )
        .group_by(hour)
    )

    buckets = [0] * 24
    for value, count in rows.all():
        buckets[int(value) % 24] = int(count)
    return buckets


async def _payment_mix(
    session: AsyncSession,
    country: CountryCode,
    from_at: datetime,
    to_at: datetime,
) -> dict[str, int]:
    """توزيعُ القنوات على الدفعات المؤكدة — عدداً لا مبلغاً.

    عدداً لأن السؤال «بأي شيء يدفع الناس»، ومبلغُ قناةٍ واحدة قد ترفعه رحلةٌ
    طويلة فتقرأ اللوحة عادةً لا وجود لها.
    """
    rows = await session.execute(
        select(Payment.method, func.count())
        .join(Ride, Payment.ride_id == Ride.id)
        .where(
            Ride.country_code == country,
            Payment.status == PaymentStatus.CONFIRMED,
            Payment.created_at >= from_at,
            Payment.created_at <= to_at,
        )
        .group_by(Payment.method)
    )
    mix = {method.value: 0 for method in PaymentMethod}
    for method, count in rows.all():
        mix[method.value] = int(count)
    return mix


async def online_driver_count(redis: Redis, country: CountryCode) -> int:
    """عدّ من له مفتاح حضورٍ حيّ — لا من رفع `is_online` ثم اختفى.

    الفهرس الجغرافي لا يملك عمراً لكل عضو (Redis لا يدعمه)، ومفتاحُ الحضور
    يملكه؛ فالعضو الذي ذهب مفتاحُه صامتٌ ولو بقي في الفهرس. وهذا نفس ما يفعله
    `geo.nearby` حين يقصّ الصامتين.
    """
    members = await redis.zrange(geo.geo_key(country), 0, -1)
    if not members:
        return 0

    pipe = redis.pipeline()
    for member in members:
        pipe.exists(geo.presence_key(member))
    return sum(1 for alive in await pipe.execute() if alive)


def parse_driver_id(member: str) -> uuid.UUID | None:  # pragma: no cover - أداة
    try:
        return uuid.UUID(member)
    except ValueError:
        return None
