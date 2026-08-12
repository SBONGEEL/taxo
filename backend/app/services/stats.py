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
from datetime import date, datetime, time, timedelta
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
from app.models.subscription import DriverSubscription, SubscriptionPlan
from app.models.user import User
from app.models.wallet import WithdrawalRequest
from app.core.currency import currency_for_country
from app.services import campaigns, geo, subscriptions

# نوافذ التقرير الثلاث كما في `DESIGN.md` §3.2 (اليوم/الأسبوع/الشهر)
PERIOD_DAYS = {"today": 1, "week": 7, "month": 30}
DEFAULT_TIMEZONE = "Asia/Amman"

# «أفضل السائقين» في التصميم لوحٌ قصير — خمسةٌ تُقرأ، وعشرون قائمةٌ ثانية
TOP_DRIVERS = 5


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


@dataclass(frozen=True, slots=True)
class DayRevenue:
    """يومٌ واحد في شريط الإيراد — `day` تاريخُ **يوم الدولة** لا يوم UTC."""

    day: str
    revenue: Decimal
    rides: int


@dataclass(frozen=True, slots=True)
class TopDriver:
    driver_id: uuid.UUID
    name: str
    completed_rides: int
    revenue: Decimal
    rating_avg: Decimal


@dataclass(frozen=True, slots=True)
class PlanSales:
    plan_id: uuid.UUID
    plan_name: str
    sold: int
    revenue: Decimal


@dataclass(frozen=True, slots=True)
class Reports:
    """«التقارير والإحصاءات» (SPEC القسم 13/5 وDESIGN §5.4).

    **ما ليس فيها مقصودٌ كما ما فيها**: لا «أعلى المناطق طلباً» لأن المناطق
    لا وجود لها في هذا المخطط — لا جدولَ مناطق ولا عمودَ منطقةٍ على الرحلة،
    ورسمُها من الإحداثيات اختراعُ تقسيمٍ لم يقله أحد. ولا «معدّل قبول
    الطلبات» لأن `ride_offers` لم يُبنَ (القسم 16/9-ب)، وحسابُه من الرحلات
    وحدها يقيس شيئاً آخر ويسمّيه باسمه.
    """

    period: str
    from_at: datetime
    to_at: datetime
    currency: str

    revenue_by_day: list[DayRevenue]
    avg_ride_fare: Decimal
    cancellation_rate: Decimal
    active_drivers: int

    subscriptions_sold: int
    subscription_revenue: Decimal
    sales_by_plan: list[PlanSales]

    top_drivers: list[TopDriver]


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


def _days_in(zone: ZoneInfo, from_at: datetime, to_at: datetime) -> list[date]:
    """أيامُ النافذة **بتقويم الدولة** — من أولها إلى يومها الأخير ضمناً."""
    first = from_at.astimezone(zone).date()
    last = to_at.astimezone(zone).date()
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]


async def reports(
    session: AsyncSession,
    *,
    country: CountryCode,
    period: str,
    now: datetime,
) -> Reports:
    """تقاريرُ الفترة — بنفس نافذة «نظرة عامة» وبنفس قاعدة «يومُ الدولة».

    ولا معدّلَ يُحسب في الواجهة: «متوسط قيمة الرحلة» قسمةُ مجموعٍ على عدد،
    وكلاهما ينزل من استعلامٍ مسقوفٍ لو تُرك للوحة — فتقرأ الشاشةُ متوسطَ
    الخمسين صفاً الأولى وتسمّيه متوسط الشهر.
    """
    zone = await _zone(session, country)
    from_at, to_at = _window(zone, period, now)
    in_window = (
        Ride.country_code == country,
        Ride.created_at >= from_at,
        Ride.created_at <= to_at,
    )
    fare = func.coalesce(Ride.final_fare, Ride.estimated_fare)
    day = func.date(func.timezone(str(zone), Ride.created_at)).label("day")

    day_rows = await session.execute(
        select(day, func.coalesce(func.sum(fare), 0), func.count())
        .where(*in_window, Ride.status == RideStatus.COMPLETED)
        .group_by(day)
        .order_by(day)
    )
    # **كلُّ يومٍ في النافذة صفٌّ ولو بصفر.** الاستعلام لا يعيد إلا الأيام التي
    # فيها رحلة، ورسمُ الأعمدة على ما يعود يضغط الفجوات فيُقرأ أسبوعٌ فيه ثلاثة
    # أيام عملٍ ثلاثةَ أيامٍ متتالية — رسمٌ يكذب بلا رقمٍ خاطئ فيه. والملءُ هنا
    # لا في الواجهة: هي لا تعرف حدود النافذة ولا مِنطقة الدولة
    found = {
        value: (Decimal(total), int(count))
        for value, total, count in day_rows.all()
    }
    revenue_by_day = [
        DayRevenue(
            day=value.isoformat(),
            revenue=found.get(value, (Decimal(0), 0))[0],
            rides=found.get(value, (Decimal(0), 0))[1],
        )
        for value in _days_in(zone, from_at, to_at)
    ]

    completed = sum(row.rides for row in revenue_by_day)
    revenue = sum((row.revenue for row in revenue_by_day), Decimal(0))
    cancelled = int(
        await session.scalar(
            select(func.count())
            .select_from(Ride)
            .where(
                *in_window,
                Ride.status.in_(
                    (RideStatus.CANCELLED_BY_RIDER, RideStatus.CANCELLED_BY_DRIVER)
                ),
            )
        )
        or 0
    )

    # «سائقٌ نشط» = من أنهى رحلةً في الفترة، لا من رفع `is_online` مرةً:
    # الحضورُ نيّةٌ والرحلةُ عمل
    active_drivers = int(
        await session.scalar(
            select(func.count(func.distinct(Ride.driver_id))).where(
                *in_window,
                Ride.status == RideStatus.COMPLETED,
                Ride.driver_id.is_not(None),
            )
        )
        or 0
    )

    top_rows = await session.execute(
        select(
            Driver.id,
            User.name,
            func.count(),
            func.coalesce(func.sum(fare), 0),
            Driver.rating_avg,
        )
        .select_from(Ride)
        .join(Driver, Ride.driver_id == Driver.id)
        .join(User, Driver.user_id == User.id)
        .where(*in_window, Ride.status == RideStatus.COMPLETED)
        .group_by(Driver.id, User.name)
        .order_by(func.count().desc())
        .limit(TOP_DRIVERS)
    )
    top_drivers = [
        TopDriver(
            driver_id=driver_id,
            name=name,
            completed_rides=int(count),
            revenue=Decimal(total),
            rating_avg=rating,
        )
        for driver_id, name, count, total, rating in top_rows.all()
    ]

    # تقاريرُ الاشتراكات (القسم 13/5): ما **بيع** في الفترة لا ما هو سارٍ
    # الآن — ذاك رقمُ «نظرة عامة»، وهذا إيرادُ الشهر
    sold_in_window = (
        User.country_code == country,
        DriverSubscription.created_at >= from_at,
        DriverSubscription.created_at <= to_at,
    )
    plan_rows = await session.execute(
        select(
            SubscriptionPlan.id,
            SubscriptionPlan.name,
            func.count(),
            func.coalesce(func.sum(DriverSubscription.amount_paid), 0),
        )
        .select_from(DriverSubscription)
        .join(SubscriptionPlan, DriverSubscription.plan_id == SubscriptionPlan.id)
        .join(Driver, DriverSubscription.driver_id == Driver.id)
        .join(User, Driver.user_id == User.id)
        .where(*sold_in_window)
        .group_by(SubscriptionPlan.id, SubscriptionPlan.name)
        .order_by(func.count().desc())
    )
    sales_by_plan = [
        PlanSales(
            plan_id=plan_id, plan_name=name, sold=int(count), revenue=Decimal(total)
        )
        for plan_id, name, count, total in plan_rows.all()
    ]

    total_rides = completed + cancelled
    return Reports(
        period=period,
        from_at=from_at,
        to_at=to_at,
        currency=currency_for_country(country).value,
        revenue_by_day=revenue_by_day,
        # القسمةُ على `Decimal` لا على float: هذه أرقامُ مال (القسم 14)
        avg_ride_fare=(
            (revenue / completed).quantize(Decimal("0.001"))
            if completed
            else Decimal("0.000")
        ),
        cancellation_rate=(
            (Decimal(cancelled) * 100 / total_rides).quantize(Decimal("0.01"))
            if total_rides
            else Decimal("0.00")
        ),
        active_drivers=active_drivers,
        subscriptions_sold=sum(row.sold for row in sales_by_plan),
        subscription_revenue=sum((row.revenue for row in sales_by_plan), Decimal(0)),
        sales_by_plan=sales_by_plan,
        top_drivers=top_drivers,
    )


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
