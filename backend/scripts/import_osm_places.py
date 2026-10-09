"""**استيرادُ أماكن الأردن من OpenStreetMap** (أمرُ المالك ٢٠٢٦-١٠-٠٩، SPEC §٧١-ح/٤) — من ملفٍّ JSON جُلب من Overpass وراجعه النموذج.

    python -m scripts.import_osm_places /tmp/osm_jo.json            # يعدّ ويطبع ولا يكتب
    python -m scripts.import_osm_places /tmp/osm_jo.json --apply    # يكتب ما لم يُستورد قبلُ

**المواقعُ كما في OSM حرفاً** — نقطةُ العقدة، أو مركزُ الطريق/العلاقة كما يعطيه Overpass (`out center`) — **ولا تقريبَ ولا تعديل**.
**وكلُّ صفٍّ `source = osm` وأصلُه في `osm_ref`** فيراجعه المالكُ ويعدّله ويخفيه من «الأماكن». **وidempotent**: ما وُجد أصلُه لا يُكتب ثانيةً —
فتعديلُ المالك لا يُمحى باستيرادٍ لاحق. **وقيدُ تدقيقٍ واحدٌ** بالأعداد (بلا فاعل: إنسانٌ شغّل سكربتاً بأمر المالك).

**والرخصة**: © OpenStreetMap contributors — ODbL 1.0. الإسنادُ في صفحة «الأماكن» وفي خريطة المزوّد، **والقاعدةُ لا تُوزَّع** (نتائجُ بحثٍ تُعرض لا ملفٌّ يُنشر).

**ويطبع العددَ لكلِّ مدينة** — بأقرب مدينةٍ أو بلدةٍ في الملفّ نفسِه (`place=city|town`) — كما طلب المالكُ في التقرير.
"""

from __future__ import annotations

import asyncio
import json
import math
import sys
from collections import Counter

from sqlalchemy import select

from app.core.db import SessionLocal, engine
from app.models.enums import AuditAction, CountryCode, MapPlaceCategory
from app.models.map_place import SOURCE_OSM, MapPlace
from app.services import audit

APPLY = "--apply" in sys.argv
REASON = "بأمر المالك — SPEC §71-ح/4 (2026-10-09)، استيرادٌ من OpenStreetMap (ODbL)"
#: حدودُ الأردن تقريباً — **فحصُ سلامةٍ لا تعديل**: نقطةٌ خارجها تُرفض ولا تُكتب
JO_BOX = (29.0, 33.5, 34.8, 39.4)


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    d = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    return 12_742 * math.asin(math.sqrt(d))


async def main(path: str) -> int:
    data = json.load(open(path, encoding="utf-8"))
    places = data["places"]
    # **مراكزُ المحافظات الاثنتي عشرة** — ضواحي عمّان (`place=town` كالجبيهة ودابوق) تُعدّ لعمّان، والكركُ مدينتُها ولو وُسمت بلدة.
    # **للعدّ في التقرير وحدَه** — لا يُكتب في الصفّ
    capitals = {"عمان", "عمّان", "إربد", "اربد", "الزرقاء", "السلط", "المفرق", "جرش", "عجلون", "مادبا", "الكرك", "الطفيلة", "معان", "العقبة"}
    named = [c for c in data["cities"] if c.get("name_ar")]
    cities = [c for c in named if c["name_ar"] in capitals] or named
    allowed = {c.value for c in MapPlaceCategory}
    bad = [p for p in places if p["category"] not in allowed or not (JO_BOX[0] <= p["lat"] <= JO_BOX[1] and JO_BOX[2] <= p["lng"] <= JO_BOX[3])]
    if bad:
        print(f"✗ {len(bad)} صفّاً بفئةٍ غيرِ معروفةٍ أو خارج الأردن — **يقف ولا يكتب**: {bad[:3]}")
        return 1

    def city_of(place: dict) -> str:
        if not cities:
            return "؟"
        nearest = min(cities, key=lambda c: _km((place["lat"], place["lng"]), (c["lat"], c["lng"])))
        return nearest["name_ar"]

    async with SessionLocal() as session:
        have = set((await session.scalars(select(MapPlace.osm_ref).where(MapPlace.osm_ref.is_not(None)))).all())
        fresh = [p for p in places if p["osm_ref"] not in have]
        per_category = Counter(p["category"] for p in fresh)
        per_city = Counter(city_of(p) for p in fresh)
        print(f"  في الملفّ {len(places)} · مستوردٌ قبلُ {len(places) - len(fresh)} · جديد {len(fresh)} · بلا اسمٍ عربيّ (لم يُجلب) {data.get('skipped_no_ar')}")
        print("  بالفئة:", dict(per_category.most_common()))
        print("  بالمدينة:", dict(per_city.most_common()))
        if not APPLY:
            print("· لم يُكتب شيء — أعد بـ--apply")
            await engine.dispose()
            return 0
        for p in fresh:
            session.add(MapPlace(
                country_code=CountryCode.JO, name_ar=p["name_ar"], name_en=p.get("name_en"), category=p["category"],
                lat=p["lat"], lng=p["lng"], source=SOURCE_OSM, osm_ref=p["osm_ref"],
            ))
        await audit.record(
            session, actor=None, action=AuditAction.CREATE, entity_type="map_place_import",  # type: ignore[arg-type]
            details={"reason": REASON, "count": len(fresh), "per_category": dict(per_category), "per_city": dict(per_city),
                     "attribution": data.get("attribution"), "fetched": data.get("fetched")},
        )
        await session.commit()
        print(f"✓ استُورد {len(fresh)} مكاناً")
    await engine.dispose()
    return 0


sys.exit(asyncio.run(main(sys.argv[1])))
