"""تسعير الرحلة — في الخلفية حصراً (SPEC القسم 5).

    estimated_fare = base_fare + (km × price_per_km) + (min × price_per_min)
                     + (عدد المحطات الوسيطة × stop_fee)

بحدٍّ أدنى `minimum_fare`. كل الحساب بـ Decimal: مبالغ NUMERIC(12,3) لا float.

**ورسمُ الانتظار خارج التقدير عمداً** (المرحلة 12-ب، SPEC القسم 5.10): لا
يُعرف قبل أن يقع، فيُضاف إلى `final_fare` عند الإنهاء. والشاشةُ تقول سعرَه
قبل الطلب فيكون **معلوماً** ولو لم يكن مقدَّراً.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.exceptions import PricingRuleMissing
from app.models.enums import CountryCode, Currency, VehicleCategory
from app.models.pricing import PricingRule
from app.services.directions import Coordinates, Route, route_between

if TYPE_CHECKING:
    from app.models.ride import RideStop

# دقة الأعمدة المالية نفسها — التقريب مرة واحدة في النهاية لا في كل حد
MONEY_STEP = Decimal("0.001")


@dataclass(frozen=True, slots=True)
class FareEstimate:
    country_code: CountryCode
    vehicle_category: VehicleCategory
    currency: Currency
    route: Route
    fare: Decimal
    minimum_fare_applied: bool
    # **شروطُ الوقوف كما ستُجمَّد على الرحلة لو طُلبت الآن** (§5.10).
    #
    # **ومحلُّها التقديرُ لا `GET /config`، والسببُ قياسٌ لا ذوق**: الأربعةُ
    # على `pricing_rules` أي **لكلِّ (دولة × فئة)**، و`/config` ينشر
    # `vehicle_categories` قائمةَ رموزٍ بلا بنيةٍ تُعلَّق عليها — فنشرُها هناك
    # إمّا كذبٌ (تُؤخذ فئةٌ وتُسمّى الدولة) أو خريطةٌ متداخلةٌ تُمرَّر إلى ثلاث
    # مرايا. **والتقديرُ يعرف الفئةَ المختارة**، وهو الموضعُ الذي يُقرأ فيه
    # السعرُ قبل القبول — فمن قَبِل يعرف ما يدفعه لو انتظر.
    stop_fee: Decimal
    stop_free_minutes: int
    stop_price_per_min: Decimal
    stop_max_wait_minutes: int


def round_money(amount: Decimal) -> Decimal:
    return amount.quantize(MONEY_STEP, rounding=ROUND_HALF_UP)


def calculate_fare(
    rule: PricingRule, route: Route, stops_count: int = 0
) -> tuple[Decimal, bool]:
    """السعر وهل جبره الحد الأدنى.

    و`stops_count` عددُ المحطات **الوسيطة**: رسمُها المقطوع يدخل التقدير
    المعروض قبل الطلب، بخلاف رسم الانتظار الذي لا يُعرف إلا بعد وقوعه.
    """
    # `rule.stop_fee or 0`: العمودُ `server_default="0"` فكلُّ صفٍّ في القاعدة
    # يحمل قيمة، أما صفٌّ بُني في الذاكرة ولم يُفلَش بعد فحقلُه `None` —
    # والأجرةُ لا يجوز أن تتعلق بلحظة الفلش
    fare = (
        rule.base_fare
        + route.distance_km * rule.price_per_km
        + route.duration_min * rule.price_per_min
        + (rule.stop_fee or Decimal(0)) * stops_count
    )
    fare = round_money(fare)

    minimum = round_money(rule.minimum_fare)
    if fare < minimum:
        return minimum, True
    return fare, False


async def get_rule(
    session: AsyncSession, country_code: CountryCode, vehicle_category: VehicleCategory
) -> PricingRule:
    rule = await session.scalar(
        select(PricingRule).where(
            PricingRule.country_code == country_code,
            PricingRule.vehicle_category == vehicle_category,
        )
    )
    if rule is None:
        raise PricingRuleMissing()
    return rule


async def estimate(
    session: AsyncSession,
    *,
    country_code: CountryCode,
    vehicle_category: VehicleCategory,
    pickup: Coordinates,
    dropoff: Coordinates,
    stops: Sequence[Coordinates] = (),
) -> FareEstimate:
    """تسعيرة الدولة + مسار Mapbox → سعر مقدّر.

    تُستدعى مرتين: لعرض التقدير للراكب، ثم مجدداً عند إنشاء الرحلة — فالسعر
    المخزَّن يُحسب في الخلفية ولا يُقبل من العميل أبداً.

    و`stops` المحطاتُ الوسيطة بترتيبها: تدخل **المسارَ** (فالمسافة والمدة
    مسافةُ الطريق كلِّه ومدتُه) و**الرسمَ المقطوع** معاً.
    """
    rule = await get_rule(session, country_code, vehicle_category)
    route = await route_between(session, pickup, dropoff, country_code, stops=stops)
    fare, minimum_applied = calculate_fare(rule, route, len(stops))

    return FareEstimate(
        country_code=CountryCode(country_code),
        vehicle_category=VehicleCategory(vehicle_category),
        currency=currency_for_country(country_code),
        route=route,
        fare=fare,
        minimum_fare_applied=minimum_applied,
        # **`round_money` على الصفر أيضاً — وهذا ليس تزيّداً** (الشكلُ السابع):
        # `Decimal(0)` المبنيُّ في بايثون يُسلسَل `"0"` لا `"0.000"`، فيقرأ
        # الراكبُ `0` في عمودٍ كلُّه ثلاثُ خانات. **وأمسكه `money_format`
        # فعلاً** عند أول تشغيلٍ بعد كتابة هذه الدالة، لا مراجعةٌ ولا `tsc`.
        #
        # و`or 0`: الأعمدةُ `server_default="0"` فكلُّ صفٍّ يحملها، والحارسُ
        # هنا لصفٍّ قديمٍ في قاعدةٍ رُقّيت ولم تُملأ حقولُه بعد
        stop_fee=round_money(rule.stop_fee or Decimal(0)),
        stop_free_minutes=rule.stop_free_minutes or 0,
        stop_price_per_min=round_money(rule.stop_price_per_min or Decimal(0)),
        stop_max_wait_minutes=rule.stop_max_wait_minutes or 0,
    )


def waiting_minutes(stop: "RideStop", now: datetime) -> Decimal:
    """دقائقُ الانتظار عند محطة — من ختمَي الخلفية لا من مؤقت الواجهة.

    و**المحطةُ التي لم تُستأنف بعد تُقاس حتى الآن**: بها يمشي العدّاد الذي
    يراه الراكب، وبها يُحسب ما استحقّ حتى هذه اللحظة.
    """
    if stop.arrived_at is None:
        return Decimal(0)
    until = stop.resumed_at or now
    seconds = Decimal(str((until - stop.arrived_at).total_seconds()))
    if seconds <= 0:
        return Decimal(0)
    return seconds / 60


def waiting_charge(
    stops: "Sequence[RideStop]",
    *,
    free_minutes: int,
    price_per_min: Decimal,
    now: datetime,
) -> Decimal:
    """رسمُ الانتظار على محطات رحلةٍ — **بالمعدلات المجمَّدة عليها**.

    المهلةُ المجانية **لكل محطة** لا للرحلة: من وقف دقيقتين عند اثنتين لم
    ينتظر أحداً أربع دقائق، وجمعُ المهل يعاقبه على تقسيم طريقه.

    ولا سقفَ على المحتسَب: سقفُ الانتظار (`stop_max_wait_minutes`) حدُّ صبرٍ
    يُنبَّه عنده ويُفتح للكبتن مخرج، لا حدُّ فاتورة (SPEC القسم 5.10).
    """
    if price_per_min <= 0:
        return Decimal("0.000")

    billable = Decimal(0)
    for stop in stops:
        over = waiting_minutes(stop, now) - free_minutes
        if over > 0:
            billable += over
    return round_money(billable * price_per_min)
