"""المهامُّ والمستويات — القياسُ حيٌّ، والمستوى محضَّرٌ بكاتبٍ واحد (البند ٥٣).

**والتناقضُ الظاهريُّ بين قاعدتين هو صلبُ هذا الملف:**

* قاعدةُ الإحالة تقول: **لا تُخزِّن حكماً**، قِسه حيّاً كي يعيد تعديلُ الإعداد
  تقييمَ الجميع.
* وقاعدةُ التوزيع تقول: **لا استعلامَ إضافيّاً على المسار الحرج** — نافذةُ عشرين
  ثانيةً لكل عرض.

والجوابُ أن المخزَّن ليس حكماً مجمَّداً بل **حاصلَ حسابٍ مادّيٍّ** له كاتبٌ واحدٌ
ووقتُ حسابٍ مكتوب، وسابقتُه في المشروع `drivers.rating_avg` بالضبط. والفرقُ بينه
وبين `qualified_at` المرفوض ليس التخزينَ بل **من يكتب ومتى**.

**فالتقدّمُ يُقاس حيّاً** (لا عمودَ يراكمه — درسُ `budget_spent`)، **والمستوى
وحدَه يُكتب**، ومن يكتبه `tasks/levels.py` لا مسارُ إنهاء الرحلة ولا التقييم.

**والشهرُ بتقويم الدولة** لا بتقويم الخادم — قاعدةُ «يومِ الدولة» في
`services/stats.py`: كبتنٌ أنهى رحلتَه الأخيرة في الحادية عشرة ليلاً في آخر يومٍ
في عمّان يُحرم منها لو قيس بـUTC.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, InvalidInput, NotFound
from app.models.driver import Driver
from app.models.enums import CountryCode, DriverStatus, FeatureKey, RideStatus
from app.models.mission import (
    MAX_LEVEL,
    MAX_LEVEL_DISCOUNT_METERS,
    METRIC_COMPLETED_RIDES,
    METRIC_MIN_RATING,
    MISSION_METRICS,
    LevelSetting,
    Mission,
)
from app.models.ride import Ride
from app.models.user import User
from app.services import settings_service


class MissionNotFound(NotFound):
    code = "mission_not_found"
    message = "المهمة غير موجودة"


class MissionExists(Conflict):
    code = "mission_exists"
    message = "لهذا المعيار مهمةٌ في هذا الشهر"


def _now() -> datetime:
    return datetime.now(UTC)


async def _zone(session: AsyncSession, country: CountryCode) -> ZoneInfo:
    """مِنطقةُ الدولة — **من `services/stats.py` نفسِه لا نسخةٌ ثانية**.

    ومنطقةُ زمنٍ ثانيةٌ في هذا الملف حالةٌ ثانيةٌ تخالف الأولى أوّلَ ما تُعدَّل
    إحداهما، فتصير «بدايةُ شهر عمّان» جوابين.
    """
    from app.services.stats import _zone as stats_zone

    return await stats_zone(session, country)


async def _country_month(session: AsyncSession, country: CountryCode) -> date:
    """أوّلُ يومٍ في الشهر **بتقويم الدولة** — قاعدةُ «يومِ الدولة»."""
    local = _now().astimezone(await _zone(session, country))
    return date(local.year, local.month, 1)


# ------------------------------------------------------------ إدارةُ المهامّ


async def list_missions(
    session: AsyncSession, *, country: CountryCode, month: date | None = None
) -> list[Mission]:
    stmt = select(Mission).where(Mission.country_code == country)
    if month is not None:
        stmt = stmt.where(Mission.month == month)
    return list(
        (await session.scalars(stmt.order_by(Mission.month.desc(), Mission.metric))).all()
    )


async def current_missions(
    session: AsyncSession, country: CountryCode
) -> list[Mission]:
    """مهامُّ الشهر الجاري المفعّلة — وهي ما يُقاس عليه المستوى وما تعرضه الشاشة."""
    month = await _country_month(session, country)
    return list(
        (
            await session.scalars(
                select(Mission)
                .where(
                    Mission.country_code == country,
                    Mission.month == month,
                    Mission.is_active.is_(True),
                )
                .order_by(Mission.metric)
            )
        ).all()
    )


async def create_mission(
    session: AsyncSession,
    *,
    country: CountryCode,
    month: date,
    metric: str,
    target: Decimal,
    title: str,
    description: str | None = None,
    created_by: uuid.UUID | None = None,
) -> Mission:
    if metric not in MISSION_METRICS:
        # **يُرفض لا يُهمَل**: مهمّةٌ بمعيارٍ لا يقرؤه أحدٌ تُعرض للكباتن ولا
        # تُنجَز أبداً — وهي «قاعدةٌ بلا باب» مقلوبةً: بابٌ بلا قاعدة
        raise InvalidInput("معيار المهمة غير معروف")
    if target <= 0:
        raise InvalidInput("هدف المهمة يكون أكبر من صفر")
    if month.day != 1:
        month = date(month.year, month.month, 1)

    exists = await session.scalar(
        select(Mission.id).where(
            Mission.country_code == country,
            Mission.month == month,
            Mission.metric == metric,
        )
    )
    if exists is not None:
        raise MissionExists()

    mission = Mission(
        country_code=country,
        month=month,
        metric=metric,
        target=target,
        title=title.strip(),
        description=description,
        created_by=created_by,
    )
    session.add(mission)
    await session.flush()
    return mission


async def update_mission(
    session: AsyncSession,
    mission_id: uuid.UUID,
    *,
    title: str | None = None,
    description: str | None = None,
    target: Decimal | None = None,
    is_active: bool | None = None,
) -> Mission:
    """**والهدفُ يُعدَّل ولا يُجمَّد على أحد**: التقدّمُ مقيسٌ حيّاً، فتنزيلُ
    الهدف يرفع في الدورة التالية من كان ينتظره — بلا لمسِ صفٍّ لأحد."""
    mission = await session.get(Mission, mission_id)
    if mission is None:
        raise MissionNotFound()
    if title is not None:
        mission.title = title.strip()
    if description is not None:
        mission.description = description
    if target is not None:
        if target <= 0:
            raise InvalidInput("هدف المهمة يكون أكبر من صفر")
        mission.target = target
    if is_active is not None:
        mission.is_active = is_active
    await session.flush()
    return mission


# ------------------------------------------------------------ قياسُ التقدّم


@dataclass(frozen=True)
class MissionProgress:
    """**حقائقُ لا جملةُ حالة** — النصَّ تبنيه الشاشة (قاعدةُ `data` في الإشعار)."""

    mission: Mission
    value: Decimal
    target: Decimal

    @property
    def done(self) -> bool:
        return self.value >= self.target

    @property
    def ratio(self) -> float:
        if self.target <= 0:  # pragma: no cover - يمنعه CHECK
            return 0.0
        return min(1.0, float(self.value) / float(self.target))


def _month_bounds(month: date, zone: ZoneInfo) -> tuple[datetime, datetime]:
    """حدُّ الشهر **لحظتان بتوقيت الدولة**، مُحوَّلتان إلى UTC للمقارنة."""
    start = datetime(month.year, month.month, 1, tzinfo=zone)
    if month.month == 12:
        end = datetime(month.year + 1, 1, 1, tzinfo=zone)
    else:
        end = datetime(month.year, month.month + 1, 1, tzinfo=zone)
    return start.astimezone(UTC), end.astimezone(UTC)


def _completed_rides_expr(start: datetime, end: datetime) -> Select:
    return (
        select(Ride.driver_id, func.count().label("value"))
        .where(
            Ride.status == RideStatus.COMPLETED,
            Ride.completed_at >= start,
            Ride.completed_at < end,
            Ride.driver_id.is_not(None),
        )
        .group_by(Ride.driver_id)
    )


async def measure(
    session: AsyncSession,
    *,
    country: CountryCode,
    missions: list[Mission],
    driver_ids: list[uuid.UUID] | None = None,
) -> dict[uuid.UUID, dict[str, Decimal]]:
    """قيمةُ كلِّ معيارٍ لكل كبتن — **استعلامٌ لكل معيارٍ لا لكل كبتن**.

    نفسُ شكلِ `ride_log.payment_summaries`: سوقٌ فيه ألفُ كبتنٍ ومهمّتان يُقاس
    بمرورين لا بألفَي ذهابٍ وعودة.
    """
    if not missions:
        return {}

    start, end = _month_bounds(missions[0].month, await _zone(session, country))
    out: dict[uuid.UUID, dict[str, Decimal]] = {}

    metrics = {mission.metric for mission in missions}

    if METRIC_COMPLETED_RIDES in metrics:
        stmt = _completed_rides_expr(start, end)
        if driver_ids is not None:
            stmt = stmt.where(Ride.driver_id.in_(driver_ids))
        for driver_id, value in (await session.execute(stmt)).all():
            out.setdefault(driver_id, {})[METRIC_COMPLETED_RIDES] = Decimal(value)

    if METRIC_MIN_RATING in metrics:
        # **يُقرأ من `drivers.rating_avg`** — وهو نفسُه محضَّرٌ يُعاد بناؤه من كل
        # الجدول بعد كل تقييم (`services/ratings.py`)، فلا حسابَ ثانياً هنا
        stmt = select(Driver.id, Driver.rating_avg)
        if driver_ids is not None:
            stmt = stmt.where(Driver.id.in_(driver_ids))
        for driver_id, value in (await session.execute(stmt)).all():
            out.setdefault(driver_id, {})[METRIC_MIN_RATING] = Decimal(value or 0)

    return out


async def progress_for(
    session: AsyncSession, *, driver: Driver
) -> list[MissionProgress]:
    """تقدّمُ كبتنٍ واحدٍ في مهامِّ شهره — لشاشته."""
    user = await session.get(User, driver.user_id)
    assert user is not None
    missions = await current_missions(session, user.country_code)
    if not missions:
        return []
    measured = await measure(
        session, country=user.country_code, missions=missions, driver_ids=[driver.id]
    )
    values = measured.get(driver.id, {})
    return [
        MissionProgress(
            mission=mission,
            value=values.get(mission.metric, Decimal(0)),
            target=mission.target,
        )
        for mission in missions
    ]


# ------------------------------------------------------------ إعادةُ التقييم


def level_from(done: int, total: int) -> int:
    """المستوى من عدد المهامِّ المنجزة — **متدرّجٌ بعدد المهامّ لا بجدولٍ ثابت**.

    سوقٌ فيه مهمّةٌ واحدةٌ لا يجعل أحداً في المستوى الثالث، وسوقٌ فيه ثلاثٌ يجعل
    من أنجزها كلَّها في أعلاه. **والصفرُ مستوىً** لا نقص: كبتنٌ جديدٌ فيه ولا
    يُعامَل معاملةَ الناقص.
    """
    if total <= 0 or done <= 0:
        return 0
    return min(MAX_LEVEL, round(MAX_LEVEL * done / total))


async def reevaluate(session: AsyncSession, country: CountryCode) -> int:
    """يعيد حسابَ مستويات سوقٍ كامل. الـcommit للمستدعي. يعيد عددَ من تبدّل.

    **وهي الكاتبُ الوحيد** لـ`drivers.level` — ولا يُحدَّث في مسار إنهاء الرحلة
    ولا في مسار التقييم (قاعدةُ `current_leg`).

    **ومطفأً يُصفَّر لا يُترك**: مفتاحٌ يُطفأ ثم يبقى المستوى مكتوباً يجعل
    إعادةَ إشعاله تعيد ترتيباً حُسب على تعريفٍ قديم — والصفرُ هو حالُ «لا ميزة».
    """
    enabled = await settings_service.is_feature_enabled(
        session, country, FeatureKey.DRIVER_LEVELS_ENABLED
    )
    missions = await current_missions(session, country) if enabled else []

    # **دولةُ الكبتن على حساب صاحبِه** لا على صفِّ الكبتن — كما في كل المشروع
    driver_ids = list(
        (
            await session.scalars(
                select(Driver.id)
                .join(User, User.id == Driver.user_id)
                .where(
                    User.country_code == country,
                    Driver.status == DriverStatus.APPROVED,
                )
            )
        ).all()
    )
    if not driver_ids:
        return 0

    measured = (
        await measure(
            session, country=country, missions=missions, driver_ids=driver_ids
        )
        if missions
        else {}
    )

    stamped = _now()
    changed = 0
    for driver_id in driver_ids:
        values = measured.get(driver_id, {})
        done = sum(
            1
            for mission in missions
            if values.get(mission.metric, Decimal(0)) >= mission.target
        )
        level = level_from(done, len(missions))
        result = await session.execute(
            update(Driver)
            .where(Driver.id == driver_id)
            .values(level=level, level_computed_at=stamped)
        )
        changed += result.rowcount or 0
    return changed


async def reevaluate_all(session: AsyncSession) -> int:
    total = 0
    for country in CountryCode:
        total += await reevaluate(session, country)
        await session.commit()
    return total


# ------------------------------------------------------------ أثرُ المستوى


async def discounts_for(
    session: AsyncSession, country: CountryCode
) -> dict[int, int]:
    """خصمُ كلِّ مستوىً بالأمتار — **صفرٌ لكلِّ ما لم يُضبط**.

    ومطفأً (المفتاح) تُعاد خريطةٌ أصفارٌ كلُّها، فالترتيبُ يبقى **حرفياً كما هو
    اليوم**: لا شرطَ في الكود يقول «إن كانت الميزةُ مطفأةً فرتّب بطريقةٍ أخرى»،
    بل رقمٌ قدرُه صفر — وهو ما يجعل الفرقَ بين مطفأٍ ومشتعلٍ **قابلاً للقياس**
    لا معتمداً على فرعٍ ثانٍ في الشيفرة.
    """
    if not await settings_service.is_feature_enabled(
        session, country, FeatureKey.DRIVER_LEVELS_ENABLED
    ):
        return {}
    rows = await session.execute(
        select(LevelSetting.level, LevelSetting.discount_meters).where(
            LevelSetting.country_code == country
        )
    )
    return {level: meters for level, meters in rows.all() if meters}


async def set_discount(
    session: AsyncSession, *, country: CountryCode, level: int, meters: int
) -> LevelSetting:
    if not 0 <= level <= MAX_LEVEL:
        raise InvalidInput("المستوى خارج المدى")
    if not 0 <= meters <= MAX_LEVEL_DISCOUNT_METERS:
        # **حدُّ المالك**: «يقلّص نطاقَ البحث قليلاً لا يلغيه»
        raise InvalidInput(
            f"أثر المستوى لا يتجاوز {MAX_LEVEL_DISCOUNT_METERS} متراً"
        )
    row = await session.scalar(
        select(LevelSetting).where(
            LevelSetting.country_code == country, LevelSetting.level == level
        )
    )
    if row is None:
        row = LevelSetting(country_code=country, level=level)
        session.add(row)
    row.discount_meters = meters
    await session.flush()
    return row


async def level_counts(
    session: AsyncSession, country: CountryCode
) -> dict[int, int]:
    """كم كبتناً في كل مستوى — لجدول اللوحة."""
    rows = await session.execute(
        select(Driver.level, func.count())
        .join(User, User.id == Driver.user_id)
        .where(
            User.country_code == country, Driver.status == DriverStatus.APPROVED
        )
        .group_by(Driver.level)
    )
    return {level: int(total) for level, total in rows.all()}
