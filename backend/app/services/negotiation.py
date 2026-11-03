"""«تفاوض» على السعر، كبتنٌ واحدٌ في كلِّ مرّة (SPEC §٩٢، `design/NEGOTIATE.md`).

**يُبنى على ما هو قائم ولا يكرّره** (§٩٢-د): الطلبُ بابُه `POST /rides` بحقلٍ زائد، والتوزيعُ `dispatch._run` نفسُه **تسلسليٌّ قسراً**،
و«قبول» الكبتن و«رفضُه» بابا العرض القائمان. **والجديدُ هنا ثلاثة**: الحدُّ الأدنى والخطوةُ (§٩٢-ب)، **والعرضُ المقابل** وجوابُ الراكب
عليه (§٩٢-أ/٣–٤)، **وتعديلُ السعر أثناء البحث** (§٩٢-أ/٥).

**والعرضُ المقابلُ المعلَّقُ يعيش في Redis بمهلة الراكب** (`counter_key`) كما يعيش العرضُ نفسُه بمهلة الكبتن — **ولا يُكتب على الرحلة
حتى يُقبل**: الرحلةُ تحمل ما اتُّفق عليه لا ما عُرض.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.currency import currency_for_country, money_text
from app.core.exceptions import InvalidInput, NotFound, RateLimited
from app.models.driver import Driver
from app.models.enums import CountryCode, RideStatus
from app.models.negotiation import NegotiationSetting, RideFareOffer
from app.models.ride import Ride
from app.services import rounding
from app.services.pricing import FareLine, as_money

#: **حدُّ الإساءة** (§٩٢-د، `design/NEGOTIATE.md` §٤) — طلباتُ تفاوضٍ وتعديلاتُ سعرٍ للراكب، وعروضٌ مقابلةٌ للكبتن
RIDER_LIMIT, RIDER_WINDOW = 5, 600
DRIVER_LIMIT, DRIVER_WINDOW = 10, 3600
#: **عرضٌ فوق خمسة أضعاف التقدير خطأُ كتابة** لا سعر («250» بدل «2.500») — يُردّ بعلّته
MAX_FACTOR = 5


@dataclass(frozen=True)
class NegotiationRules:
    """**إعدادُ السوق يُقرأ مرّةً ويُمرَّر** — والغيابُ مطفأ."""

    enabled: bool
    min_percent: int
    min_amount: Decimal | None
    driver_timeout_seconds: int
    rider_timeout_seconds: int
    max_counter_percent: int | None
    max_drivers: int | None
    categories: tuple[str, ...]

    def allows(self, category: str) -> bool:
        return self.enabled and (not self.categories or category in self.categories)


#: **سوقٌ بلا صفٍّ لا تفاوضَ فيه** — والقيمُ هي افتراضاتُ الجدول نفسُها
DISABLED = NegotiationRules(
    enabled=False, min_percent=70, min_amount=None, driver_timeout_seconds=20, rider_timeout_seconds=20,
    max_counter_percent=None, max_drivers=None, categories=(),
)


def counter_key(ride_id: uuid.UUID | str) -> str:
    """**العرضُ المقابلُ المعلَّق** — `driver_id:amount` بعمر مهلة الراكب."""
    return f"negotiation:counter:{ride_id}"


async def rules_for(session: AsyncSession, country: CountryCode) -> NegotiationRules:
    row = await session.scalar(select(NegotiationSetting).where(NegotiationSetting.country_code == country))
    if row is None:
        return DISABLED
    return NegotiationRules(
        enabled=row.enabled,
        min_percent=row.min_percent,
        min_amount=row.min_amount,
        driver_timeout_seconds=row.driver_timeout_seconds,
        rider_timeout_seconds=row.rider_timeout_seconds,
        max_counter_percent=row.max_counter_percent,
        max_drivers=row.max_drivers,
        categories=tuple(row.categories or ()),
    )


@dataclass(frozen=True)
class Floor:
    """**أقلُّ ما يُعرض** — والحدّان معاً ليُعرضا للراكب بوضوح (§٩٢-ب)."""

    minimum: Decimal
    by_percent: Decimal
    by_amount: Decimal | None
    step: Decimal | None


def _ceil_to(amount: Decimal, step: Decimal | None) -> Decimal:
    if step is None or step <= 0:
        return as_money(amount)
    return as_money((amount / step).to_integral_value(rounding=ROUND_CEILING) * step)


async def floor_for(session: AsyncSession, country: CountryCode, rules: NegotiationRules, estimate: Decimal) -> Floor:
    """**الحدُّ الأدنى للعرض** = الأعلى من (نسبةٍ من التقدير، المبلغِ الثابت) — **مرفوعاً إلى خطوة السوق** فيكون عرضاً يُقبل.

    والخطوةُ وحدةُ التقريب إن كان مشتعلاً، وإلا لا خطوة (خاناتُ العملة وحدَها تحكم، `rounding.require_precise`).
    """
    policy = await rounding.policy_for(session, country)
    step = policy.unit if policy.enabled else None
    by_percent = _ceil_to(estimate * Decimal(rules.min_percent) / Decimal(100), step)
    by_amount = _ceil_to(rules.min_amount, step) if rules.min_amount is not None else None
    return Floor(minimum=max(by_percent, by_amount or Decimal(0)), by_percent=by_percent, by_amount=by_amount, step=step)


async def require_rider_budget(redis: Redis, rider_id: uuid.UUID) -> None:
    hit = await rate_limit.hit(redis, f"negotiate:rider:{rider_id}", limit=RIDER_LIMIT, window_seconds=RIDER_WINDOW)
    if not hit.allowed:
        raise RateLimited(f"عروضٌ كثيرةٌ في وقتٍ قصير — جرّب بعد {hit.retry_after} ثانية", retry_after=hit.retry_after)


async def validate_offer(
    session: AsyncSession, *, country: CountryCode, category: str, estimate: Decimal, amount: Decimal
) -> NegotiationRules:
    """**عرضُ الراكب يُقبل أو يُردّ بعلّته** — والتطبيقُ يمنعه قبلها، **والخلفيةُ لا تثق بالتطبيق** (§٩٢-ب)."""
    rules = await rules_for(session, country)
    if not rules.enabled:
        raise InvalidInput("التفاوضُ غيرُ متاحٍ في بلدك الآن", field="negotiation")
    if not rules.allows(category):
        raise InvalidInput("التفاوضُ غيرُ متاحٍ في هذه الفئة", field="negotiation")
    await rounding.require_multiple_in(session, country, amount, field="negotiation")
    floor = await floor_for(session, country, rules, estimate)
    if amount < floor.minimum:
        shown = money_text(floor.minimum, currency_for_country(country))
        raise InvalidInput(f"أقلُّ عرضٍ في هذه الرحلة {shown}", field="negotiation", minimum=str(floor.minimum))
    if amount > estimate * MAX_FACTOR:
        raise InvalidInput("العرضُ أكبرُ من خمسة أضعاف التقدير — راجع الرقم", field="negotiation")
    return rules


async def record(
    session: AsyncSession, ride_id: uuid.UUID, kind: str, *, amount: Decimal | None = None, driver_id: uuid.UUID | None = None
) -> None:
    session.add(RideFareOffer(ride_id=ride_id, kind=kind, amount=amount, driver_id=driver_id))


def agree(ride: Ride, amount: Decimal) -> None:
    """**السعرُ المتّفق عليه يُكتب على الرحلة** — تحت قفل صفّها في `rides._take`.

    ويحلّ محلَّ التقدير في كلِّ ما يُعرض (السجلّ والإيصال واللوحة يقرؤون `estimated_fare` كما اليوم)، **وسطرُ تفصيله واحد**: «سعر متفاوض
    عليه». **ورسمُ الانتظار والوقفات فوقه** عند الإنهاء (`rides._final_fare`) بقواعدها التي عُرضت قبل الطلب (§٩٢-ج).
    """
    ride.negotiated_fare = as_money(amount)
    ride.estimated_fare = ride.negotiated_fare
    ride.fare_lines = [FareLine("negotiated", ride.negotiated_fare).as_json()]


# ------------------------------------------------------------- العرضُ المقابل


async def counter(
    session: AsyncSession, redis: Redis, *, ride: Ride, driver: Driver, amount: Decimal
) -> NegotiationRules:
    """**«سعرٌ آخر» من الكبتن المعروضةِ عليه الرحلةُ الآن** (§٩٢-أ/٣) — يُعلَّق بمهلة الراكب، ويُمدَّد حجزُ الكبتن معه.

    **ولا يكون إلا أعلى من عرض الراكب** (ما يساويه أو يقلّ عنه قبولٌ يُضغط له «قبول»)، ولا فوق السقف إن أُشعل، **ولا يُكتب على الرحلة**.
    """
    from app.services import dispatch

    if ride.negotiation_offer is None or ride.status is not RideStatus.SEARCHING:
        raise NotFound("لا عرضَ قائمٌ على هذه الرحلة")
    await dispatch.require_offer(redis, ride.id, driver.id)
    if await redis.exists(counter_key(ride.id)):
        raise InvalidInput("أرسلتَ سعرك — ينتظر جوابَ الراكب", field="amount")
    rules = await rules_for(session, ride.country_code)
    await rounding.require_multiple_in(session, ride.country_code, amount, field="amount")
    if amount <= ride.negotiation_offer:
        raise InvalidInput("سعرُك يساوي عرضَ الراكب أو أقلّ — اضغط «قبول»", field="amount")
    if rules.max_counter_percent is not None:
        cap = as_money(ride.negotiation_offer * (Decimal(100) + Decimal(rules.max_counter_percent)) / Decimal(100))
        if amount > cap:
            shown = money_text(cap, currency_for_country(ride.country_code))
            raise InvalidInput(f"أعلى سعرٍ تعرضه على هذه الرحلة {shown}", field="amount", maximum=str(cap))
    hit = await rate_limit.hit(redis, f"negotiate:driver:{driver.id}", limit=DRIVER_LIMIT, window_seconds=DRIVER_WINDOW)
    if not hit.allowed:
        raise RateLimited(f"عروضٌ كثيرة — جرّب بعد {hit.retry_after} ثانية", retry_after=hit.retry_after)

    ttl = rules.rider_timeout_seconds
    pipe = redis.pipeline()
    pipe.set(counter_key(ride.id), f"{driver.id}:{as_money(amount)}", ex=ttl)
    # **حجزُ الكبتن يُمدَّد بمهلة الراكب** — فلا يُعرض عليه طلبٌ آخر وهو ينتظر جوابَ هذا
    pipe.expire(dispatch.offer_key(ride.id), ttl)
    pipe.expire(dispatch.driver_offer_key(driver.id), ttl)
    await pipe.execute()
    await record(session, ride.id, "counter", amount=as_money(amount), driver_id=driver.id)
    await dispatch.notify_countered(redis, ride.id, driver.id)
    return rules


async def pending_counter(redis: Redis, ride_id: uuid.UUID) -> tuple[uuid.UUID, Decimal, int] | None:
    """`(الكبتن، السعر، الثواني الباقية)` للعرض المقابل المعلَّق — أو `None`."""
    raw = await redis.get(counter_key(ride_id))
    if raw is None:
        return None
    text = raw.decode() if isinstance(raw, bytes) else str(raw)
    driver_raw, _, amount_raw = text.partition(":")
    remaining = await redis.ttl(counter_key(ride_id))
    try:
        return uuid.UUID(driver_raw), Decimal(amount_raw), max(int(remaining or 0), 0)
    except (ValueError, ArithmeticError):  # pragma: no cover - قيمة تالفة
        return None


async def take_counter(redis: Redis, ride_id: uuid.UUID) -> tuple[uuid.UUID, Decimal] | None:
    """**يأخذ العرضَ المقابلَ مرّةً واحدة** (`GETDEL`) — فجوابان متزامنان من الراكب لا يجيبان معاً."""
    raw = await redis.getdel(counter_key(ride_id))
    if raw is None:
        return None
    text = raw.decode() if isinstance(raw, bytes) else str(raw)
    driver_raw, _, amount_raw = text.partition(":")
    try:
        return uuid.UUID(driver_raw), Decimal(amount_raw)
    except (ValueError, ArithmeticError):  # pragma: no cover
        return None
