"""المرافقُ الحيويّة ورسمُ المطار (SPEC §٦٣-ج/٢) — **مطفأةٌ لكلِّ سوقٍ حتى يُشعلها المالك**.

**بابٌ واحدٌ يقرّر الرسم** (`fee_for`) ويُنادى من `pricing.estimate` وحدَه — **فالتقديرُ والطلبُ يحسبانه بالحساب نفسِه**،
ولا يُعرض للراكب رسمٌ ثمّ يُطلب غيرُه. **والرسمُ يُجمَّد على الرحلة لحظةَ إنشائها** (`rides.captain_fees_at_ride`)، فتعديلُ
المشرف يحكم ما يأتي لا رحلةً سائرة.

**والمضلّعُ يُكتب ويُقرأ بترتيب GeoJSON** (`[[lng, lat], …]`) كخطوط المسار في هذا المشروع — **والحلقةُ تُغلق هنا** لا في
الواجهة: لوحةٌ ترسل ثلاثَ نقاطٍ تُكمَّل برابعةٍ تساوي الأولى، ومضلّعٌ لا يصحّ (`ST_IsValid`) يُرفض باسمه.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInput, NotFound
from app.models.enums import CountryCode, FeatureKey
from app.models.facility import FACILITY_AIRPORT, Facility
from app.models.ride import make_point
from app.services import settings_service
from app.services.directions import Coordinates

#: **أقلُّ مضلّعٍ ثلاثُ نقاط**، وأكثرُه ما يرسمه إنسانٌ بنقراتٍ لا ما يُلصق من ملفّ — سقفٌ يمنع حمولةً لا تُرسم
MAX_VERTICES = 200


async def fee_for(
    session: AsyncSession,
    *,
    country_code: CountryCode,
    pickup: Coordinates,
    dropoff: Coordinates,
) -> Facility | None:
    """المطارُ الذي تبدأ فيه الرحلةُ أو تنتهي — **في سوقٍ أشعل مفتاحَه، ومرفقٍ مفعَّلٍ رسمُه موجب**؛ وإلا `None`.

    **وإن مسّت مرفقين فرسمٌ واحدٌ، أكبرُهما**: الرسمُ مقابلُ رحلةٍ إلى مطارٍ أو منه، لا لكلِّ مطارٍ تمرّ به.
    """
    if not await settings_service.is_feature_enabled(
        session, country_code, FeatureKey.AIRPORT_ENABLED
    ):
        return None
    start = make_point(pickup.lat, pickup.lng)
    end = make_point(dropoff.lat, dropoff.lng)
    return await session.scalar(
        select(Facility)
        .where(
            Facility.country_code == country_code,
            Facility.kind == FACILITY_AIRPORT,
            Facility.is_active.is_(True),
            Facility.fee > 0,
            or_(func.ST_Covers(Facility.area, start), func.ST_Covers(Facility.area, end)),
        )
        .order_by(Facility.fee.desc())
        .limit(1)
    )


# ------------------------------------------------------------------ اللوحة


def _ring_wkt(points: list[list[float]]) -> str:
    if len(points) < 3:
        raise InvalidInput("المنطقةُ ثلاثُ نقاطٍ على الأقل")
    if len(points) > MAX_VERTICES:
        raise InvalidInput(f"أكثرُ ما تُرسم به المنطقة {MAX_VERTICES} نقطة")
    ring = [list(map(float, point)) for point in points]
    for lng, lat in ring:
        if not (-180 <= lng <= 180 and -90 <= lat <= 90):
            raise InvalidInput("نقطةٌ خارج الخريطة")
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    if len(ring) < 4:
        raise InvalidInput("المنطقةُ ثلاثُ نقاطٍ مختلفةٍ على الأقل")
    return "SRID=4326;POLYGON((" + ", ".join(f"{lng} {lat}" for lng, lat in ring) + "))"


async def _valid_area(session: AsyncSession, points: list[list[float]]) -> str:
    wkt = _ring_wkt(points)
    ok = await session.scalar(select(func.ST_IsValid(func.ST_GeomFromEWKT(wkt))))
    if not ok:
        raise InvalidInput("المنطقةُ تتقاطع مع نفسها — ارسمها بلا تقاطع")
    return wkt


async def area_points(session: AsyncSession, facility: Facility) -> list[list[float]]:
    """المضلّعُ كما يُرسم: `[[lng, lat], …]` بلا النقطة المكرَّرة في آخره."""
    geojson = await session.scalar(select(func.ST_AsGeoJSON(Facility.area)).where(Facility.id == facility.id))
    ring = json.loads(geojson)["coordinates"][0]
    return [[round(lng, 6), round(lat, 6)] for lng, lat in ring[:-1]]


async def list_for(session: AsyncSession, *, country: CountryCode | None) -> list[Facility]:
    query = select(Facility).order_by(Facility.country_code, Facility.name)
    if country is not None:
        query = query.where(Facility.country_code == country)
    return list(await session.scalars(query))


async def airports_for_rider(session: AsyncSession, *, country: CountryCode) -> list[tuple[uuid.UUID, str, float, float]]:
    """**مطاراتُ سوق الراكب ليختارها وجهةً** (§٦٣-ج/٢): اسمٌ ونقطةٌ **داخل** المضلّع (`ST_PointOnSurface` لا المركز — مركزُ مضلّعٍ
    مقعّرٍ قد يقع خارجه فلا يُحسب الرسم). **والمطفأُ لا يُعرض**، ولا الرسمُ ولا المضلّعُ نفسُه: ما يحتاجه الراكبُ وجهةٌ لا حدود."""
    point = func.ST_PointOnSurface(func.geometry(Facility.area))
    rows = await session.execute(
        select(Facility.id, Facility.name, func.ST_Y(point), func.ST_X(point))
        .where(
            Facility.country_code == country,
            Facility.kind == FACILITY_AIRPORT,
            Facility.is_active.is_(True),
        )
        .order_by(Facility.name)
    )
    return [(row[0], row[1], float(row[2]), float(row[3])) for row in rows.all()]


async def get(session: AsyncSession, facility_id: uuid.UUID) -> Facility:
    row = await session.get(Facility, facility_id)
    if row is None:
        raise NotFound("المرفق غير موجود")
    return row


async def create(
    session: AsyncSession,
    *,
    country_code: CountryCode,
    name: str,
    area: list[list[float]],
    fee: Decimal,
    is_active: bool,
) -> Facility:
    row = Facility(
        country_code=country_code,
        kind=FACILITY_AIRPORT,
        name=" ".join(name.split()),
        area=await _valid_area(session, area),
        fee=fee,
        is_active=is_active,
    )
    session.add(row)
    await session.flush()
    return row


async def update(
    session: AsyncSession,
    facility: Facility,
    *,
    name: str | None = None,
    area: list[list[float]] | None = None,
    fee: Decimal | None = None,
    is_active: bool | None = None,
) -> dict[str, object]:
    """يعيد ما تغيّر — **للتدقيق**، والمضلّعُ يُذكر تغيّرُه لا نقاطُه."""
    changed: dict[str, object] = {}
    if name is not None and " ".join(name.split()) != facility.name:
        facility.name = " ".join(name.split())
        changed["name"] = facility.name
    if area is not None:
        facility.area = await _valid_area(session, area)
        changed["area"] = f"{len(area)} نقطة"
    if fee is not None and fee != facility.fee:
        changed["fee"] = {"from": str(facility.fee), "to": str(fee)}
        facility.fee = fee
    if is_active is not None and is_active != facility.is_active:
        facility.is_active = is_active
        changed["is_active"] = is_active
    await session.flush()
    return changed
