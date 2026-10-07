"""ساعاتُ العمل (SPEC §٦٢-ج/٣٧، قرارُ المالك ٢٠٢٦-١٠-٠٧ §٦٤-ج: «(أ) يراها الكبتنُ والإدارة»).

**ما يُقاس**: دقائقُ الكبتن **متصلاً** — مفتاحُ حضوره حيٌّ (`geo:presence:*`)، وهو ما يعدّه «متصلٌ الآن» في اللوحة نفسِه
(`stats.online_driver_count`) لا `drivers.is_online`: العمودُ يقول «رُفع المفتاح» لا «هو هنا»، وتطبيقٌ قُتل في وسط ورديّته يبقى
عمودُه مرفوعاً حتى ينقضي مفتاحُه. **والرحلةُ الجاريةُ عملٌ** — يبثّ فيها موقعَه، فتُحسب.

**وما لا يُقاس**: **الموقعُ لا يُحفظ** — الرقمُ وحدَه، دقائقُ يومٍ لكلِّ كبتن (`driver_activity_days`). **ويُحفظ ثلاثةَ عشرَ شهراً ثمّ
يُجمع شهرياً** (`driver_activity_months`) ويُحذف اليوميّ — وذلك سطرُ سياسة الخصوصية بعينه (`APPROVALS-62` §٥-٢).

**ومطفأً لا يُحسب شيء** (`work_hours_enabled` لكلِّ سوق): البياناتُ الشخصيةُ لا تُجمع قبل نشر سطرها (§٦٤-هـ/٤)، **فالمفتاحُ يحكم
الجمعَ لا العرضَ وحدَه** — كالمهامّ (البند ٥٣): ميزةٌ تُحسب في الظلّ تُشحن يوماً بأرقامٍ لم يأذن بها أحد.

**والدقيقةُ تُعدّ مرّةً**: الدورةُ كلَّ دقيقة، **ومفتاحُ الدقيقة في Redis** (`activity:tick:<دقيقة UTC>`) يمنع عدَّها مرّتين إن أُعيد
تشغيلُ المُجدوِل أو تداخلت دورتان — والعدُّ ترقيةٌ ذرّيةٌ في القاعدة (`ON CONFLICT … + 1`) فلا يضيع بين قراءةٍ وكتابة.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import Date, cast, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import DriverActivityDay, DriverActivityMonth
from app.models.enums import CountryCode, FeatureKey
from app.services import geo, settings_service
from app.services.stats import _zone

#: **ثلاثةَ عشرَ شهراً يوميّاً** ثمّ شهريّاً — بالأيام: ٣٩٥ تسعُ سنةً وشهراً كاملاً
DAILY_RETENTION_DAYS = 395

_TICK_TTL_SECONDS = 180


def _tick_key(moment: datetime) -> str:
    return f"activity:tick:{moment.astimezone(UTC):%Y%m%d%H%M}"


async def live_driver_ids(redis: Redis, country: CountryCode) -> list[uuid.UUID]:
    """من له مفتاحُ حضورٍ حيٌّ في فهرس الدولة — **الحسابُ نفسُه** الذي يعدّ به `stats.online_driver_count`."""
    members = await redis.zrange(geo.geo_key(country), 0, -1)
    if not members:
        return []
    pipe = redis.pipeline()
    for member in members:
        pipe.exists(geo.presence_key(member))
    alive = await pipe.execute()
    found: list[uuid.UUID] = []
    for member, live in zip(members, alive, strict=True):
        if not live:
            continue
        try:
            found.append(uuid.UUID(member.decode() if isinstance(member, bytes) else str(member)))
        except ValueError:  # pragma: no cover - عضوٌ ليس كبتناً
            continue
    return found


async def tick(session: AsyncSession, redis: Redis, *, now: datetime | None = None) -> int:
    """**دقيقةٌ واحدة** لكلِّ كبتنٍ حيٍّ في سوقٍ أشعل المفتاح — ويعيد عددَ من عُدّ. والالتزامُ على المنادي."""
    moment = now or datetime.now(UTC)
    if not await redis.set(_tick_key(moment), "1", nx=True, ex=_TICK_TTL_SECONDS):
        return 0
    counted = 0
    for country in CountryCode:
        if not await settings_service.is_feature_enabled(session, country, FeatureKey.WORK_HOURS_ENABLED):
            continue
        drivers = await live_driver_ids(redis, country)
        if not drivers:
            continue
        day = moment.astimezone(await _zone(session, country)).date()
        statement = insert(DriverActivityDay).values(
            [{"driver_id": driver_id, "day": day, "online_minutes": 1} for driver_id in drivers]
        )
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=[DriverActivityDay.driver_id, DriverActivityDay.day],
                set_={"online_minutes": DriverActivityDay.online_minutes + 1},
            )
        )
        counted += len(drivers)
    return counted


async def minutes_between(session: AsyncSession, driver_id: uuid.UUID, first: date, last: date) -> int:
    """دقائقُه في أيّامٍ من `first` إلى `last` شاملةً — **بيوم السوق** كما كُتبت."""
    total = await session.scalar(
        select(func.coalesce(func.sum(DriverActivityDay.online_minutes), 0)).where(
            DriverActivityDay.driver_id == driver_id,
            DriverActivityDay.day >= first,
            DriverActivityDay.day <= last,
        )
    )
    return int(total or 0)


@dataclass(frozen=True, slots=True)
class ActivityView:
    days: list[tuple[date, int]]
    months: list[tuple[date, int]]
    #: **المجاميعُ هنا لا في اللوحة** (قاعدةُ `stats`: «التجميعُ في الخلفية») — اليوم وسبعةُ أيّامٍ وثلاثون
    today: int
    week: int
    month: int


async def view_for_admin(session: AsyncSession, driver_id: uuid.UUID, today: date) -> ActivityView:
    """**ما تراه الإدارة** — ثلاثون يوماً يوماً بيوم، وما جُمع شهريّاً. **ولا موقعَ**: لا شيءَ منه يُحفظ أصلاً."""
    start = today - timedelta(days=29)
    rows = await session.execute(
        select(DriverActivityDay.day, DriverActivityDay.online_minutes)
        .where(DriverActivityDay.driver_id == driver_id, DriverActivityDay.day >= start)
        .order_by(DriverActivityDay.day)
    )
    found = {day: minutes for day, minutes in rows}
    days = [(start + timedelta(days=offset), found.get(start + timedelta(days=offset), 0)) for offset in range(30)]
    months = await session.execute(
        select(DriverActivityMonth.month, DriverActivityMonth.online_minutes)
        .where(DriverActivityMonth.driver_id == driver_id)
        .order_by(DriverActivityMonth.month.desc())
        .limit(24)
    )
    return ActivityView(
        days=days,
        months=[(month, minutes) for month, minutes in months],
        today=days[-1][1],
        week=sum(minutes for _day, minutes in days[-7:]),
        month=sum(minutes for _day, minutes in days),
    )


async def roll_up(session: AsyncSession, *, today: date) -> int:
    """**ما جاوز ثلاثةَ عشرَ شهراً يُجمع شهرياً ثمّ يُحذف يوميُّه** — ويعيد عددَ الصفوف اليومية المحذوفة. والالتزامُ على المنادي."""
    cutoff = today - timedelta(days=DAILY_RETENTION_DAYS)
    month = cast(func.date_trunc("month", DriverActivityDay.day), Date)
    grouped = (
        await session.execute(
            select(DriverActivityDay.driver_id, month.label("month"), func.sum(DriverActivityDay.online_minutes))
            .where(DriverActivityDay.day < cutoff)
            .group_by(DriverActivityDay.driver_id, month)
        )
    ).all()
    if not grouped:
        return 0
    statement = insert(DriverActivityMonth).values(
        [{"driver_id": driver_id, "month": first, "online_minutes": int(minutes)} for driver_id, first, minutes in grouped]
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[DriverActivityMonth.driver_id, DriverActivityMonth.month],
            set_={"online_minutes": DriverActivityMonth.online_minutes + statement.excluded.online_minutes},
        )
    )
    result = await session.execute(delete(DriverActivityDay).where(DriverActivityDay.day < cutoff))
    return int(result.rowcount or 0)
