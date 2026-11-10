"""**دقّةُ وقت الوصول وتصحيحُه** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٢).

* **عند حساب الاقتراب** (`eta.approach`) يُحفظ ما قاله المزوّدُ وما عُرض في `eta:pred:{الرحلة}`، **وعند الوصول** (`record_arrival`)
  يصير صفّاً في `eta_samples` بالزمن الفعليّ من لحظة التوقّع إلى `arrived_at`.
* **التصحيحُ** (`factor`): **وسيطُ «الفعليّ ÷ ما قاله المزوّد»** آخرَ ٢٨ يوماً **لساعة الدولة ويومها** (والساعتين حولها)، وإن قلّت
  العيّناتُ فللساعة في كلِّ الأيام، وإلا لا تصحيح (`1.0`). **بحدٍّ أدنى ٢٠ عيّنةً** وبين ٠٫٨ و١٫٦ — رحلةٌ شاذّةٌ لا تقلب الرقم.
  **ومخزَّنٌ ساعةً** في Redis: نداءٌ يُحسب في كلِّ عرضٍ لا يدفع استعلاماً كلَّ مرّة.
* **والقياسُ في اللوحة** (`summary`): العدد، **متوسّطُ الخطأ بالدقائق**، ونسبةُ ما وقع خلال دقيقتين، والانحيازُ (موجبٌ = يتأخّر
  عمّا قيل)، ولكلِّ ساعة. **والفشلُ هنا لا يُفشل الوصول** — يُسجَّل ويُمضى.
"""

from __future__ import annotations

import json
import logging
import statistics
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CountryCode
from app.models.eta_sample import EtaSample

logger = logging.getLogger(__name__)

WINDOW_DAYS = 28
MIN_SAMPLES = 20
FACTOR_MIN, FACTOR_MAX = 0.8, 1.6
FACTOR_TTL_S = 3600
PRED_TTL_S = 3 * 3600
#: ما فوق ساعتين ليس اقتراباً بل رحلةٌ نُسي فيها زرُّ «وصلت» — لا يُعدّ
MAX_ACTUAL_S = 2 * 3600


def _pred_key(ride_id: uuid.UUID) -> str:
    return f"eta:pred:{ride_id}"


async def _zone(session: AsyncSession, country: CountryCode):
    from app.services.stats import _zone as zone

    return await zone(session, country)


def ratio_from(rows) -> float | None:
    """**وسيطُ «الفعليّ ÷ ما قاله المزوّد»** — و`None` دون `MIN_SAMPLES`. الوسيطُ لا المتوسّط: اقترابٌ علق في حادثٍ لا يقلب الرقم."""
    rows = list(rows)
    if len(rows) < MIN_SAMPLES:
        return None
    return statistics.median(actual / raw for actual, raw in rows)


def clamp(value: float | None) -> float:
    return round(min(FACTOR_MAX, max(FACTOR_MIN, 1.0 if value is None else value)), 3)


async def factor(session: AsyncSession, redis: Redis, country: CountryCode, now: datetime | None = None) -> float:
    now = now or datetime.now(UTC)
    local = now.astimezone(await _zone(session, country))
    key = f"eta:factor:{country.value}:{local.weekday()}:{local.hour}"
    cached = await redis.get(key)
    if cached is not None:
        return float(cached)
    hours = [(local.hour + delta) % 24 for delta in (-1, 0, 1)]
    since = now - timedelta(days=WINDOW_DAYS)
    base = select(EtaSample.actual_seconds, EtaSample.raw_seconds).where(
        EtaSample.country_code == country,
        EtaSample.created_at >= since,
        EtaSample.raw_seconds >= 60,
        EtaSample.local_hour.in_(hours),
    )
    value = 1.0
    for query in (base.where(EtaSample.local_dow == local.weekday()), base):
        found = ratio_from((await session.execute(query.order_by(EtaSample.created_at.desc()).limit(2000))).all())
        if found is not None:
            value = found
            break
    value = clamp(value)
    await redis.set(key, str(value), ex=FACTOR_TTL_S)
    return value


async def remember_prediction(redis: Redis, ride_id: uuid.UUID, *, raw_min: float, shown_min: float, now: datetime) -> None:
    """**الأوّلُ يبقى** (`nx`) — إعادةُ قراءة الاقتراب لا تحرّك لحظةَ التوقّع."""
    await redis.set(
        _pred_key(ride_id),
        json.dumps({"raw": round(raw_min * 60), "shown": round(shown_min * 60), "at": now.isoformat()}),
        ex=PRED_TTL_S,
        nx=True,
    )


async def record_arrival(session: AsyncSession, redis: Redis, ride) -> None:
    try:
        raw = await redis.get(_pred_key(ride.id))
        if not raw or ride.arrived_at is None:
            return
        data = json.loads(raw)
        at = datetime.fromisoformat(data["at"])
        actual = int((ride.arrived_at - at).total_seconds())
        if actual <= 0 or actual > MAX_ACTUAL_S:
            await redis.delete(_pred_key(ride.id))
            return
        local = at.astimezone(await _zone(session, ride.country_code))
        exists = await session.scalar(select(EtaSample.id).where(EtaSample.ride_id == ride.id))
        if exists is None:
            session.add(
                EtaSample(
                    ride_id=ride.id,
                    country_code=ride.country_code,
                    raw_seconds=int(data["raw"]),
                    shown_seconds=int(data["shown"]),
                    actual_seconds=actual,
                    local_hour=local.hour,
                    local_dow=local.weekday(),
                )
            )
        await redis.delete(_pred_key(ride.id))
    except Exception:  # noqa: BLE001 — القياسُ لا يُفشل الوصول
        logger.exception("eta sample for ride %s not recorded", ride.id)


@dataclass(frozen=True, slots=True)
class HourAccuracy:
    hour: int
    samples: int
    mean_abs_error_min: float


@dataclass(frozen=True, slots=True)
class Accuracy:
    samples: int
    mean_abs_error_min: float | None
    within_two_min_percent: int | None
    bias_min: float | None
    raw_mean_abs_error_min: float | None
    by_hour: list[HourAccuracy]


async def summary(session: AsyncSession, *, country: CountryCode, days: int, now: datetime | None = None) -> Accuracy:
    now = now or datetime.now(UTC)
    rows = (
        await session.execute(
            select(EtaSample.local_hour, EtaSample.shown_seconds, EtaSample.raw_seconds, EtaSample.actual_seconds).where(
                EtaSample.country_code == country, EtaSample.created_at >= now - timedelta(days=days)
            )
        )
    ).all()
    if not rows:
        return Accuracy(0, None, None, None, None, [])
    errors = [actual - shown for _, shown, _, actual in rows]
    raw_errors = [abs(actual - raw) for _, _, raw, actual in rows]
    by: dict[int, list[int]] = {}
    for hour, shown, _, actual in rows:
        by.setdefault(int(hour), []).append(abs(actual - shown))
    return Accuracy(
        samples=len(rows),
        mean_abs_error_min=round(sum(abs(e) for e in errors) / len(errors) / 60, 1),
        within_two_min_percent=round(100 * sum(1 for e in errors if abs(e) <= 120) / len(errors)),
        bias_min=round(sum(errors) / len(errors) / 60, 1),
        raw_mean_abs_error_min=round(sum(raw_errors) / len(raw_errors) / 60, 1),
        by_hour=[
            HourAccuracy(hour=h, samples=len(v), mean_abs_error_min=round(sum(v) / len(v) / 60, 1))
            for h, v in sorted(by.items())
        ],
    )


async def count(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(EtaSample)) or 0)
