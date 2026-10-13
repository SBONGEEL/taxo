"""مناطقُ التسعير — **البيتُ الواحد** (SPEC §٧٤-أ/٥): أيُّ منطقةٍ تحكم الرحلة، وكم تزيد، وإدارتُها من اللوحة.

**ولايةُ الانطلاق تحكم** — تُسأل القاعدةُ (`ST_Covers` على نقطة الالتقاء) كما تُسأل عن المطار. **وغيرُ الموسومة «وعرة» لا أثرَ لها**،
فالسعرُ الموحَّدُ لكلِّ الولايات يبقى كما هو حرفاً.

**والأثرُ سطرٌ واحدٌ في تفصيل الأجرة** (`rugged` — «تسعيرة المناطق الوعرة»):
- **بالنسبة**: أجرةُ الطريق (بعد الحدّ الأدنى، قبل رسوم الكبتن) × النسبة؛
- **بالجدول**: فرقُ أجرة الطريق بجدول المنطقة عن أجرته بتسعيرة الدولة — **فأسطرُ الطريق تبقى بتسعيرة الدولة ويظهر الفرقُ سطراً**، ومجموعُ
  الأسطر هو السعرُ حرفاً (§١٤).

**ويُحسب قبل التقريب** (§٧٠): التقريبُ على ما يدفعه الراكبُ في النهاية، والسطرُ جزءٌ ممّا يُقرَّب. **ورسومُ الكبتن لا تُزاد** (المطار والطرد):
رسمٌ للكبتن لا سعرُ رحلة.

**ولا قفلَ هنا**: قراءةٌ وتعديلُ إعداد — لا مالَ يتحرّك ولا حالَ صفٍّ تتنازعه طلبات.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.exceptions import InvalidInput, NotFound
from app.models.enums import AuditAction, CountryCode
from app.models.pricing import PricingRule
from app.models.pricing_zone import ZONE_MODE_PERCENT, ZONE_MODE_TABLE, PricingZone, ZonePricingRule
from app.models.ride import make_point
from app.models.user import User
from app.services import audit

#: **ملفّاتُ الحدود في الشجرة** — منها يُحمَّل كلُّ سوق (`scripts/load_pricing_zones.py`)، ولا تُكتب بيد
ZONES_DIR = Path(__file__).resolve().parents[1] / "data" / "zones"


@dataclass(frozen=True, slots=True)
class ZoneEffect:
    zone_id: uuid.UUID
    #: **ما يُضاف إلى أجرة الطريق** — موجبٌ أو صفر، بخانات العملة
    amount: Decimal
    #: أجرةُ الطريق بعد المنطقة (بالجدول تحلّ محلَّ أجرة الدولة)
    fare: Decimal


async def zone_at(session: AsyncSession, country: CountryCode, lat: float, lng: float) -> PricingZone | None:
    """**المنطقةُ التي تقع فيها النقطة** في سوقها — `None` خارج كلِّ منطقة (سوقٌ بلا مناطق، أو نقطةٌ على البحر)."""
    return await session.scalar(
        select(PricingZone)
        .where(PricingZone.country_code == country, func.ST_Covers(PricingZone.area, make_point(lat, lng)))
        .order_by(PricingZone.code)
        .limit(1)
    )


async def _zone_rule(session: AsyncSession, zone_id: uuid.UUID, category: str) -> ZonePricingRule | None:
    return await session.scalar(
        select(ZonePricingRule).where(ZonePricingRule.zone_id == zone_id, ZonePricingRule.vehicle_category == str(category))
    )


def _as_rule(country: CountryCode, base: PricingRule, row: ZonePricingRule) -> PricingRule:
    """**تسعيرةُ الدولة بمعدّلات المنطقة الأربعة** — وما سواها (المحطات والانتظار والوقفات) من تسعيرة الدولة كما هو."""
    return PricingRule(
        country_code=country,
        vehicle_category=base.vehicle_category,
        base_fare=row.base_fare,
        price_per_km=row.price_per_km,
        price_per_min=row.price_per_min,
        minimum_fare=row.minimum_fare,
        cancellation_fee=base.cancellation_fee,
        stop_fee=base.stop_fee,
        stop_free_minutes=base.stop_free_minutes,
        stop_price_per_min=base.stop_price_per_min,
        stop_max_wait_minutes=base.stop_max_wait_minutes,
        pause_price_per_min=base.pause_price_per_min,
        arrival_free_minutes=base.arrival_free_minutes,
        pause_max_minutes=base.pause_max_minutes,
    )


async def effect_for(
    session: AsyncSession,
    *,
    country: CountryCode,
    rule: PricingRule,
    pickup_lat: float,
    pickup_lng: float,
    road_fare: Decimal,
    route=None,
    stops_count: int = 0,
    zone_id: uuid.UUID | None = None,
) -> ZoneEffect | None:
    """**أثرُ منطقة الانطلاق على أجرة الطريق** — `None` حيث لا منطقةَ وعرة.

    و`zone_id` حين يُعاد الحسابُ عند الإنهاء (انحرافُ الطريق): المنطقةُ التي جُمِّدت على الرحلة لا التي يقع فيها الطرفُ الآن.
    """
    from app.services import pricing

    zone = await session.get(PricingZone, zone_id) if zone_id else await zone_at(session, country, pickup_lat, pickup_lng)
    if zone is None or not zone.rugged:
        return None
    currency = currency_for_country(country)
    fare = road_fare
    if zone.adjustment_mode == ZONE_MODE_TABLE and route is not None:
        row = await _zone_rule(session, zone.id, rule.vehicle_category)
        if row is not None:
            fare, _, _ = pricing.fare_breakdown(_as_rule(country, rule, row), route, stops_count)
    elif zone.adjustment_mode == ZONE_MODE_PERCENT:
        fare = pricing.round_money(road_fare + road_fare * zone.adjustment_percent / Decimal(100), currency)
    amount = pricing.round_money(fare - road_fare, currency)
    if amount <= 0:
        return None
    return ZoneEffect(zone_id=zone.id, amount=amount, fare=fare)


# ------------------------------------------------------------------ اللوحة


async def list_for(session: AsyncSession, country: CountryCode) -> list[PricingZone]:
    return list((await session.scalars(select(PricingZone).where(PricingZone.country_code == country).order_by(PricingZone.code))).all())


async def rules_for(session: AsyncSession, zone_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[ZonePricingRule]]:
    out: dict[uuid.UUID, list[ZonePricingRule]] = {zone_id: [] for zone_id in zone_ids}
    if not zone_ids:
        return out
    for row in await session.scalars(select(ZonePricingRule).where(ZonePricingRule.zone_id.in_(zone_ids))):
        out[row.zone_id].append(row)
    return out


async def geojson_for(session: AsyncSession, country: CountryCode) -> dict:
    """**حدودُ المناطق للخريطة** — مبسَّطةً من القاعدة نفسِها، وحالُ كلٍّ في خصائصها."""
    rows = await session.execute(
        select(
            PricingZone.id,
            PricingZone.code,
            PricingZone.name_ar,
            PricingZone.rugged,
            func.ST_AsGeoJSON(PricingZone.area, 4),
        )
        .where(PricingZone.country_code == country)
        .order_by(PricingZone.code)
    )
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": str(zone_id), "code": code, "name": name, "rugged": rugged},
                "geometry": json.loads(geo),
            }
            for zone_id, code, name, rugged, geo in rows
        ],
    }


async def get(session: AsyncSession, zone_id: uuid.UUID) -> PricingZone:
    zone = await session.get(PricingZone, zone_id)
    if zone is None:
        raise NotFound("لا منطقةَ بهذا المعرّف")
    return zone


async def update(
    session: AsyncSession,
    *,
    zone: PricingZone,
    actor: User,
    rugged: bool | None = None,
    adjustment_mode: str | None = None,
    adjustment_percent: Decimal | None = None,
) -> PricingZone:
    changes: dict[str, dict] = {}
    if adjustment_mode is not None and adjustment_mode not in (ZONE_MODE_PERCENT, ZONE_MODE_TABLE):
        raise InvalidInput("وجهُ التعديل نسبةٌ أو جدول")
    for field, value in (("rugged", rugged), ("adjustment_mode", adjustment_mode), ("adjustment_percent", adjustment_percent)):
        if value is not None and getattr(zone, field) != value:
            changes[field] = {"from": str(getattr(zone, field)), "to": str(value)}
            setattr(zone, field, value)
    if changes:
        zone.updated_by = actor.id
        await audit.record(
            session,
            actor=actor,
            action=AuditAction.UPDATE,
            entity_type="pricing_zone",
            entity_id=zone.id,
            details={"country_code": CountryCode(zone.country_code).value, "code": zone.code, "changes": changes},
        )
    await session.flush()
    return zone


async def set_rule(
    session: AsyncSession,
    *,
    zone: PricingZone,
    category: str,
    base_fare: Decimal,
    price_per_km: Decimal,
    price_per_min: Decimal,
    minimum_fare: Decimal,
    actor: User,
) -> ZonePricingRule:
    row = await _zone_rule(session, zone.id, category)
    values = {"base_fare": base_fare, "price_per_km": price_per_km, "price_per_min": price_per_min, "minimum_fare": minimum_fare}
    if row is None:
        row = ZonePricingRule(zone_id=zone.id, vehicle_category=str(category), **values)
        session.add(row)
        action = AuditAction.CREATE
    else:
        for key, value in values.items():
            setattr(row, key, value)
        action = AuditAction.UPDATE
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action=action,
        entity_type="zone_pricing_rule",
        entity_id=row.id,
        details={"zone": zone.code, "country_code": CountryCode(zone.country_code).value, "category": str(category)},
    )
    return row


# ------------------------------------------------------------------ التحميل


async def load_country(session: AsyncSession, country: CountryCode, *, rugged_codes: dict[str, str] | None = None) -> dict:
    """**يحمّل مناطقَ سوقٍ من ملفّه في الشجرة** — إضافةً لما غاب **وتحديثاً لحدود ما وُجد**، **ولا يمسّ وسمَ «وعرة» ولا نسبتَه ولا جدولَه**
    فيما وُجد (قرارُ المالك لا يُمحى بإعادة تحميل). و`rugged_codes` (الرمز ⇒ العلّة) يُوسَم به **الجديدُ وحدَه** — قائمةٌ مقترحةٌ أولى.
    """
    path = ZONES_DIR / f"{country.value}.geojson"
    data = json.loads(path.read_text(encoding="utf-8"))
    existing = {zone.code: zone for zone in await list_for(session, country)}
    added = updated = 0
    for feature in data["features"]:
        props = feature["properties"]
        geo = json.dumps(feature["geometry"])
        area = func.Geography(func.ST_Multi(func.ST_SetSRID(func.ST_GeomFromGeoJSON(geo), 4326)))
        merged = props.get("includes_new") or []
        note = (
            "تضمّ حتى بدء عمل الولايات الجديدة (2027-01-01): " + "، ".join(f"{m['name_ar']} ({m['code']})" for m in merged)
            if merged
            else None
        )
        zone = existing.get(props["code"])
        if zone is None:
            reason = (rugged_codes or {}).get(props["code"])
            session.add(
                PricingZone(
                    country_code=country,
                    code=props["code"],
                    name_ar=props["name_ar"],
                    name_fr=props.get("name_fr"),
                    note=note,
                    area=area,
                    rugged=reason is not None,
                )
            )
            added += 1
        else:
            zone.area = area
            zone.name_ar = props["name_ar"]
            zone.name_fr = props.get("name_fr")
            zone.note = note
            updated += 1
    await session.flush()
    return {"added": added, "updated": updated, "attribution": data.get("attribution")}
