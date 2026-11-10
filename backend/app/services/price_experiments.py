"""**تجاربُ الأسعار** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٤، SPEC §٩٧/٤) — البيتُ الواحد: من يقع في تجربة، وكم تغيّر أجرتَه، والمقارنة،
والقرار.

**الأثرُ سطرٌ في تفصيل الأجرة** (`experiment` — «تسعيرة تجريبية»): أجرةُ الطريق بعد المنطقة الوعرة × النسبة، **قبل رسوم الكبتن** (رسمٌ
للكبتن لا سعرُ رحلة) **وقبل التقريب**. ويُحسب في `pricing.estimate` وحدَه — **فالتقديرُ والطلبُ يحسبانه بالحساب نفسِه** — ويُعاد
عند الإنهاء بنسبة التجربة المجمَّدة على الرحلة.

**والذراعُ ثابتةٌ لكلِّ راكب** (بصمةُ معرّف التجربة والراكب): من رأى سعراً يرى مثلَه غداً، والتقديرُ يطابق الطلب.

**والأقفال**: كلُّ تغيير حالٍ يقفل صفَّ التجربة قبل فحص الانتقال (`locked`)، **و«تطبيقُ الفائز» يقفله ثمّ صفوفَ تسعيرة الدولة** —
بلا القفل يقرأ نقران «تعمل» معاً فتُضرب التسعيرةُ في النسبة مرّتين (`test_price_experiments_concurrency.py`). ولا صفَّ رحلةٍ ولا دفعٍ في
هذا المسار.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.exceptions import Conflict, InvalidInput, NotFound
from app.models.enums import CountryCode, FeatureKey, PriceExperimentArm, PriceExperimentStatus, RideStatus, WalletTransactionType
from app.models.price_experiment import PriceExperiment
from app.models.pricing import PricingRule
from app.models.ride import Ride
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.services import settings_service
from app.services.pickup_spots import meters

#: **حدودُ النسبة** — تجربةٌ لا تعيد تسعيرَ السوق؛ وما فوقها قرارُ تسعيرٍ لا تجربة
MAX_PERCENT = Decimal(50)


async def enabled(session: AsyncSession, country: CountryCode) -> bool:
    return await settings_service.is_feature_enabled(session, country, FeatureKey.PRICE_EXPERIMENTS_ENABLED)


def arm_of(experiment: PriceExperiment, rider_id: uuid.UUID) -> str:
    """**ذراعُ الراكب** — بصمةٌ ثابتةٌ لا عشوائيّة: الراكبُ نفسُه في الذراع نفسِها كلَّ مرّة."""
    bucket = int(hashlib.sha256(f"{experiment.id}:{rider_id}".encode()).hexdigest(), 16) % 100
    return PriceExperimentArm.TEST.value if bucket < experiment.share_percent else PriceExperimentArm.CONTROL.value


def covers(experiment: PriceExperiment, lat: float, lng: float) -> bool:
    if experiment.radius_km is None:
        return True
    return meters(lat, lng, experiment.center_lat, experiment.center_lng) <= float(experiment.radius_km) * 1000


@dataclass(frozen=True, slots=True)
class Assignment:
    experiment_id: uuid.UUID
    arm: str
    #: النسبةُ على أجرة الطريق — صفرٌ لذراع المقارنة
    percent: Decimal


async def assign(
    session: AsyncSession, *, country: CountryCode, rider_id: uuid.UUID, lat: float, lng: float, now: datetime | None = None
) -> Assignment | None:
    """**التجربةُ التي يقع فيها هذا الطلب** — `None` مطفأً، أو حيث لا تجربةَ تعمل في مدّتها ونطاقها."""
    if not await enabled(session, country):
        return None
    now = now or datetime.now(UTC)
    rows = await session.scalars(
        select(PriceExperiment)
        .where(
            PriceExperiment.country_code == country,
            PriceExperiment.status == PriceExperimentStatus.RUNNING.value,
            PriceExperiment.ends_at > now,
        )
        .order_by(PriceExperiment.started_at)
    )
    for experiment in rows:
        if covers(experiment, lat, lng):
            arm = arm_of(experiment, rider_id)
            percent = experiment.adjust_percent if arm == PriceExperimentArm.TEST.value else Decimal(0)
            return Assignment(experiment.id, arm, percent)
    return None


def adjustment(road_fare: Decimal, percent: Decimal, country: CountryCode) -> Decimal:
    """**مبلغُ السطر** — أجرةُ الطريق × النسبة، مقرَّباً بخانات العملة. وصفرٌ لذراع المقارنة."""
    from app.services import pricing

    if not percent:
        return Decimal(0)
    return pricing.round_money(road_fare * percent / Decimal(100), currency_for_country(country))


async def frozen_percent(session: AsyncSession, ride: Ride) -> Decimal:
    """**نسبةُ التجربة المجمَّدة على رحلة** — لإعادة الحساب عند الإنهاء؛ صفرٌ خارج ذراع التجربة."""
    if ride.price_experiment_id is None or ride.price_experiment_arm != PriceExperimentArm.TEST.value:
        return Decimal(0)
    experiment = await session.get(PriceExperiment, ride.price_experiment_id)
    return experiment.adjust_percent if experiment is not None else Decimal(0)


# ------------------------------------------------------------------ اللوحة


async def locked(session: AsyncSession, experiment_id: uuid.UUID) -> PriceExperiment:
    experiment = (
        await session.execute(
            select(PriceExperiment)
            .where(PriceExperiment.id == experiment_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if experiment is None:
        raise NotFound("التجربةُ غيرُ موجودة")
    return experiment


async def create(session: AsyncSession, *, country: CountryCode, actor: User, data: dict) -> PriceExperiment:
    percent = Decimal(str(data["adjust_percent"]))
    if percent == 0 or abs(percent) > MAX_PERCENT:
        raise InvalidInput("النسبةُ بين −50٪ و+50٪ ولا تكون صفراً")
    area = [data.get("center_lat"), data.get("center_lng"), data.get("radius_km")]
    if any(value is not None for value in area) and not all(value is not None for value in area):
        raise InvalidInput("النطاقُ نقطةٌ ونصفُ قطر معاً، أو الدولةُ كلُّها")
    experiment = PriceExperiment(
        country_code=country,
        name=data["name"].strip(),
        adjust_percent=percent,
        share_percent=int(data["share_percent"]),
        center_lat=data.get("center_lat"),
        center_lng=data.get("center_lng"),
        radius_km=data.get("radius_km"),
        days=int(data["days"]),
        created_by=actor.id,
    )
    session.add(experiment)
    await session.flush()
    return experiment


#: **الانتقالاتُ المسموحة** — من كلِّ حالٍ إلى ما يليها؛ وغيرُها `Conflict`
_MOVES = {
    "start": ({PriceExperimentStatus.DRAFT.value}, PriceExperimentStatus.RUNNING.value),
    "stop": ({PriceExperimentStatus.RUNNING.value}, PriceExperimentStatus.STOPPED.value),
    "apply": ({PriceExperimentStatus.RUNNING.value, PriceExperimentStatus.STOPPED.value}, PriceExperimentStatus.APPLIED.value),
    "cancel": (
        {PriceExperimentStatus.DRAFT.value, PriceExperimentStatus.RUNNING.value, PriceExperimentStatus.STOPPED.value},
        PriceExperimentStatus.CANCELLED.value,
    ),
}


async def _country_rules(session: AsyncSession, country: CountryCode) -> list[PricingRule]:
    """**صفوفُ تسعيرة الدولة مقفولة** — بعد صفِّ التجربة (ترتيبُ الأقفال: التجربةُ ثمّ التسعيرة)."""
    return list(
        (
            await session.scalars(
                select(PricingRule)
                .where(PricingRule.country_code == country)
                .order_by(PricingRule.vehicle_category)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).all()
    )


async def move(session: AsyncSession, experiment_id: uuid.UUID, action: str) -> tuple[PriceExperiment, dict]:
    """**تغييرُ الحال تحت قفل الصفّ** — والقفلُ قبل فحص الانتقال. ويعيد ما تغيّر في التسعيرة (للتدقيق) عند التطبيق."""
    from app.services import pricing

    allowed, target = _MOVES[action]
    experiment = await locked(session, experiment_id)
    if experiment.status not in allowed:
        raise Conflict("لا يصحّ هذا من حال التجربة الآن")
    now = datetime.now(UTC)
    changes: dict = {}
    if action == "start":
        experiment.started_at = now
        experiment.ends_at = now + timedelta(days=experiment.days)
    elif action == "stop":
        experiment.stopped_at = now
    elif action == "apply":
        # **تطبيقُ الفائز على تسعيرة الدولة كلِّها** — فلا يصحّ لتجربةٍ على جزءٍ منها: النتيجةُ هناك لا تقول شيئاً عن غيرها
        if experiment.radius_km is not None:
            raise InvalidInput("تجربةٌ على جزءٍ من الدولة لا تُطبَّق على الدولة كلِّها — أوقفها، وعدّل التسعيرةَ بيدك إن شئت")
        currency = currency_for_country(experiment.country_code)
        factor = Decimal(1) + experiment.adjust_percent / Decimal(100)
        for rule in await _country_rules(session, experiment.country_code):
            before = {field: str(getattr(rule, field)) for field in ("base_fare", "price_per_km", "price_per_min", "minimum_fare")}
            # **المبلغان بخانات العملة، والمعدّلان بدقّة التخزين** (معدّلٌ لا مبلغ — §٧٣)
            rule.base_fare = pricing.round_money(rule.base_fare * factor, currency)
            rule.minimum_fare = pricing.round_money(rule.minimum_fare * factor, currency)
            rule.price_per_km = pricing.as_money(rule.price_per_km * factor)
            rule.price_per_min = pricing.as_money(rule.price_per_min * factor)
            changes[str(rule.vehicle_category)] = {
                "from": before,
                "to": {field: str(getattr(rule, field)) for field in before},
            }
        experiment.stopped_at = experiment.stopped_at or now
        experiment.decided_at = now
    else:
        experiment.stopped_at = experiment.stopped_at or (now if experiment.status == PriceExperimentStatus.RUNNING.value else None)
        experiment.decided_at = now
    experiment.status = target
    await session.flush()
    return experiment, changes


@dataclass(frozen=True, slots=True)
class ArmStats:
    arm: str
    requests: int
    completed: int
    cancelled: int
    #: ما دفعه الركّاب في المكتملة
    fares: Decimal
    #: **إيرادُ TAXO**: العمولةُ من الدفتر
    commission: Decimal
    #: **دخلُ الكباتن**: الأجرةُ ناقصَ العمولة
    captains: Decimal
    completion_percent: int | None
    cancel_percent: int | None
    average_fare: Decimal | None


async def compare(session: AsyncSession, experiment: PriceExperiment) -> list[ArmStats]:
    """**المقارنةُ بين الذراعين** — مجمَّعةٌ في القاعدة (§١٤: الحسابُ في الخلفية)، والنسبُ هنا لا في اللوحة."""
    from app.services import pricing

    completed = Ride.status == RideStatus.COMPLETED
    rows = (
        await session.execute(
            select(
                Ride.price_experiment_arm,
                func.count(),
                func.count().filter(completed),
                func.count().filter(Ride.status.in_((RideStatus.CANCELLED_BY_RIDER, RideStatus.CANCELLED_BY_DRIVER))),
                func.coalesce(func.sum(case((completed, Ride.final_fare), else_=0)), 0),
            )
            .where(Ride.price_experiment_id == experiment.id)
            .group_by(Ride.price_experiment_arm)
        )
    ).all()
    commission_rows = (
        await session.execute(
            select(Ride.price_experiment_arm, func.coalesce(func.sum(WalletTransaction.amount), 0))
            .join(WalletTransaction, WalletTransaction.ride_id == Ride.id)
            .where(
                Ride.price_experiment_id == experiment.id,
                completed,
                WalletTransaction.type == WalletTransactionType.COMMISSION,
            )
            .group_by(Ride.price_experiment_arm)
        )
    ).all()
    commission = {arm: -Decimal(total) for arm, total in commission_rows}
    found = {arm: (requests, done, cancelled, Decimal(fares)) for arm, requests, done, cancelled, fares in rows}
    out = []
    for arm in (PriceExperimentArm.TEST.value, PriceExperimentArm.CONTROL.value):
        requests, done, cancelled, fares = found.get(arm, (0, 0, 0, Decimal(0)))
        taken = pricing.as_money(commission.get(arm, Decimal(0)))
        out.append(
            ArmStats(
                arm=arm,
                requests=requests,
                completed=done,
                cancelled=cancelled,
                fares=pricing.as_money(fares),
                commission=taken,
                captains=pricing.as_money(fares - taken),
                completion_percent=round(done * 100 / requests) if requests else None,
                cancel_percent=round(cancelled * 100 / requests) if requests else None,
                average_fare=pricing.as_money(fares / done) if done else None,
            )
        )
    return out
