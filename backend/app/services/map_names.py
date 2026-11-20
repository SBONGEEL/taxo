"""**«أماكن بلا اسم عربي»** (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-ب) — القائمةُ من `places-search` (`/missing-ar`، يبنيها
`arabic_names.py` خارج الإنتاج من OSM وOverture وWikidata وGeoNames)، **والاسمُ الذي يكتبه المشرف** في `map_name_fixes`.

* **ما كُتب له اسمٌ يخرج من القائمة** ويظهر في «ما كُتب» — فلا يُعرض مرّتين.
* **الاسمُ عربيٌّ خالص**: حرفٌ عربيٌّ ولا حرفَ لاتينيّاً. **ولا ترجمةَ آليّة**: المشرفُ يكتب.
* **والتطبيقان يرسمانه بمفتاح المكان** (`for_country`) فوق اسم المربّع.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInput, NotFound
from app.models.enums import CountryCode
from app.models.map_name_fix import MapNameFix

ARABIC = re.compile("[؀-ۿ]")
LATIN = re.compile("[A-Za-z]")
OKEY = re.compile(r"^[nwro][0-9A-Za-z_-]{1,38}$")
TIMEOUT = 8.0
#: **للاختبار** — `httpx.MockTransport` مكانَ الشبكة، كـ`maps.open_transport`
transport: httpx.AsyncBaseTransport | None = None


def clean_name(value: str) -> str:
    """**اسمٌ عربيٌّ خالص** — وإلا ٤٢٢ بسببه."""
    name = " ".join((value or "").split())
    if not name or len(name) > 120:
        raise InvalidInput("اكتب الاسمَ العربيَّ (حتى 120 حرفاً)")
    if not ARABIC.search(name) or LATIN.search(name):
        raise InvalidInput("الاسمُ بالعربيّة وحدَها — بلا أحرفٍ لاتينيّة")
    return name


def check_key(okey: str) -> str:
    if not OKEY.match(okey or ""):
        raise InvalidInput("مفتاحُ المكان غيرُ صالح")
    return okey


@dataclass(frozen=True)
class MissingPage:
    built: bool
    cities: list[dict]
    total: int
    items: list[dict]
    #: أعدادُ الفئات بترتيب الأهمّيّة (أمرُ المالك ٢٠٢٦-١١-٢٠ الثاني، البند ٤) — فارغةٌ من خدمةٍ أقدم
    cats: list[dict] = field(default_factory=list)


async def missing(
    session: AsyncSession, country: CountryCode, city: str, offset: int, limit: int, cat: str = ""
) -> MissingPage | None:
    """القائمةُ من الخدمة، **وما له اسمٌ مكتوبٌ يُطوى منها**. `None` ⇐ الخدمةُ لا تجيب."""
    from app.core.config import settings

    base = settings.places_search_url.rstrip("/")
    if not base:
        return None
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, transport=transport) as client:
            response = await client.get(
                f"{base}/missing-ar", params={"cc": country.value, "city": city, "cat": cat, "offset": offset, "limit": limit}
            )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    fixed = set((await session.scalars(select(MapNameFix.okey).where(MapNameFix.country_code == country))).all())
    items = [item for item in body.get("items") or [] if item.get("okey") not in fixed]
    return MissingPage(
        bool(body.get("built")), list(body.get("cities") or []), int(body.get("total") or 0), items, list(body.get("cats") or [])
    )


async def fixes(session: AsyncSession, country: CountryCode) -> list[MapNameFix]:
    return list(
        (await session.scalars(
            select(MapNameFix).where(MapNameFix.country_code == country).order_by(MapNameFix.updated_at.desc())
        )).all()
    )


async def for_country(session: AsyncSession, country: CountryCode) -> dict[str, str]:
    """**ما يرسمه التطبيقان** — مفتاحُ المكان ⇐ اسمُه العربيّ."""
    rows = await session.execute(select(MapNameFix.okey, MapNameFix.name_ar).where(MapNameFix.country_code == country))
    return {okey: name for okey, name in rows.all()}


async def put(
    session: AsyncSession, *, okey: str, country: CountryCode, name_ar: str, original_name: str, city: str,
    actor_id: uuid.UUID,
) -> tuple[MapNameFix, str | None]:
    """يكتب الاسم أو يغيّره، ويُرجع **الاسمَ السابق** للتدقيق (`None` ⇐ جديد)."""
    check_key(okey)
    name = clean_name(name_ar)
    # **إنشاءان متزامنان لا ينتهيان بـ٥٠٠**: الإدراجُ `ON CONFLICT DO NOTHING` ثمّ قفلُ الصفّ — فالثاني يقرأ ما كتبه الأوّل اسماً سابقاً
    created = await session.execute(
        pg_insert(MapNameFix)
        .values(okey=okey, country_code=country, name_ar=name, original_name=(original_name or "")[:120],
                city=(city or "")[:120], updated_by=actor_id)
        .on_conflict_do_nothing(index_elements=["okey"])
    )
    row = await session.get(MapNameFix, okey, with_for_update=True, populate_existing=True)
    assert row is not None
    if created.rowcount == 1:
        return row, None
    if row.country_code != country:
        raise InvalidInput("المكانُ في دولةٍ أخرى")
    previous = row.name_ar
    row.name_ar = name
    row.updated_by = actor_id
    await session.flush()
    return row, previous


async def remove(session: AsyncSession, okey: str) -> MapNameFix:
    row = await session.get(MapNameFix, check_key(okey), with_for_update=True)
    if row is None:
        raise NotFound("لا اسمَ مكتوباً لهذا المكان")
    await session.delete(row)
    await session.flush()
    return row
