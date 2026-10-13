"""«مناطق التسعير» (SPEC §٧٤-أ/٥) — المناطقُ بحدودها، ووسمُ «وعرة»، ونسبتُها أو جدولُها.

**القراءةُ لطاقم اللوحة، والكتابةُ `settings.write` كالتسعيرة** — وهي تسعيرةٌ: **فيمرّ كلُّ تعديلٍ بحارس الكتابة على التسعير**
(`money_guards.require_pricing_writes`)، فتجميدُ التسعير يجمّد المناطقَ معه.
"""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter

from app.core.deps import DbSession, SettingsWriter, StaffUser
from app.models.enums import CountryCode
from app.schemas.pricing_zones import PricingZoneOut, PricingZonesOut, PricingZoneUpdate, ZoneRuleIn, ZoneRuleOut
from app.services import categories, money_guards, pricing_zones

router = APIRouter(prefix="/admin/pricing-zones", tags=["admin"])


async def _out(session, country: CountryCode) -> PricingZonesOut:
    zones = await pricing_zones.list_for(session, country)
    rules = await pricing_zones.rules_for(session, [zone.id for zone in zones])
    path = pricing_zones.ZONES_DIR / f"{country.value}.geojson"
    attribution = json.loads(path.read_text(encoding="utf-8")).get("attribution") if path.exists() else None
    return PricingZonesOut(
        zones=[
            PricingZoneOut(
                id=zone.id,
                country_code=zone.country_code,
                code=zone.code,
                name_ar=zone.name_ar,
                name_fr=zone.name_fr,
                note=zone.note,
                rugged=zone.rugged,
                adjustment_mode=zone.adjustment_mode,
                adjustment_percent=zone.adjustment_percent,
                rules=[ZoneRuleOut.model_validate(rule) for rule in rules[zone.id]],
            )
            for zone in zones
        ],
        attribution=attribution,
    )


@router.get("", response_model=PricingZonesOut)
async def list_zones(country_code: CountryCode, session: DbSession, _: StaffUser) -> PricingZonesOut:
    return await _out(session, country_code)


@router.get("/map")
async def zones_map(country_code: CountryCode, session: DbSession, _: StaffUser) -> dict:
    """**الحدودُ للخريطة** — GeoJSON من القاعدة، وحالُ كلِّ منطقةٍ في خصائصها (`rugged`)."""
    return await pricing_zones.geojson_for(session, country_code)


@router.put("/{zone_id}", response_model=PricingZonesOut)
async def update_zone(zone_id: uuid.UUID, payload: PricingZoneUpdate, session: DbSession, admin: SettingsWriter) -> PricingZonesOut:
    zone = await pricing_zones.get(session, zone_id)
    await money_guards.require_pricing_writes(session, actor=admin, country_code=zone.country_code, entity_id=zone.id)
    await pricing_zones.update(
        session,
        zone=zone,
        actor=admin,
        rugged=payload.rugged,
        adjustment_mode=payload.adjustment_mode,
        adjustment_percent=payload.adjustment_percent,
    )
    await session.commit()
    return await _out(session, CountryCode(zone.country_code))


@router.put("/{zone_id}/rules/{vehicle_category}", response_model=PricingZonesOut)
async def set_zone_rule(
    zone_id: uuid.UUID, vehicle_category: str, payload: ZoneRuleIn, session: DbSession, admin: SettingsWriter
) -> PricingZonesOut:
    """**جدولُ أسعار المنطقة لفئة** — يحلّ محلَّ تسعيرة الدولة لها حين يكون وجهُ المنطقة «جدول»."""
    zone = await pricing_zones.get(session, zone_id)
    await money_guards.require_pricing_writes(session, actor=admin, country_code=zone.country_code, entity_id=zone.id)
    await categories.require_requestable(session, zone.country_code, vehicle_category)
    await pricing_zones.set_rule(
        session,
        zone=zone,
        category=vehicle_category,
        base_fare=payload.base_fare,
        price_per_km=payload.price_per_km,
        price_per_min=payload.price_per_min,
        minimum_fare=payload.minimum_fare,
        actor=admin,
    )
    await session.commit()
    return await _out(session, CountryCode(zone.country_code))
