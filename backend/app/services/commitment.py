"""**نقاطُ الالتزام** (أمرُ المالك ٢٠٢٦-١١-٢٤ السادس، الجزء ب؛ SPEC §١١٤-ب).

## الشرطُ اليوميّ — ومن أين يُقاس

**كلُّ دقيقةٍ يبثّ فيها الكبتنُ موقعَه داخل نطاق الخدمة دقيقةُ «اتّصال»** — تُكتب بتّاً في Redis (`duty:on:<كبتن>:<يوم>`) من بابِ البثّ
نفسِه (`drivers.report_location`)، فلا دقيقةَ بلا نبضةٍ حقيقيّةٍ من التطبيق. **واليومُ يومُ الدولة** (مِنطقتُها في إعداداتها).

**وتحقّقُ اليوم**: داخل النافذة (07:00–23:59 افتراضاً) مدّةٌ واحدةٌ من `span_minutes` (عشرُ ساعات) **تبدأ متّصلاً**، والاستراحاتُ **داخلها**:
كلُّ استراحةٍ ≤ `max_break_minutes` (ساعة)، ومجموعُها ≤ `max_total_break_minutes` (ساعتان) — فهو متّصلٌ ثماني ساعاتٍ على الأقلّ من العشر،
**ولا تُؤخذ الساعتان كتلةً واحدة** لأن كلَّ استراحةٍ ساعةٌ على الأكثر. **استراحةٌ فوق الساعة أو مجموعٌ فوق الساعتين ⇐ انقطعت المدّة**، ولمن
بقي له في النافذة متّسعٌ أن يبدأ مدّةً جديدة. **وصفرُ رحلاتٍ لا يُسقط اليوم.**

## منعُ الغشّ — يُسقط اليومَ بسببٍ يُرى، أو يُعلَّم للوحة

* **يُسقط**: موقعٌ مزيَّف (`mock_location`) أو محاكٍ (`emulator`) مقيسٌ على جهازه من التطبيق · **جهازٌ دخل منه حساباتُ كباتن أكثرُ من
  `max_accounts_per_device`** · (والرقمُ فريدٌ لكلِّ حسابٍ أصلاً).
* **لا تُحسب**: دقائقُ خارج نطاق الخدمة (`require_service_area`).
* **يُعلَّم ولا يُسقط** (`flags` — يراها المشرف): دقائقُ كثيرةٌ خارج النطاق، وثباتٌ في موضعٍ واحدٍ طوالَ المدّة بلا رحلة، وجهازٌ معدَّل.

## النقاط ورصيدُ الاشتراك

**النقاطُ لا تُصرف إلا رصيدَ اشتراك**، **ورصيدُ الاشتراك دفترٌ مستقلٌّ إلحاقيٌّ** (`subscription_credit_entries`) ليس في محفظة الكبتن — فلا
سحبَ ولا تحويلَ ولا نقدَ يقرؤه. **ولا يضع الوكيلُ قيمةً**: نقاطُ اليوم وقيمةُ التحويل والسقوفُ والصلاحيّةُ فارغةٌ حتى يضعها المالك من اللوحة،
**والقاعدةُ ترفض التشغيلَ بلا قيم** (قيدُ `0190`).

**ترتيبُ الأقفال**: صفُّ الكبتن (شراءُ الاشتراك) ⇐ قفلُ نقاطه الاستشاريّ ⇐ قفلُ رصيده الاستشاريّ — والاثنان في آخر السلسلة كقفل المحفظة.
"""

from __future__ import annotations

import hashlib
import json
import time as _time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import service_area
from app.core.currency import currency_for_country
from app.core.exceptions import Conflict, InvalidInput, NotFound, PermissionDenied
from app.models.commitment import (
    CREDIT_EXPIRY,
    CREDIT_FROM_POINTS,
    CREDIT_SUBSCRIPTION,
    DUTY_DISQUALIFIED,
    DUTY_MET,
    DUTY_NOT_MET,
    POINTS_CONVERSION,
    POINTS_DAILY,
    POINTS_DISCOUNTED_RIDE,
    POINTS_EXPIRY,
    CommitmentRule,
    DriverDutyDay,
    DriverPointsEntry,
    SubscriptionCreditEntry,
)
from app.core.currency import STORAGE_STEP
from app.models.device_login import DeviceLogin
from app.models.driver import Driver
from app.models.enums import AuditAction, CountryCode, Currency, PaymentMethod, RideStatus
from app.models.ride import Ride
from app.models.subscription import DriverSubscription
from app.models.user import User

#: **كسبٌ يُستهلك** — ما سواه سالبٌ لا باقيَ له
EARN_KINDS = (POINTS_DAILY, POINTS_DISCOUNTED_RIDE, "adjustment")
#: **عمرُ مفاتيح الدقائق في Redis** — يومُ أمس يُقيَّم بعد منتصف الليل، وهامشٌ لتعثّر المجدول
_KEY_TTL = 4 * 24 * 3600
#: **وحدةُ المال** — ثلاثُ خانات (§١)
_MONEY = STORAGE_STEP
#: **ثبات**: مواضعُ مميَّزةٌ (تقريبُ ثلاث خاناتٍ ≈ ١١٠ م) لا تتجاوز هذا العدد في مدّةٍ كاملةٍ بلا رحلة ⇐ علَم
_STATIONARY_POSITIONS = 3
#: **خارج النطاق**: دقائقُ أكثرُ من هذا ⇐ علَم
_OUTSIDE_FLAG_MINUTES = 30


def _now() -> datetime:
    return datetime.now(UTC)


def _minute(at: time) -> int:
    return at.hour * 60 + at.minute


# ===================================================================== المفاتيح


def on_key(driver_id: uuid.UUID, day: date) -> str:
    return f"duty:on:{driver_id}:{day:%Y%m%d}"


#: **ما يراه الكابتن وهو يبثّ من خارج نطاق الخدمة** — والدقائقُ لا تُحسب حتى يعود
OUT_OF_AREA_REASON = "أنت خارج نطاق الخدمة — دقائقُك الآن لا تُحسب حتى تعود"


def out_key(driver_id: uuid.UUID, day: date) -> str:
    return f"duty:out:{driver_id}:{day:%Y%m%d}"


def pos_key(driver_id: uuid.UUID, day: date) -> str:
    return f"duty:pos:{driver_id}:{day:%Y%m%d}"


def rule_key(country: CountryCode) -> str:
    return f"duty:rule:{country.value}"


# ===================================================================== القاعدة


async def get_rule(session: AsyncSession, country: CountryCode) -> CommitmentRule:
    """**قاعدةُ الدولة — تُنشأ بافتراضاتها مطفأةً أوّلَ قراءة** (كإعدادات الدول الأخرى): لا «لا قاعدة» تُقرأ «مطفأ» بالصدفة."""
    rule = await session.scalar(select(CommitmentRule).where(CommitmentRule.country_code == country))
    if rule is None:
        # **الصفُّ يُضاف داخل نقطة الحفظ لا قبلها**: `begin_nested` يدفع المعلَّقَ قبل أن يفتحها، فيسقط تكرارُ مسحين متزامنين
        # خارجها ويُفسد المعاملةَ كلَّها (قِيس: `PendingRollbackError` في `test_two_concurrent_sweeps_grant_once`)
        try:
            async with session.begin_nested():
                rule = CommitmentRule(country_code=country)
                session.add(rule)
                await session.flush()
        except IntegrityError:
            rule = await session.scalar(select(CommitmentRule).where(CommitmentRule.country_code == country))
            assert rule is not None
    return rule


def rule_ready(rule: CommitmentRule) -> bool:
    """**قيمُ المالك مكتوبة** — شرطُ التشغيل (وقيدُ القاعدة يحرسه أيضاً)."""
    return (
        rule.points_per_day is not None
        and rule.points_per_credit_unit is not None
        and rule.credit_unit_value is not None
    )


#: الحقولُ التي يحرّرها المشرف — وغيرُها لا يُكتب من الطلب
EDITABLE = (
    "is_enabled",
    "window_start",
    "window_end",
    "span_minutes",
    "max_break_minutes",
    "max_total_break_minutes",
    "points_per_day",
    "points_per_credit_unit",
    "credit_unit_value",
    "daily_points_cap",
    "monthly_points_cap",
    "points_expiry_days",
    "credit_expiry_days",
    "require_service_area",
    "max_accounts_per_device",
)


async def update_rule(
    session: AsyncSession, redis: Redis, *, country: CountryCode, changes: dict, actor: User
) -> CommitmentRule:
    """**تحريرُ القاعدة من اللوحة** — بقيد تدقيقٍ يحمل القديمَ والجديد، **ورفضٌ صريحٌ للتشغيل بلا قيم**."""
    from app.services import audit

    rule = await get_rule(session, country)
    before: dict[str, object] = {}
    after: dict[str, object] = {}
    for key, value in changes.items():
        if key not in EDITABLE:
            continue
        old = getattr(rule, key)
        if old != value:
            before[key] = str(old) if old is not None else None
            after[key] = str(value) if value is not None else None
            setattr(rule, key, value)
    if rule.is_enabled and not rule_ready(rule):
        raise InvalidInput(
            "لا تشغيلَ قبل أن تُكتب نقاطُ اليوم وقيمةُ تحويلها إلى رصيد اشتراك", field="is_enabled"
        )
    if not (0 < rule.max_break_minutes <= rule.max_total_break_minutes < rule.span_minutes):
        raise InvalidInput("الاستراحةُ الواحدة ≤ مجموعِ الاستراحات < المدّة", field="max_break_minutes")
    if rule.window_start >= rule.window_end:
        raise InvalidInput("بدايةُ النافذة قبل نهايتها", field="window_start")
    if _minute(rule.window_end) + 1 - _minute(rule.window_start) < rule.span_minutes:
        raise InvalidInput("المدّةُ أطولُ من النافذة", field="span_minutes")
    if after:
        await audit.record(
            session,
            actor=actor,
            action=AuditAction.UPDATE,
            entity_type="commitment_rule",
            entity_id=rule.id,
            details={"country_code": country.value},
            changes={key: {"from": before[key], "to": after[key]} for key in after},
        )
    await session.flush()
    await publish_rule(session, redis, rule)
    return rule


async def _zone_name(session: AsyncSession, country: CountryCode) -> str:
    from app.services import stats

    return (await stats._zone(session, country)).key


async def publish_rule(session: AsyncSession, redis: Redis, rule: CommitmentRule) -> None:
    """**لقطةُ القاعدة في Redis** — يقرؤها بابُ البثّ كلَّ دقيقةٍ بلا قاعدة بيانات (البثُّ كلَّ ثلاث ثوانٍ)."""
    snapshot = {
        "enabled": bool(rule.is_enabled),
        "zone": await _zone_name(session, rule.country_code),
        "area": bool(rule.require_service_area),
    }
    await redis.set(rule_key(rule.country_code), json.dumps(snapshot), ex=7 * 24 * 3600)


# ===================================================================== البثّ ⇐ الدقائق

#: ذاكرةُ العمليّة للقطة القاعدة — دقيقةٌ واحدة
_SNAPSHOTS: dict[str, tuple[float, dict | None]] = {}


async def _snapshot(redis: Redis, country: CountryCode) -> dict | None:
    cached = _SNAPSHOTS.get(country.value)
    now = _time.monotonic()
    if cached is not None and cached[0] > now:
        return cached[1]
    raw = await redis.get(rule_key(country))
    value = json.loads(raw) if raw else None
    _SNAPSHOTS[country.value] = (now + 60, value)
    return value


async def touch(
    redis: Redis,
    *,
    driver_id: uuid.UUID,
    country: CountryCode,
    lat: float,
    lng: float,
    now: datetime | None = None,
) -> None:
    """**دقيقةُ اتّصال** — يناديه بابُ البثّ. مطفأً لا يكتب شيئاً، **ولا يُسقط البثَّ بسقوطه** (يُبتلع الخطأ)."""
    try:
        snapshot = await _snapshot(redis, country)
        if not snapshot or not snapshot.get("enabled"):
            return
        local = (now or _now()).astimezone(ZoneInfo(snapshot["zone"]))
        day = local.date()
        minute = local.hour * 60 + local.minute
        inside = (not snapshot.get("area")) or service_area.box_for(country).holds(lat, lng)
        key = on_key(driver_id, day) if inside else out_key(driver_id, day)
        pipe = redis.pipeline()
        pipe.setbit(key, minute, 1)
        pipe.expire(key, _KEY_TTL)
        pipe.pfadd(pos_key(driver_id, day), f"{round(lat, 3)},{round(lng, 3)}")
        pipe.expire(pos_key(driver_id, day), _KEY_TTL)
        await pipe.execute()
    except Exception:  # noqa: BLE001 — البثُّ أهمُّ من دقيقة نقاط
        return


async def _raw(redis: Redis, key: str) -> bytes | None:
    """**البتّاتُ بايتاتٌ لا نصّ** — والعميلُ المشترك يفكّ الردودَ UTF-8 (`decode_responses=True`) فيسقط على `0xff`؛ فتُقرأ بلا فكّ."""
    return await redis.execute_command("GET", key, NEVER_DECODE=True)


def _bits(raw: bytes | None) -> list[bool]:
    """بتّاتُ اليوم الـ١٤٤٠ — البتُّ الأعلى في كلِّ بايتٍ أوّلاً (ترتيبُ `SETBIT`)."""
    out = [False] * 1440
    if not raw:
        return out
    for index, byte in enumerate(raw):
        for bit in range(8):
            minute = index * 8 + bit
            if minute >= 1440:
                return out
            out[minute] = bool(byte & (0x80 >> bit))
    return out


# ===================================================================== التقييم (دالّةٌ نقيّة)


@dataclass(slots=True)
class SpanResult:
    met: bool
    start: int | None = None
    end: int | None = None
    online_minutes: int = 0
    break_count: int = 0
    longest_break: int = 0
    total_break: int = 0
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class Shape:
    window_start: int
    window_end: int  # **حصريّة** — 23:59 ⇐ 1440
    span: int
    max_break: int
    max_total: int

    @classmethod
    def of(cls, rule: CommitmentRule) -> "Shape":
        return cls(
            window_start=_minute(rule.window_start),
            window_end=_minute(rule.window_end) + 1,
            span=rule.span_minutes,
            max_break=rule.max_break_minutes,
            max_total=rule.max_total_break_minutes,
        )


def _hours(minutes: int) -> str:
    """**المعدودُ بعدده** (فحصُ المالك ٢٦/١١: كان الكابتن يقرأ «مدّةُ 10 ساعة»). مواضعُه كلُّها مجرورةٌ أو مفعول («مدّةُ ساعتين»،
    «تجاوزت ساعتين») فالمثنّى بالياء: ١ «ساعة» · ٢ «ساعتين» · ٣–١٠ «N ساعات» · ١١ فما فوق «N ساعةً» — والكسرُ «1:30 ساعة»."""
    hours, rest = divmod(minutes, 60)
    if rest:
        return f"{hours}:{rest:02d} ساعة"
    if hours == 1:
        return "ساعة"
    if hours == 2:
        return "ساعتين"
    tail = hours % 100
    if 3 <= tail <= 10:
        return f"{hours} ساعات"
    if tail >= 11:
        return f"{hours} ساعةً"
    return f"{hours} ساعة"


def _scan(online: list[bool], start: int, stop: int, shape: Shape) -> SpanResult:
    """يمشي من `start` حتى `stop` (حصريّ) ويقف عند أوّل مخالفة — **والاستراحةُ الجارية تُحسب**."""
    run = 0
    total = 0
    count = 0
    longest = 0
    on = 0
    for minute in range(start, stop):
        if online[minute]:
            if run:
                count += 1
                run = 0
            on += 1
            continue
        run += 1
        total += 1
        longest = max(longest, run)
        if run > shape.max_break:
            return SpanResult(
                met=False, start=start, end=minute, online_minutes=on, break_count=count + 1, longest_break=run,
                total_break=total, reason=f"استراحةٌ تجاوزت {_hours(shape.max_break)} فانقطعت المدّة",
            )
        if total > shape.max_total:
            return SpanResult(
                met=False, start=start, end=minute, online_minutes=on, break_count=count + 1, longest_break=longest,
                total_break=total, reason=f"مجموعُ الاستراحات تجاوز {_hours(shape.max_total)} فانقطعت المدّة",
            )
    if run:
        count += 1
    return SpanResult(
        met=True, start=start, end=stop, online_minutes=on, break_count=count, longest_break=longest, total_break=total
    )


def evaluate(online: list[bool], shape: Shape) -> SpanResult:
    """**حكمُ يومٍ انتهت نافذتُه** — أوّلُ مدّةٍ مكتملة، وإلا أبعدُ محاولةٍ وسببُ انقطاعها."""
    starts = [
        minute
        for minute in range(shape.window_start, shape.window_end - shape.span + 1)
        if online[minute] and (minute == shape.window_start or not online[minute - 1])
    ]
    if not any(online[shape.window_start : shape.window_end]):
        return SpanResult(met=False, reason="لم تتّصل داخل النافذة اليوم")
    best: SpanResult | None = None
    for start in starts:
        result = _scan(online, start, start + shape.span, shape)
        if result.met:
            return result
        if best is None or (result.end or 0) - start > (best.end or 0) - (best.start or 0):
            best = result
    if best is None:
        return SpanResult(
            met=False,
            online_minutes=sum(online[shape.window_start : shape.window_end]),
            reason=f"لم تبدأ مدّةُ {_hours(shape.span)} يتّسع لها ما بقي من النافذة",
        )
    return best


@dataclass(slots=True)
class Progress:
    """**حالُ اليوم الجاري** — بطاقةُ الرئيسيّة."""

    state: str  # before_window · idle · running · met · broken · after_window
    elapsed_minutes: int = 0
    online_minutes: int = 0
    breaks_used_minutes: int = 0
    break_count: int = 0
    current_break_minutes: int = 0
    remaining_minutes: int = 0
    can_restart: bool = False
    reason: str | None = None


def progress(online: list[bool], shape: Shape, now_minute: int) -> Progress:
    """**المدّةُ الجارية الآن** — آخرُ بدايةٍ لم تنقطع حتى هذه الدقيقة، أو المكتملةُ إن اكتملت."""
    if now_minute < shape.window_start:
        return Progress(state="before_window", remaining_minutes=shape.span)
    final = evaluate(online, shape) if now_minute >= shape.window_end else None
    if final is not None:
        if final.met:
            return Progress(state="met", elapsed_minutes=shape.span, online_minutes=final.online_minutes,
                            breaks_used_minutes=final.total_break, break_count=final.break_count)
        return Progress(state="after_window", reason=final.reason)
    stop = now_minute + 1
    starts = [
        minute
        for minute in range(shape.window_start, min(stop, shape.window_end - shape.span + 1))
        if online[minute] and (minute == shape.window_start or not online[minute - 1])
    ]
    # **مدّةٌ اكتملت قبل الآن** تُقرأ «تحقّق» ولو انقطع ما بعدها
    for start in starts:
        if start + shape.span <= stop:
            done = _scan(online, start, start + shape.span, shape)
            if done.met:
                return Progress(state="met", elapsed_minutes=shape.span, online_minutes=done.online_minutes,
                                breaks_used_minutes=done.total_break, break_count=done.break_count)
    # **الأقدمُ أوّلاً**: مدّةٌ بدأت مبكّراً ولم تنقطع أطولُ ممّا بعدها — والسببُ إن انقطع الكلُّ سببُ آخرِ بداية
    last_reason: str | None = None
    for start in starts:
        if start + shape.span <= stop:
            continue
        running = _scan(online, start, stop, shape)
        if running.met:
            current = 0
            minute = now_minute
            while minute >= start and not online[minute]:
                current += 1
                minute -= 1
            elapsed = stop - start
            return Progress(
                state="running",
                elapsed_minutes=elapsed,
                online_minutes=running.online_minutes,
                breaks_used_minutes=running.total_break,
                break_count=running.break_count,
                current_break_minutes=current,
                remaining_minutes=shape.span - elapsed,
            )
        last_reason = running.reason
    can_restart = now_minute + shape.span <= shape.window_end
    if last_reason is not None:
        return Progress(state="broken", reason=last_reason, can_restart=can_restart, remaining_minutes=shape.span)
    if not can_restart:
        # **لا تُدعى إلى ما لا يتحقّق** (فحصُ المالك ٢٦/١١): بعد آخر بدايةٍ تتّسع لها النافذة كانت البطاقةُ تقول «اتّصل لتبدأ مدّةَ اليوم»
        # — وكلُّ اتّصالٍ بعدها لا يبلغ المدّة. فيومُ النقاط انتهى وإن بقيت النافذةُ مفتوحة، ويُقال متى يبدأ التالي
        start = f"{shape.window_start // 60:02d}:{shape.window_start % 60:02d}"
        return Progress(
            state="after_window",
            reason=f"لم يعد في نافذة اليوم متّسعٌ لمدّة {_hours(shape.span)} — تبدأ مدّتُك غداً من {start}",
            remaining_minutes=shape.span,
        )
    return Progress(state="idle", can_restart=can_restart, remaining_minutes=shape.span)


# ===================================================================== الأرصدة


async def points_balance(session: AsyncSession, driver_id: uuid.UUID, now: datetime | None = None) -> int:
    moment = now or _now()
    value = await session.scalar(
        select(func.coalesce(func.sum(DriverPointsEntry.remaining), 0)).where(
            DriverPointsEntry.driver_id == driver_id,
            DriverPointsEntry.remaining > 0,
            (DriverPointsEntry.expires_at.is_(None)) | (DriverPointsEntry.expires_at > moment),
        )
    )
    return int(value or 0)


async def credit_balance(session: AsyncSession, driver_id: uuid.UUID) -> Decimal:
    value = await session.scalar(
        select(func.coalesce(func.sum(SubscriptionCreditEntry.amount), 0)).where(
            SubscriptionCreditEntry.driver_id == driver_id
        )
    )
    return Decimal(value or 0).quantize(_MONEY)


def _advisory(prefix: str, driver_id: uuid.UUID) -> int:
    digest = hashlib.blake2b(f"{prefix}:{driver_id}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=True)


async def _lock(session: AsyncSession, prefix: str, driver_id: uuid.UUID) -> None:
    await session.execute(select(func.pg_advisory_xact_lock(_advisory(prefix, driver_id))))


# ===================================================================== الكسب


async def _day_bounds(session: AsyncSession, country: CountryCode, day: date) -> tuple[datetime, datetime]:
    zone = ZoneInfo(await _zone_name(session, country))
    start = datetime.combine(day, time(0, 0), zone).astimezone(UTC)
    return start, start + timedelta(days=1)


async def _earned(session: AsyncSession, driver_id: uuid.UUID, country: CountryCode, first: date, last: date) -> int:
    """**ما كُسب لأيّام [first, last] بتوقيت الدولة** — نقاطُ اليوم بيومها المقيَّم (تُكتب بعد منتصف ليله)، ونقاطُ الرحلات بوقت كتابتها."""
    start, _ = await _day_bounds(session, country, first)
    _, end = await _day_bounds(session, country, last)
    daily = await session.scalar(
        select(func.coalesce(func.sum(DriverPointsEntry.points), 0))
        .join(DriverDutyDay, DriverDutyDay.id == DriverPointsEntry.duty_day_id)
        .where(DriverPointsEntry.driver_id == driver_id, DriverDutyDay.day >= first, DriverDutyDay.day <= last)
    )
    rides = await session.scalar(
        select(func.coalesce(func.sum(DriverPointsEntry.points), 0)).where(
            DriverPointsEntry.driver_id == driver_id,
            DriverPointsEntry.kind == POINTS_DISCOUNTED_RIDE,
            DriverPointsEntry.created_at >= start,
            DriverPointsEntry.created_at < end,
        )
    )
    return int(daily or 0) + int(rides or 0)


async def award(
    session: AsyncSession,
    *,
    driver_id: uuid.UUID,
    country: CountryCode,
    rule: CommitmentRule,
    kind: str,
    points: int,
    day: date,
    duty_day_id: uuid.UUID | None = None,
    ride_id: uuid.UUID | None = None,
    reason: str | None = None,
) -> DriverPointsEntry | None:
    """**كسبٌ تحت السقفين** — يُقصّ إلى ما بقي من سقف اليوم والشهر، **وصفرٌ لا يُكتب**. تحت قفل نقاط الكبتن."""
    if points <= 0 or not rule.is_enabled:
        return None
    await _lock(session, "points", driver_id)
    granted = points
    if rule.daily_points_cap is not None:
        granted = min(granted, rule.daily_points_cap - await _earned(session, driver_id, country, day, day))
    if rule.monthly_points_cap is not None:
        month_end = (day.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        granted = min(granted, rule.monthly_points_cap - await _earned(session, driver_id, country, day.replace(day=1), month_end))
    if granted <= 0:
        return None
    now = _now()
    entry = DriverPointsEntry(
        driver_id=driver_id,
        country_code=country,
        kind=kind,
        points=granted,
        remaining=granted,
        expires_at=now + timedelta(days=rule.points_expiry_days) if rule.points_expiry_days else None,
        duty_day_id=duty_day_id,
        ride_id=ride_id,
        reason=reason,
    )
    session.add(entry)
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError:
        # **يومٌ أو رحلةٌ كسبت مرّةً** — الفريدُ يردّ الثانية
        return None
    return entry


async def award_discounted_ride(session: AsyncSession, ride: Ride, points_per_ride: int | None) -> None:
    """**نقاطٌ إضافيّةٌ عن رحلةٍ بخصم الافتتاح** (§١١٤-د/أ) — لا مال، وتحت سقفي اليوم والشهر."""
    if not points_per_ride or ride.driver_id is None:
        return
    rule = await get_rule(session, ride.country_code)
    if not rule.is_enabled:
        return
    from app.services import stats

    await award(
        session,
        driver_id=ride.driver_id,
        country=ride.country_code,
        rule=rule,
        kind=POINTS_DISCOUNTED_RIDE,
        points=points_per_ride,
        day=await stats.country_today(session, ride.country_code),
        ride_id=ride.id,
        reason="رحلةٌ بخصم الافتتاح",
    )


# ===================================================================== تقييمُ اليوم


async def _signals_reason(driver: Driver, day_start: datetime | None = None) -> str | None:
    """**هاتفٌ حقيقيٌّ بلا موقعٍ مزيَّف** — مقيسٌ من غلاف التطبيق؛ **وغيابُ القياس يُسقط اليوم** (متصفّحٌ يزيّف موقعَه بلا أثر)."""
    signals = driver.device_signals or {}
    measured_at = driver.device_signals_at
    if "mock_location" not in signals or measured_at is None or (
        day_start is not None and measured_at < day_start - timedelta(days=1)
    ):
        return "لم تصل إشاراتُ الجهاز — النقاطُ من تطبيق الكابتن المثبَّت على هاتفٍ حقيقيّ"
    if signals.get("emulator") is True:
        return "التطبيقُ يعمل على محاكٍ لا على هاتفٍ حقيقيّ"
    if signals.get("mock_location") is True:
        return "رُصد موقعٌ وهميٌّ (تطبيقُ تزييف الموقع) على جهازك"
    return None


async def _shared_device_reason(session: AsyncSession, driver: Driver, limit: int) -> str | None:
    devices = select(DeviceLogin.device_id).where(DeviceLogin.user_id == driver.user_id, DeviceLogin.app == "driver")
    accounts = await session.scalar(
        select(func.count(func.distinct(DeviceLogin.user_id))).where(
            DeviceLogin.device_id.in_(devices), DeviceLogin.app == "driver"
        )
    )
    if accounts and accounts > limit:
        return "هذا الجهازُ دخل منه أكثرُ من حساب كابتن — النقاطُ لحسابٍ واحدٍ في الجهاز"
    return None


async def evaluate_driver_day(
    session: AsyncSession,
    redis: Redis,
    *,
    driver: Driver,
    country: CountryCode,
    day: date,
    rule: CommitmentRule,
) -> DriverDutyDay | None:
    """**حكمُ يومٍ واحدٍ لكبتنٍ واحد** — يُكتب مرّةً (الفريد)، والنقاطُ معه إن تحقّق ولم يُسقط."""
    exists = await session.scalar(
        select(DriverDutyDay.id).where(DriverDutyDay.driver_id == driver.id, DriverDutyDay.day == day)
    )
    if exists is not None:
        return None
    shape = Shape.of(rule)
    online = _bits(await _raw(redis, on_key(driver.id, day)))
    outside = sum(_bits(await _raw(redis, out_key(driver.id, day))))
    positions = int(await redis.pfcount(pos_key(driver.id, day)) or 0)
    result = evaluate(online, shape)
    day_start, day_end = await _day_bounds(session, country, day)
    rides = int(
        await session.scalar(
            select(func.count()).select_from(Ride).where(
                Ride.driver_id == driver.id,
                Ride.status == RideStatus.COMPLETED,
                Ride.completed_at >= day_start,
                Ride.completed_at < day_end,
            )
        )
        or 0
    )

    flags: list[str] = []
    if outside > _OUTSIDE_FLAG_MINUTES:
        flags.append(f"{outside} دقيقةً خارج نطاق الخدمة")
    if result.met and rides == 0 and positions <= _STATIONARY_POSITIONS:
        flags.append("ثابتٌ في موضعٍ واحدٍ طوالَ المدّة بلا رحلات")
    if (driver.device_signals or {}).get("rooted") is True:
        flags.append("جهازٌ معدَّل (روت)")

    status = DUTY_MET if result.met else DUTY_NOT_MET
    reason = result.reason
    if result.met:
        reason = await _signals_reason(driver, day_start) or await _shared_device_reason(
            session, driver, rule.max_accounts_per_device
        )
        if reason is not None:
            status = DUTY_DISQUALIFIED
            flags.append(reason)

    zone = ZoneInfo(await _zone_name(session, country))
    base = datetime.combine(day, time(0, 0), zone)
    row = DriverDutyDay(
        driver_id=driver.id,
        country_code=country,
        day=day,
        status=status,
        online_minutes=sum(online[shape.window_start : shape.window_end]),
        break_count=result.break_count,
        longest_break_minutes=result.longest_break,
        total_break_minutes=result.total_break,
        span_start=(base + timedelta(minutes=result.start)).astimezone(UTC) if result.start is not None else None,
        span_end=(base + timedelta(minutes=result.end)).astimezone(UTC) if result.end is not None else None,
        reason=reason,
        flags=flags,
        rides_completed=rides,
        evaluated_at=_now(),
    )
    session.add(row)
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError:
        return None
    if status == DUTY_MET and rule.points_per_day:
        await award(
            session,
            driver_id=driver.id,
            country=country,
            rule=rule,
            kind=POINTS_DAILY,
            points=rule.points_per_day,
            day=day,
            duty_day_id=row.id,
            reason="يومُ التزامٍ مكتمل",
        )
    return row


async def evaluate_country_day(session: AsyncSession, redis: Redis, *, country: CountryCode, day: date) -> int:
    """**كلُّ من اتّصل ذلك اليوم** — من مفاتيح Redis لا من جدول الكباتن، فيُقيَّم من بثّ وحدَه."""
    rule = await get_rule(session, country)
    if not rule.is_enabled:
        return 0
    pattern = f"duty:on:*:{day:%Y%m%d}"
    written = 0
    async for raw in redis.scan_iter(match=pattern, count=500):
        key = raw.decode() if isinstance(raw, bytes) else raw
        try:
            driver_id = uuid.UUID(key.split(":")[2])
        except (IndexError, ValueError):
            continue
        driver = await session.get(Driver, driver_id)
        if driver is None:
            continue
        country_of = await session.scalar(select(User.country_code).where(User.id == driver.user_id))
        if country_of != country:
            continue
        if await evaluate_driver_day(session, redis, driver=driver, country=country, day=day, rule=rule):
            written += 1
    return written


async def sweep(session: AsyncSession, redis: Redis, now: datetime | None = None) -> dict[str, int]:
    """**المجدول** (كلَّ عشر دقائق): يومُ أمس دائماً، واليومُ إن انتهت نافذتُه — ثمّ انتهاءُ النقاط والرصيد. **مطفأً لا يكتب شيئاً.**"""
    moment = now or _now()
    done: dict[str, int] = {}
    for country in CountryCode:
        rule = await get_rule(session, country)
        await publish_rule(session, redis, rule)
        if not rule.is_enabled:
            continue
        zone = ZoneInfo(await _zone_name(session, country))
        local = moment.astimezone(zone)
        days = [local.date() - timedelta(days=1)]
        if local.hour * 60 + local.minute >= _minute(rule.window_end) + 1:
            days.append(local.date())
        count = 0
        for day in days:
            count += await evaluate_country_day(session, redis, country=country, day=day)
        done[country.value] = count
    await expire_points(session, moment)
    await expire_credit(session, moment)
    return done


# ===================================================================== التحويلُ والانتهاء


@dataclass(frozen=True, slots=True)
class Conversion:
    points: int
    amount: Decimal
    currency: str
    credit_balance: Decimal


async def convert(session: AsyncSession, *, driver: Driver, user: User, points: int) -> Conversion:
    """**نقاطٌ ⇐ رصيدُ اشتراك** — بمضاعفات وحدة التحويل وحدَها، **والأقدمُ يُستهلك أوّلاً**، تحت قفلَي النقاط والرصيد."""
    from app.services import audit

    rule = await get_rule(session, user.country_code)
    if not rule.is_enabled or not rule_ready(rule):
        raise PermissionDenied("نقاطُ الالتزام غيرُ مفعّلةٍ في بلدك الآن")
    unit = int(rule.points_per_credit_unit or 0)
    if points <= 0 or points % unit != 0:
        raise InvalidInput(f"حوّل بمضاعفات {unit} نقطة", field="points")
    await _lock(session, "points", driver.id)
    await _lock(session, "credit", driver.id)
    now = _now()
    if points > await points_balance(session, driver.id, now):
        raise Conflict("نقاطُك لا تكفي")
    rows = (
        await session.execute(
            select(DriverPointsEntry)
            .where(
                DriverPointsEntry.driver_id == driver.id,
                DriverPointsEntry.remaining > 0,
                (DriverPointsEntry.expires_at.is_(None)) | (DriverPointsEntry.expires_at > now),
            )
            .order_by(DriverPointsEntry.created_at, DriverPointsEntry.id)
            .with_for_update()
        )
    ).scalars().all()
    left = points
    for row in rows:
        take = min(row.remaining, left)
        row.remaining -= take
        left -= take
        if left == 0:
            break
    amount = (Decimal(points // unit) * Decimal(rule.credit_unit_value)).quantize(_MONEY)
    currency = currency_for_country(user.country_code)
    balance = await credit_balance(session, driver.id)
    credit = SubscriptionCreditEntry(
        id=uuid.uuid4(),
        driver_id=driver.id,
        country_code=user.country_code,
        currency=currency,
        kind=CREDIT_FROM_POINTS,
        amount=amount,
        balance_after=balance + amount,
        points=points,
        expires_at=now + timedelta(days=rule.credit_expiry_days) if rule.credit_expiry_days else None,
        reference=f"{points} نقطة",
        created_by=user.id,
    )
    session.add(credit)
    session.add(
        DriverPointsEntry(
            driver_id=driver.id,
            country_code=user.country_code,
            kind=POINTS_CONVERSION,
            points=-points,
            remaining=0,
            credit_entry_id=credit.id,
            reason="تحويلٌ إلى رصيد اشتراك",
            created_by=user.id,
        )
    )
    await audit.record(
        session,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="subscription_credit_entry",
        entity_id=credit.id,
        details={"driver_id": str(driver.id), "kind": CREDIT_FROM_POINTS, "points": points},
    )
    await session.flush()
    return Conversion(points=points, amount=amount, currency=currency.value, credit_balance=balance + amount)


async def expire_points(session: AsyncSession, now: datetime) -> int:
    """**النقاطُ المنتهية** — قيدٌ سالبٌ بما بقي منها، والباقي صفر. لا تُخصم مرّتين."""
    rows = (
        await session.execute(
            select(DriverPointsEntry)
            .where(DriverPointsEntry.remaining > 0, DriverPointsEntry.expires_at <= now)
            .with_for_update(skip_locked=True)
            .limit(2000)
        )
    ).scalars().all()
    for row in rows:
        session.add(
            DriverPointsEntry(
                driver_id=row.driver_id,
                country_code=row.country_code,
                kind=POINTS_EXPIRY,
                points=-row.remaining,
                remaining=0,
                reason="انتهت صلاحيّتها",
            )
        )
        row.remaining = 0
    await session.flush()
    return len(rows)


async def expire_credit(session: AsyncSession, now: datetime) -> int:
    """**الرصيدُ المنتهي** — ما زاد من الرصيد على ما لم ينتهِ من التحويلات (الصرفُ يأكل الأقدمَ أوّلاً)."""
    drivers = (
        await session.execute(
            select(SubscriptionCreditEntry.driver_id)
            .where(SubscriptionCreditEntry.kind == CREDIT_FROM_POINTS, SubscriptionCreditEntry.expires_at <= now)
            .distinct()
        )
    ).scalars().all()
    written = 0
    for driver_id in drivers:
        await _lock(session, "credit", driver_id)
        balance = await credit_balance(session, driver_id)
        if balance <= 0:
            continue
        valid = await session.scalar(
            select(func.coalesce(func.sum(SubscriptionCreditEntry.amount), 0)).where(
                SubscriptionCreditEntry.driver_id == driver_id,
                SubscriptionCreditEntry.amount > 0,
                (SubscriptionCreditEntry.expires_at.is_(None)) | (SubscriptionCreditEntry.expires_at > now),
            )
        )
        expired = (balance - Decimal(valid or 0)).quantize(_MONEY)
        if expired <= 0:
            continue
        last = await session.scalar(
            select(SubscriptionCreditEntry)
            .where(SubscriptionCreditEntry.driver_id == driver_id)
            .order_by(SubscriptionCreditEntry.created_at.desc())
            .limit(1)
        )
        assert last is not None
        session.add(
            SubscriptionCreditEntry(
                driver_id=driver_id,
                country_code=last.country_code,
                currency=last.currency,
                kind=CREDIT_EXPIRY,
                amount=-expired,
                balance_after=balance - expired,
                reference="انتهت صلاحيّتُه",
            )
        )
        written += 1
    await session.flush()
    return written


# ===================================================================== الصرف: اشتراكٌ برصيد الاشتراك


async def purchase_with_credit(
    session: AsyncSession, *, driver: Driver, user: User, plan_id: uuid.UUID, idempotency_key: str
) -> DriverSubscription:
    """**اشتراكٌ يُدفع كلُّه من رصيد الاشتراك** — بالثمن نفسِه الذي تعرضه الشاشة (العرضُ ثمّ التقريب)، **ولا دفعَ جزئيّ**.

    **ترتيبُ الأقفال**: صفُّ الكبتن ثمّ قفلُ رصيده الاستشاريّ (آخراً، كقفل المحفظة).
    """
    from app.services import offers, subscriptions

    locked = await subscriptions._locked_driver(session, driver.id)
    subscriptions.require_purchasable(locked)
    existing = await subscriptions._find_by_idempotency_key(session, idempotency_key)
    if existing is not None:
        return existing
    plan = await subscriptions.get_plan(session, plan_id, user.country_code, held_ok=bool(user.is_test))
    offer = await offers.resolve(session, driver=locked, plan=plan, for_update=True)
    price = await subscriptions.price_to_pay(session, plan, offer)
    payable = price.payable
    if payable <= 0:
        raise InvalidInput("هذه الباقةُ بلا ثمنٍ يُدفع", field="plan_id")
    await _lock(session, "credit", driver.id)
    balance = await credit_balance(session, driver.id)
    if balance < payable:
        raise Conflict("رصيدُ الاشتراك لا يكفي لهذه الباقة")
    subscription = await subscriptions._create(
        session,
        driver=locked,
        plan=plan,
        method=PaymentMethod.SUBSCRIPTION_CREDIT,
        amount_paid=payable,
        idempotency_key=idempotency_key,
        offer=offer,
        price=price,
    )
    session.add(
        SubscriptionCreditEntry(
            driver_id=driver.id,
            country_code=user.country_code,
            currency=plan.currency,
            kind=CREDIT_SUBSCRIPTION,
            amount=-payable,
            balance_after=balance - payable,
            subscription_id=subscription.id,
            reference=plan.name,
            idempotency_key=f"credit-sub:{idempotency_key}",
            created_by=user.id,
        )
    )
    await session.flush()
    return subscription


# ===================================================================== القراءة للشاشتين


@dataclass(slots=True)
class DriverView:
    enabled: bool
    window_start: str
    window_end: str
    span_minutes: int
    max_break_minutes: int
    max_total_break_minutes: int
    points_per_day: int | None
    points_per_credit_unit: int | None
    credit_unit_value: str | None
    currency: str
    points_balance: int
    credit_balance: str
    credit_value_of_points: str | None
    #: **ما يُحوَّل الآن** — أكبرُ مضاعفٍ لوحدة التحويل في الرصيد، تحسبه الخلفيّة (§14)
    convertible_points: int
    today: dict
    recent: list[dict] = field(default_factory=list)


async def driver_view(session: AsyncSession, redis: Redis, *, driver: Driver, user: User) -> DriverView:
    rule = await get_rule(session, user.country_code)
    zone = ZoneInfo(await _zone_name(session, user.country_code))
    local = _now().astimezone(zone)
    shape = Shape.of(rule)
    online = _bits(await _raw(redis, on_key(driver.id, local.date())))
    now_minute = local.hour * 60 + local.minute
    today = progress(online, shape, now_minute)
    # **خارج نطاق الخدمة الآن ⇐ سببٌ ظاهرٌ للكابتن** (أمرُ المالك ٢٦/١١): دقائقُ الخارج لا تُحسب (`touch`) فكانت تُقرأ «استراحة» بلا سبب،
    # والعلَمُ عند المشرف وحدَه. فإن كانت آخرُ دقيقتين بثٌّ خارج النطاق لا داخله قيل ذلك صريحاً — **ولا يتغيّر الحسابُ ولا الحكم**
    if rule.require_service_area and today.state in ("running", "broken", "idle") and today.reason is None:
        outside = _bits(await _raw(redis, out_key(driver.id, local.date())))
        recent_minutes = [m for m in (now_minute, now_minute - 1) if 0 <= m < len(outside)]
        if any(outside[m] for m in recent_minutes) and not any(online[m] for m in recent_minutes if m < len(online)):
            today.reason = OUT_OF_AREA_REASON
    balance = await points_balance(session, driver.id)
    credit = await credit_balance(session, driver.id)
    currency = currency_for_country(user.country_code)
    value_of_points: str | None = None
    if rule_ready(rule):
        units = balance // int(rule.points_per_credit_unit or 1)
        value_of_points = str((Decimal(units) * Decimal(rule.credit_unit_value)).quantize(_MONEY))
    recent = (
        await session.execute(
            select(DriverDutyDay)
            .where(DriverDutyDay.driver_id == driver.id)
            .order_by(DriverDutyDay.day.desc())
            .limit(14)
        )
    ).scalars().all()
    return DriverView(
        enabled=bool(rule.is_enabled),
        window_start=rule.window_start.strftime("%H:%M"),
        window_end=rule.window_end.strftime("%H:%M"),
        span_minutes=rule.span_minutes,
        max_break_minutes=rule.max_break_minutes,
        max_total_break_minutes=rule.max_total_break_minutes,
        points_per_day=rule.points_per_day,
        points_per_credit_unit=rule.points_per_credit_unit,
        credit_unit_value=str(rule.credit_unit_value) if rule.credit_unit_value is not None else None,
        currency=currency.value,
        points_balance=balance,
        credit_balance=str(credit),
        credit_value_of_points=value_of_points,
        convertible_points=(balance // rule.points_per_credit_unit) * rule.points_per_credit_unit if rule.points_per_credit_unit else 0,
        today=asdict(today),
        recent=[
            {
                "day": row.day.isoformat(),
                "status": row.status,
                "reason": row.reason,
                "online_minutes": row.online_minutes,
                "total_break_minutes": row.total_break_minutes,
            }
            for row in recent
        ],
    )


async def report(session: AsyncSession, *, country: CountryCode, month: date) -> list[dict]:
    """**تقريرُ اللوحة لكلِّ كبتن في الشهر** — أيّامٌ تحقّقت وأُسقطت ولم تتحقّق، والأعلامُ، والأرصدة. **والتجميعُ في القاعدة.**"""
    start = month.replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1)
    rows = (
        await session.execute(
            select(
                DriverDutyDay.driver_id,
                func.count().filter(DriverDutyDay.status == DUTY_MET),
                func.count().filter(DriverDutyDay.status == DUTY_DISQUALIFIED),
                func.count().filter(DriverDutyDay.status == DUTY_NOT_MET),
                func.count().filter(func.jsonb_array_length(DriverDutyDay.flags) > 0),
            )
            .where(DriverDutyDay.country_code == country, DriverDutyDay.day >= start, DriverDutyDay.day < end)
            .group_by(DriverDutyDay.driver_id)
        )
    ).all()
    out = []
    for driver_id, met, disqualified, not_met, flagged in rows:
        driver = await session.get(Driver, driver_id)
        name = None
        if driver is not None:
            name = await session.scalar(select(User.name).where(User.id == driver.user_id))
        out.append(
            {
                "driver_id": str(driver_id),
                "driver_name": name,
                "met": met,
                "disqualified": disqualified,
                "not_met": not_met,
                "flagged": flagged,
                "points_balance": await points_balance(session, driver_id),
                "credit_balance": str(await credit_balance(session, driver_id)),
            }
        )
    out.sort(key=lambda row: (-row["met"], row["driver_name"] or ""))
    return out


async def driver_days(session: AsyncSession, *, driver_id: uuid.UUID, limit: int = 62) -> list[DriverDutyDay]:
    driver = await session.get(Driver, driver_id)
    if driver is None:
        raise NotFound("الكابتن غير موجود")
    return list(
        (
            await session.execute(
                select(DriverDutyDay)
                .where(DriverDutyDay.driver_id == driver_id)
                .order_by(DriverDutyDay.day.desc())
                .limit(limit)
            )
        ).scalars()
    )


async def flagged_days(session: AsyncSession, *, country: CountryCode, limit: int = 200) -> list[DriverDutyDay]:
    return list(
        (
            await session.execute(
                select(DriverDutyDay)
                .where(
                    DriverDutyDay.country_code == country,
                    (DriverDutyDay.status == DUTY_DISQUALIFIED) | (func.jsonb_array_length(DriverDutyDay.flags) > 0),
                )
                .order_by(DriverDutyDay.day.desc())
                .limit(limit)
            )
        ).scalars()
    )


__all__ = [
    "Currency",
    "Shape",
    "award",
    "convert",
    "driver_view",
    "evaluate",
    "progress",
    "purchase_with_credit",
    "sweep",
    "touch",
]
