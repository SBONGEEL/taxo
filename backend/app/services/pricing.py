"""تسعير الرحلة — في الخلفية حصراً (SPEC القسم 5).

    estimated_fare = base_fare + (km × price_per_km) + (min × price_per_min)
                     + (عدد المحطات الوسيطة × stop_fee)

بحدٍّ أدنى `minimum_fare`. كل الحساب بـ Decimal: مبالغ NUMERIC(12,3) لا float.

**ورسمُ الانتظار خارج التقدير عمداً** (المرحلة 12-ب، SPEC القسم 5.10): لا
يُعرف قبل أن يقع، فيُضاف إلى `final_fare` عند الإنهاء. والشاشةُ تقول سعرَه
قبل الطلب فيكون **معلوماً** ولو لم يكن مقدَّراً.
"""

from __future__ import annotations

import uuid
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
    from app.services.hourly import HourlyTerms
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
    # **تفصيلُ الأجرة سطراً سطراً** (R10، §٦٢-ج/٢٥) — من الحساب نفسِه، فمجموعُه `fare` حرفاً
    lines: tuple["FareLine", ...] = ()
    # **رسومُ الكبتن داخل `fare`** (§٦٣-ج/٢) — والمرفقُ الذي جاءت منه. **وصفرٌ و`None` بلا رسم**
    captain_fees: Decimal = Decimal("0.000")
    facility_id: "uuid.UUID | None" = None


@dataclass(frozen=True, slots=True)
class FareLine:
    """سطرٌ من تفصيل الأجرة — **يُحسب حيث يُحسب المبلغ** (`fare_breakdown`) فلا يفترقان (§١٤: المالُ في الخلفية).

    `kind`: `base` · `distance` · `time` · `stops` · `minimum` · `waiting` · `pause` — **و`rounding`** يكتبه `rounding.apply_to_ride`
    عند الإنهاء وحدَه (SPEC §٧٠-ج/٤)، موجباً أو سالباً. و`quantity` كيلومتراتٌ أو دقائقُ أو عددٌ
    **لتسمية السطر وحدَها** («المسافة · 6.8 كم») — **لا يُضرب في الشاشة**؛ المبلغُ هو `amount`.
    """

    kind: str
    amount: Decimal
    quantity: Decimal | None = None

    def as_json(self) -> dict[str, str]:
        out = {"kind": self.kind, "amount": str(self.amount)}
        if self.quantity is not None:
            out["quantity"] = str(self.quantity)
        return out


def lines_json(lines: Sequence[FareLine]) -> list[dict[str, str]]:
    """للتجميد على الرحلة (`rides.fare_lines`، JSONB) — **نصوصٌ لا أعداد**، فلا تقريبَ يمرّ بـfloat."""
    return [line.as_json() for line in lines]


def round_money(amount: Decimal) -> Decimal:
    return amount.quantize(MONEY_STEP, rounding=ROUND_HALF_UP)


def fare_breakdown(
    rule: PricingRule, route: Route, stops_count: int = 0
) -> tuple[Decimal, bool, list[FareLine]]:
    """السعرُ، وهل جبره الحدُّ الأدنى، **وأسطرُه** — حسابٌ واحدٌ لثلاثتها.

    **والأسطرُ تُجمع إلى السعر حرفاً**: التقريبُ في السعر مرّةٌ واحدةٌ على المجموع (لا على كلِّ حدّ)، والأسطرُ يُقرَّب كلٌّ منها —
    **فالفرقُ بين الطريقين (لا يتجاوز جزءاً من الألف لكلِّ حدٍّ مقرَّب) يُحمَل على أكبر سطرٍ متغيّر** (المسافة غالباً). ولا يُعرض سطرٌ
    قيمتُه صفر. **وجبرُ الحدّ الأدنى سطرٌ بنفسه** («تكملة الحدّ الأدنى») لا تعديلٌ صامتٌ في غيره.
    """
    # `rule.stop_fee or 0`: العمودُ `server_default="0"` فكلُّ صفٍّ في القاعدة
    # يحمل قيمة، أما صفٌّ بُني في الذاكرة ولم يُفلَش بعد فحقلُه `None` —
    # والأجرةُ لا يجوز أن تتعلق بلحظة الفلش
    stop_fee = rule.stop_fee or Decimal(0)
    raw = [
        ("base", rule.base_fare, None),
        ("distance", route.distance_km * rule.price_per_km, route.distance_km),
        ("time", route.duration_min * rule.price_per_min, route.duration_min),
        ("stops", stop_fee * stops_count, Decimal(stops_count) if stops_count else None),
    ]
    fare = round_money(sum((amount for _, amount, _ in raw), Decimal(0)))

    lines = [FareLine(kind, round_money(amount), quantity) for kind, amount, quantity in raw if amount != 0]
    residual = fare - sum((line.amount for line in lines), Decimal(0))
    if residual and lines:
        variable = [i for i, line in enumerate(lines) if line.kind in ("distance", "time")] or list(range(len(lines)))
        target = max(variable, key=lambda i: lines[i].amount)
        line = lines[target]
        lines[target] = FareLine(line.kind, line.amount + residual, line.quantity)

    minimum = round_money(rule.minimum_fare)
    if fare < minimum:
        lines.append(FareLine("minimum", minimum - fare))
        return minimum, True, lines
    return fare, False, lines


def calculate_fare(
    rule: PricingRule, route: Route, stops_count: int = 0
) -> tuple[Decimal, bool]:
    """السعر وهل جبره الحد الأدنى.

    و`stops_count` عددُ المحطات **الوسيطة**: رسمُها المقطوع يدخل التقدير
    المعروض قبل الطلب، بخلاف رسم الانتظار الذي لا يُعرف إلا بعد وقوعه.
    **والحسابُ نفسُه في `fare_breakdown`** — فلا يفترق السعرُ عن تفصيله.
    """
    fare, minimum_applied, _ = fare_breakdown(rule, route, stops_count)
    return fare, minimum_applied


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
    parcel: bool = False,
    parcel_fetch: bool = False,
    hourly: "HourlyTerms | None" = None,
) -> FareEstimate:
    """تسعيرة الدولة + مسار Mapbox → سعر مقدّر.

    تُستدعى مرتين: لعرض التقدير للراكب، ثم مجدداً عند إنشاء الرحلة — فالسعر
    المخزَّن يُحسب في الخلفية ولا يُقبل من العميل أبداً.

    و`stops` المحطاتُ الوسيطة بترتيبها: تدخل **المسارَ** (فالمسافة والمدة
    مسافةُ الطريق كلِّه ومدتُه) و**الرسمَ المقطوع** معاً.
    """
    rule = await get_rule(session, country_code, vehicle_category)
    # **بالساعة سعرُها ساعاتٌ لا طريق** (§٦٣-ج/٥) — فلا نداءَ مسارٍ يُدفع ثمنُه، والمدّةُ ساعاتُها
    if hourly is not None:
        from app.services import hourly as hourly_service

        route = Route(distance_km=Decimal("0.000"), duration_min=Decimal(hourly.hours * 60))
        line = hourly_service.booked_line(hourly.hours, hourly.rate)
        fare, minimum_applied, lines = line.amount, False, [line]
    else:
        route = await route_between(session, pickup, dropoff, country_code, stops=stops)
        fare, minimum_applied, lines = fare_breakdown(rule, route, len(stops))

    # **رسمُ المطار يُحسب هنا وحدَه** (§٦٣-ج/٢) — بابُ التقدير هو بابُ الطلب، فما يُعرض هو ما يُطلب. **وبعد الحدّ الأدنى**:
    # الحدُّ حدُّ أجرة طريق، ورسمٌ يُبتلع فيه رسمٌ لا يصل صاحبَه
    from app.services import facilities

    facility = await facilities.fee_for(
        session, country_code=country_code, pickup=pickup, dropoff=dropoff
    )
    captain_fees = round_money(facility.fee if facility is not None else Decimal(0))
    if captain_fees > 0:
        fare = round_money(fare + captain_fees)
        lines = [*lines, FareLine("airport_fee", captain_fees)]
    # **ورسمُ الطرد بالطريقة نفسِها** (§٦٣-ج/٤) — سطرٌ ثانٍ، ويُجمع إلى رسوم الكبتن: طردٌ إلى المطار يحمل الرسمين
    if parcel:
        from app.services import parcels

        # **و«أحضر غرضي» برسمه هو** (§٧٢-ج/١) — والسطرُ سطرُ الطرد نفسُه: رسمٌ للكبتن خارجَ العمولة والخصم
        parcel_fee = await parcels.fee_for(session, country_code, fetch=parcel_fetch)
        if parcel_fee > 0:
            fare = round_money(fare + parcel_fee)
            captain_fees = round_money(captain_fees + parcel_fee)
            lines = [*lines, FareLine("parcel_fee", parcel_fee)]

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
        lines=tuple(lines),
        captain_fees=captain_fees,
        facility_id=facility.id if facility is not None and captain_fees > 0 else None,
    )


def discountable(fare: Decimal, captain_fees: Decimal) -> Decimal:
    """**وعاءُ الخصم: الأجرةُ دون رسوم الكبتن** (§٦٣-ب) — الرسمُ «للكبتن» يصله كاملاً، فلا يُخصم منه."""
    return round_money(max(fare - captain_fees, Decimal(0)))


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
