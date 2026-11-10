"""**درجةُ جودة الكبتن** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٣).

**خمسةُ مكوّناتٍ آخرَ ٣٠ يوماً**، كلٌّ ٠…١، بأوزانٍ من اللوحة لكلِّ دولة، **والدرجةُ ٠–١٠٠**:

* **القبول** — ما قبله ÷ ما عُرض عليه. **والعروضُ لم تكن تُحفظ** فصارت عدّاداتٍ يوميّةً في Redis (`record`) تُكتب حيث يُعرض
  ويُقبل ويُرفض؛ ٤٠ يوماً ثمّ تنقضي.
* **الإلغاء** — ١ − ما ألغاه بعد القبول ÷ ما أُسند إليه.
* **التقييم** — (متوسّطُ نجوم الركّاب − ١) ÷ ٤.
* **الشكاوى** — ١ − اعتراضاتُ الدفع على رحلاته ÷ ٣ (بحدّ الصفر). **ويُضاف إليها بلاغاتُ البند ٩ حين تُبنى.**
* **الرحلاتُ المكتملة** — ما أكمله ÷ ٤٠ (بحدّ الواحد).

**وقليلُ البيانات لا يُعاقَب**: مكوّنٌ بعيّنةٍ دون حدِّها (`MIN_SAMPLE`) يأخذ ٠٫٨ — كبتنٌ جديدٌ لا يُدفن تحت قديمٍ بتقييمٍ حقيقيّ،
ولا يعلوه.

**وأثرُها** (حين يُشعل المفتاح): **في الترتيب لا في الأهليّة** — تقدّم الكبتنَ `dispatch_bonus_m × الدرجة ÷ ١٠٠` متراً كخصم
المستوى، **فالأقربُ يبقى الأوّلَ** بين المتباعدين. **ودون `warn_below` إنذارٌ بنصائح** مرّةً في الأسبوع.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CountryCode, RatingRaterType, RideStatus
from app.models.quality import DriverQualityScore, QualitySetting

WINDOW_DAYS = 30
COUNTER_TTL_S = 40 * 86400
NEUTRAL = 0.8
MIN_SAMPLE = {"acceptance": 5, "cancellation": 3, "rating": 3}
FULL_VOLUME = 40
COMPONENTS = ("acceptance", "cancellation", "rating", "complaints", "completed")


@dataclass(frozen=True, slots=True)
class Weights:
    enabled: bool
    acceptance: int
    cancellation: int
    rating: int
    complaints: int
    completed: int
    dispatch_bonus_m: int
    warn_below: int


DEFAULTS = Weights(False, 30, 25, 25, 10, 10, 150, 50)


async def settings_for(session: AsyncSession, country: CountryCode) -> Weights:
    row = await session.scalar(select(QualitySetting).where(QualitySetting.country_code == country))
    if row is None:
        return DEFAULTS
    return Weights(
        row.enabled, row.w_acceptance, row.w_cancellation, row.w_rating, row.w_complaints, row.w_completed,
        row.dispatch_bonus_m, row.warn_below,
    )


def _key(kind: str, driver_id: uuid.UUID, day: str) -> str:
    return f"quality:{kind}:{driver_id}:{day}"


async def record(redis: Redis, kind: str, driver_id: uuid.UUID, now: datetime | None = None) -> None:
    """`offered` · `accepted` · `declined` — عدّادٌ يوميٌّ؛ **وفشلُه لا يُفشل العرضَ ولا القبول**."""
    try:
        day = (now or datetime.now(UTC)).strftime("%Y%m%d")
        key = _key(kind, driver_id, day)
        if await redis.incr(key) == 1:
            await redis.expire(key, COUNTER_TTL_S)
    except Exception:  # noqa: BLE001
        pass


async def _counter(redis: Redis, kind: str, driver_id: uuid.UUID, now: datetime) -> int:
    days = [(now - timedelta(days=offset)).strftime("%Y%m%d") for offset in range(WINDOW_DAYS)]
    values = await redis.mget([_key(kind, driver_id, day) for day in days])
    return sum(int(value) for value in values if value)


def score_from(weights: Weights, parts: dict[str, float]) -> int:
    total = sum(getattr(weights, name) for name in COMPONENTS)
    if total <= 0:
        return 0
    value = sum(getattr(weights, name) * parts[name] for name in COMPONENTS) / total
    return max(0, min(100, round(value * 100)))


async def measure(session: AsyncSession, redis: Redis, *, driver_id: uuid.UUID, now: datetime | None = None) -> tuple[dict[str, float], dict[str, float]]:
    """المكوّناتُ ٠…١ والأعدادُ التي بُنيت عليها."""
    from app.models.payment import Payment
    from app.models.rating import Rating
    from app.models.ride import Ride

    now = now or datetime.now(UTC)
    since = now - timedelta(days=WINDOW_DAYS)
    offered = await _counter(redis, "offered", driver_id, now)
    accepted = await _counter(redis, "accepted", driver_id, now)
    assigned = int(await session.scalar(
        select(func.count()).select_from(Ride).where(Ride.driver_id == driver_id, Ride.created_at >= since)
    ) or 0)
    cancelled = int(await session.scalar(
        select(func.count()).select_from(Ride).where(
            Ride.driver_id == driver_id, Ride.created_at >= since, Ride.status == RideStatus.CANCELLED_BY_DRIVER
        )
    ) or 0)
    completed = int(await session.scalar(
        select(func.count()).select_from(Ride).where(
            Ride.driver_id == driver_id, Ride.created_at >= since, Ride.status == RideStatus.COMPLETED
        )
    ) or 0)
    average, rated = (await session.execute(
        select(func.avg(Rating.stars), func.count())
        .select_from(Rating)
        .join(Ride, Rating.ride_id == Ride.id)
        .where(Ride.driver_id == driver_id, Rating.rater_type == RatingRaterType.RIDER, Rating.created_at >= since)
    )).one()
    disputes = int(await session.scalar(
        select(func.count()).select_from(Payment).join(Ride, Payment.ride_id == Ride.id).where(
            Ride.driver_id == driver_id, Payment.disputed_at.is_not(None), Payment.disputed_at >= since
        )
    ) or 0)
    parts = {
        "acceptance": min(1.0, accepted / offered) if offered >= MIN_SAMPLE["acceptance"] else NEUTRAL,
        "cancellation": max(0.0, 1 - cancelled / assigned) if assigned >= MIN_SAMPLE["cancellation"] else NEUTRAL,
        "rating": (float(average) - 1) / 4 if average is not None and rated >= MIN_SAMPLE["rating"] else NEUTRAL,
        "complaints": max(0.0, 1 - disputes / 3),
        "completed": min(1.0, completed / FULL_VOLUME),
    }
    counts = {
        "offered": offered, "accepted": accepted, "assigned": assigned, "cancelled": cancelled,
        "completed": completed, "rated": int(rated), "rating_average": round(float(average), 2) if average is not None else None,
        "disputes": disputes,
    }
    return {name: round(value, 3) for name, value in parts.items()}, counts


TIPS = {
    "acceptance": "اقبل ما يصلك من طلباتٍ أكثر — كلُّ عرضٍ يمرّ بلا ردٍّ يُحسب.",
    "cancellation": "لا تلغِ بعد القبول إلا لضرورة — الإلغاءُ يؤخّر الراكبَ ويُحسب عليك.",
    "rating": "اعتنِ بنظافة السيارة والتحيّة والقيادة الهادئة — التقييمُ يأتي منها.",
    "complaints": "اتّفق مع الراكب على الدفع بوضوحٍ قبل نهاية الرحلة — الاعتراضاتُ تُحسب عليك.",
    "completed": "رحلاتٌ مكتملةٌ أكثر ترفع درجتك — اتّصل في ساعات الذروة.",
}


def weakest(parts: dict[str, float], limit: int = 2) -> list[str]:
    return [name for name, value in sorted(parts.items(), key=lambda item: item[1]) if value < 0.9][:limit]


async def snapshot(session: AsyncSession, redis: Redis, *, driver_id: uuid.UUID, country: CountryCode, day: date, now: datetime | None = None) -> DriverQualityScore:
    weights = await settings_for(session, country)
    parts, counts = await measure(session, redis, driver_id=driver_id, now=now)
    score = score_from(weights, parts)
    row = await session.scalar(
        select(DriverQualityScore).where(DriverQualityScore.driver_id == driver_id, DriverQualityScore.day == day)
    )
    payload = {"parts": parts, "counts": counts}
    if row is None:
        row = DriverQualityScore(driver_id=driver_id, day=day, score=score, components=payload)
        session.add(row)
    else:
        row.score, row.components = score, payload
    await session.flush()
    return row


async def latest_scores(session: AsyncSession, driver_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not driver_ids:
        return {}
    latest = (
        select(DriverQualityScore.driver_id, func.max(DriverQualityScore.day).label("d"))
        .where(DriverQualityScore.driver_id.in_(driver_ids))
        .group_by(DriverQualityScore.driver_id)
        .subquery()
    )
    rows = await session.execute(
        select(DriverQualityScore.driver_id, DriverQualityScore.score).join(
            latest, (latest.c.driver_id == DriverQualityScore.driver_id) & (latest.c.d == DriverQualityScore.day)
        )
    )
    return {driver_id: int(score) for driver_id, score in rows.all()}


async def bonuses(session: AsyncSession, country: CountryCode, driver_ids: list[uuid.UUID]) -> dict[uuid.UUID, float]:
    """**أمتارُ التقديم** لكلِّ مرشَّح — وفارغةٌ حيث المفتاحُ مطفأ، فلا يتغيّر الترتيبُ حرفاً."""
    weights = await settings_for(session, country)
    if not weights.enabled or weights.dispatch_bonus_m <= 0:
        return {}
    return {driver_id: weights.dispatch_bonus_m * score / 100 for driver_id, score in (await latest_scores(session, driver_ids)).items()}
