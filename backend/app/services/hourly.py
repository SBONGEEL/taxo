"""بالساعة (SPEC §٦٣-ج/٥، قرارُ المالك ٢٠٢٦-١٠-٠٧) — **مطفأةٌ لكلِّ سوقٍ حتى يُشعلها المالك**.

**سعرُها ساعاتٌ لا طريق**: «الساعات × سعرها» مجمَّداً لحظةَ الطلب، **وما زاد** من كيلومترٍ فوق «الساعات × كيلومتراتها» ومن دقيقةٍ فوق
«الساعات × ٦٠» **بتسعيرة الاقتصادي العاديّة** — كلٌّ سطرٌ في `fare_lines`، **وعليها العمولةُ كأيِّ أجرة**.

**والمحجوزُ يُدفع عند البدء** (`prepay_on_start`، §٦٣-د/٧ توصيتي): من المحفظة دفعةٌ تُسوّى فوراً، **أو نقداً** دفعةٌ معلَّقةٌ يؤكّدها الكبتنُ
بمساره القائم. **والزيادةُ في النهاية** بالمسار القائم (`outstanding_amount` = الأجرة − المدفوع).

**وإلغاءُ الراكب بعد وصول الكبتن**: رسمُ إلغاءٍ **دقائقُ الإلغاء من سعر الساعة المجمَّد** (نصفُ ساعةٍ افتراضاً) — `cancel_fee`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import FeatureDisabled, InsufficientBalance, InvalidInput
from app.models.enums import (
    CountryCode,
    FeatureKey,
    PaymentConfirmedBy,
    PaymentMethod,
    VehicleCategory,
    WalletOwnerType,
)
from app.models.pricing import PricingRule
from app.models.ride import Ride
from app.models.service_setting import ServiceSetting
from app.models.user import User
from app.services import settings_service, wallet
from app.services.pricing import FareLine, round_money

PREPAY_METHODS = ("wallet", "cash")


class HourlyUnavailable(FeatureDisabled):
    code = "hourly_unavailable"
    message = "الرحلةُ بالساعة غيرُ مفعّلةٍ في بلدك"


@dataclass(frozen=True, slots=True)
class HourlyRequest:
    hours: int
    prepay: str


@dataclass(frozen=True, slots=True)
class HourlyTerms:
    hours: int
    rate: Decimal
    km_per_hour: int
    cancel_minutes: int
    prepay: str


async def settings_for(session: AsyncSession, country: CountryCode) -> ServiceSetting | None:
    if not await settings_service.is_feature_enabled(session, country, FeatureKey.HOURLY_ENABLED):
        return None
    row = await session.get(ServiceSetting, country)
    if row is None or row.hourly_rate <= 0:
        return None
    return row


async def prepare(
    session: AsyncSession, *, rider: User, request: HourlyRequest, vehicle_category: str
) -> HourlyTerms:
    row = await settings_for(session, rider.country_code)
    if row is None:
        raise HourlyUnavailable()
    if vehicle_category != VehicleCategory.ECONOMY:
        raise InvalidInput("الرحلةُ بالساعة بسعر الاقتصادي وحدَه")
    if not 1 <= request.hours <= row.hourly_max_hours:
        raise InvalidInput(f"الساعاتُ من 1 إلى {row.hourly_max_hours}")
    if request.prepay not in PREPAY_METHODS:
        raise InvalidInput("الساعاتُ المحجوزةُ تُدفع من المحفظة أو نقداً عند البدء")
    return HourlyTerms(
        hours=request.hours,
        rate=round_money(row.hourly_rate),
        km_per_hour=row.hourly_km_per_hour,
        cancel_minutes=row.hourly_cancel_minutes,
        prepay=request.prepay,
    )


def booked(hours: int, rate: Decimal) -> Decimal:
    return round_money(rate * hours)


def booked_line(hours: int, rate: Decimal) -> FareLine:
    return FareLine("hourly", booked(hours, rate), Decimal(hours))


def final_fare(ride: Ride, rule: PricingRule, actual_km: Decimal | None) -> tuple[Decimal, list[dict[str, str]]]:
    """**المحجوزُ وما زاد عليه** — والمسافةُ المسجَّلةُ إن وُجدت (صمتُ التطبيق لا يُحمَّل الراكبَ كيلومتراتٍ لا دليلَ عليها)."""
    hours = ride.hourly_hours or 0
    base = booked(hours, ride.hourly_rate_at_ride or Decimal(0))
    lines = [booked_line(hours, ride.hourly_rate_at_ride or Decimal(0)).as_json()]
    included_km = Decimal(hours * (ride.hourly_km_per_hour_at_ride or 0))
    extra_km = max((actual_km or Decimal(0)) - included_km, Decimal(0))
    elapsed = Decimal(0)
    if ride.started_at is not None:
        end = ride.completed_at or datetime.now(UTC)
        elapsed = Decimal(int((end - ride.started_at).total_seconds() // 60))
    extra_min = max(elapsed - Decimal(hours * 60), Decimal(0))
    km_charge = round_money(extra_km * rule.price_per_km)
    min_charge = round_money(extra_min * rule.price_per_min)
    if km_charge > 0:
        lines.append(FareLine("hourly_extra_km", km_charge, round_money(extra_km)).as_json())
    if min_charge > 0:
        lines.append(FareLine("hourly_extra_time", min_charge, extra_min).as_json())
    return round_money(base + km_charge + min_charge), lines


def prepay_key(ride_id: uuid.UUID) -> str:
    """**مفتاحُ تكرار دفعة المقدَّم** — به يُعرف صفُّها بين دفعات الرحلة (وعاءُ العمولة في `payments`)."""
    return f"hourly-prepay:{ride_id}"


def cancel_fee(ride: Ride) -> Decimal:
    """**دقائقُ الإلغاء من سعر الساعة المجمَّد** — نصفُ ساعةٍ افتراضاً، للكبتن بمسار رسم الإلغاء القائم."""
    rate = ride.hourly_rate_at_ride or Decimal(0)
    minutes = ride.hourly_cancel_minutes_at_ride or 0
    return round_money(rate * minutes / 60)


async def prepay_on_start(session: AsyncSession, ride: Ride) -> None:
    """**المحجوزُ عند البدء** — محفظةٌ تُسوّى فوراً، أو نقدٌ معلَّقٌ يؤكّده الكبتن. **ومفتاحُ التكرار على الرحلة** فبدءٌ يُعاد لا يدفع مرّتين؛
    والرحلةُ مقفولةٌ قبلها (`rides.start_ride`)، فالترتيبُ رحلةٌ ثمّ دفعةٌ ثمّ محفظة."""
    from app.services import payments, rounding

    # **المقدَّمُ مبلغٌ يدفعه الراكبُ الآن فيُقرَّب الآن** (SPEC §٧٠-ج/٤) بإعداد السوق — **ولا يُقرَّب مرّتين**: هو قسطٌ من الأجرة،
    # والإنهاءُ يقرّب ما بقي بعده (`rounding.apply_to_ride`)، ومضاعفٌ + تقريبُ الباقي = تقريبُ المجموع مرّةً حرفاً. **ولا صفَّ له
    # في السجلّ**: فرقُه يدخل فرقَ الرحلة كلِّها عند الإنهاء (سطرُ «تقريب» واحد). ومطفأً المحجوزُ كما كان حرفاً
    #
    # **والسياسةُ تُجمَّد على الرحلة الآن** (`rounding_*_at_ride`، مراجعةُ المال البند ٢): الإنهاءُ يقرّب الباقي **بها لا بإعداد
    # لحظته** — فإطفاءٌ أو اتجاهٌ آخرُ أو وحدةٌ أخرى في أثناء الرحلة لا تفصل المقدَّمَ عن باقيه، ولا يبقى فرقُه بلا سطر. والعدّادُ
    # يقرؤها من هنا أيضاً، فيعرض ما سيُحسب
    policy = await rounding.policy_for(session, ride.country_code)
    rounding.freeze_on(ride, policy)
    amount, _ = rounding.round_amount(
        booked(ride.hourly_hours or 0, ride.hourly_rate_at_ride or Decimal(0)), policy
    )
    if amount <= 0:
        return
    key = prepay_key(ride.id)
    if await payments._find_by_idempotency_key(session, key) is not None:
        return
    rider = await session.get(User, ride.rider_id)
    assert rider is not None
    if ride.hourly_prepay_method == "wallet":
        wallet.require_not_frozen(rider, WalletOwnerType.RIDER)
        await wallet.lock_wallet(session, rider.id)
        balance = await wallet.balance_of(session, rider, declared=WalletOwnerType.RIDER)
        if balance < amount:
            raise InsufficientBalance("رصيدُ الراكب لا يغطّي الساعاتِ المحجوزة — يشحن محفظتَه أو يختار الدفعَ نقداً")
        payment = payments._new_payment(ride, method=PaymentMethod.WALLET, amount=amount, idempotency_key=key)
        session.add(payment)
        await session.flush()
        await payments.settle(
            session, payment=payment, ride=ride, rider=rider, confirmed_by=PaymentConfirmedBy.SYSTEM, actor_id=rider.id
        )
        return
    payment = payments._new_payment(ride, method=PaymentMethod.CASH, amount=amount, idempotency_key=key)
    session.add(payment)
    await session.flush()
