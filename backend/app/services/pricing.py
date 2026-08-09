"""تسعير الرحلة — في الخلفية حصراً (SPEC القسم 5).

    estimated_fare = base_fare + (km × price_per_km) + (min × price_per_min)

بحدٍّ أدنى `minimum_fare`. كل الحساب بـ Decimal: مبالغ NUMERIC(12,3) لا float.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.exceptions import PricingRuleMissing
from app.models.enums import CountryCode, Currency, VehicleCategory
from app.models.pricing import PricingRule
from app.services.directions import Coordinates, Route, route_between

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


def round_money(amount: Decimal) -> Decimal:
    return amount.quantize(MONEY_STEP, rounding=ROUND_HALF_UP)


def calculate_fare(rule: PricingRule, route: Route) -> tuple[Decimal, bool]:
    """السعر وهل جبره الحد الأدنى."""
    fare = (
        rule.base_fare
        + route.distance_km * rule.price_per_km
        + route.duration_min * rule.price_per_min
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
) -> FareEstimate:
    """تسعيرة الدولة + مسار Mapbox → سعر مقدّر.

    تُستدعى مرتين: لعرض التقدير للراكب، ثم مجدداً عند إنشاء الرحلة — فالسعر
    المخزَّن يُحسب في الخلفية ولا يُقبل من العميل أبداً.
    """
    rule = await get_rule(session, country_code, vehicle_category)
    route = await route_between(session, pickup, dropoff, country_code)
    fare, minimum_applied = calculate_fare(rule, route)

    return FareEstimate(
        country_code=CountryCode(country_code),
        vehicle_category=VehicleCategory(vehicle_category),
        currency=currency_for_country(country_code),
        route=route,
        fare=fare,
        minimum_fare_applied=minimum_applied,
    )
