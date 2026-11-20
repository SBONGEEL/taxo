"""Builds the open map layers from the same sources as places.sqlite. Runs OFF production (GitHub Actions, `map-data.yml`).

usage: python -I build_map_data.py <workdir>
  reads   <workdir>/places.sqlite             (build_index.py + postprocess.py — the SAME rows the search answers from)
          <workdir>/pbf/<country>.osm.pbf     (Geofabrik — roads, works/closures)
          <workdir>/buildings.geojsonl        (optional — Overture Buildings for the eight cities, from DuckDB in the workflow)
  writes  <workdir>/places-z<N>.geojsonl (N = تكبيرُ البدء 11..16)  works.geojsonl  roads.sqlite  stats.json

**أمرُ المالك ٢٠٢٦-١١-١٨ السابع، المهمّتان ٢ و٣** (`design/MAP-OPEN-DATA-TRAFFIC.md`):
- **الأماكنُ على الخريطة هي أماكنُ البحث نفسُها** — من `places.sqlite` لا من مصدرٍ ثانٍ يفترق عنه.
- **الاسمُ العربيُّ أوّلاً** ثمّ المحلّيّ ثمّ الفرنسيّ/الإنجليزيّ، **ولا اسمَ يُخترع**: ما لا اسمَ له لا يُرسم.
- **الكثافةُ بالتكبير**: أعلى الرتب تظهر أبعد، والصغيرُ لا يظهر إلا قريباً — فلا تزدحم.
- **مقاطعُ الطرق الرئيسيّة** للمطابقة (الازدحام): ≤ ١٢٠ م، بسرعةِ الطريق الحرّة من `maxspeed` أو من صنفه.
"""
import json
import math
import os
import re
import sqlite3
import sys
import time

import osmium

WORK = sys.argv[1]
COUNTRIES = {"jordan": "JO", "algeria": "DZ", "libya": "LY"}
ARABIC = re.compile(r"[؀-ۿ]")

# ── فئةُ المكان ⇐ أيقونته (الأسماءُ نفسُها في `customer-app/src/lib/open-places.ts`)
OSM_CATEGORY = [
    ("hospital", {"amenity=hospital", "healthcare=hospital"}),
    ("clinic", {"amenity=clinic", "amenity=doctors", "healthcare=clinic", "healthcare=doctor", "healthcare=centre", "amenity=dentist", "healthcare=dentist"}),
    ("pharmacy", {"amenity=pharmacy", "healthcare=pharmacy", "shop=chemist"}),
    ("university", {"amenity=university", "amenity=college"}),
    ("school", {"amenity=school", "amenity=kindergarten"}),
    ("mosque", {"amenity=place_of_worship"}),
    ("bank", {"amenity=bank", "amenity=atm", "amenity=bureau_de_change"}),
    ("government", {"office=government", "amenity=townhall", "amenity=courthouse", "amenity=police", "amenity=post_office", "amenity=embassy", "office=diplomatic", "amenity=fire_station"}),
    ("fuel", {"amenity=fuel", "amenity=charging_station"}),
    ("restaurant", {"amenity=restaurant", "amenity=fast_food", "amenity=food_court"}),
    ("cafe", {"amenity=cafe", "amenity=ice_cream", "shop=bakery", "shop=pastry"}),
    ("hotel", {"tourism=hotel", "tourism=motel", "tourism=guest_house", "tourism=hostel", "tourism=apartment"}),
    ("mall", {"shop=mall", "shop=department_store", "amenity=marketplace", "shop=supermarket"}),
    ("landmark", {"tourism=attraction", "tourism=museum", "historic=monument", "historic=memorial", "historic=castle", "historic=archaeological_site", "historic=ruins", "tourism=viewpoint", "leisure=stadium", "leisure=park", "aeroway=aerodrome", "aeroway=terminal"}),
    ("transport", {"amenity=bus_station", "public_transport=station", "railway=station", "amenity=taxi", "amenity=parking"}),
]
OSM_LOOKUP = {tag: cat for cat, tags in OSM_CATEGORY for tag in tags}
# Overture `categories.primary` ⇐ الفئة (كلماتٌ في الاسم الإنجليزيّ للفئة)
OVERTURE_WORDS = [
    ("hospital", ("hospital",)), ("pharmacy", ("pharmacy", "drugstore")),
    ("clinic", ("clinic", "doctor", "dentist", "medical", "health", "laboratory")),
    ("university", ("university", "college")), ("school", ("school", "kindergarten", "academy")),
    ("mosque", ("mosque", "religious", "church", "place_of_worship")), ("bank", ("bank", "atm", "currency")),
    ("government", ("government", "embassy", "police", "post_office", "court", "town_hall", "public_service", "municipal")),
    ("fuel", ("gas_station", "fuel", "ev_charging")), ("cafe", ("cafe", "coffee", "bakery", "dessert", "juice", "tea_room")),
    ("restaurant", ("restaurant", "food", "pizza", "burger", "grill", "shawarma", "sandwich")),
    ("hotel", ("hotel", "motel", "resort", "hostel", "guest_house", "lodging")),
    ("mall", ("shopping_center", "mall", "supermarket", "department_store", "grocery", "hypermarket")),
    ("landmark", ("landmark", "museum", "monument", "park", "stadium", "historic", "tourist", "airport")),
    ("transport", ("bus_station", "train_station", "transportation", "parking", "taxi")),
]
MIN_ZOOM = {"hospital": 12, "university": 12, "mall": 13, "landmark": 13, "government": 14, "mosque": 14, "school": 14,
            "fuel": 14, "hotel": 14, "bank": 15, "pharmacy": 15, "clinic": 15, "restaurant": 15, "cafe": 16, "transport": 15,
            "shop": 16, "place": 16}
CITY_BOXES = {  # (lng_min, lat_min, lng_max, lat_max) — قياسُ «قبل وبعد» لكلِّ مدينة (أمرُ المالك ٢-٦)
    "عمّان": (35.75, 31.85, 36.05, 32.10), "مادبا": (35.76, 31.69, 35.83, 31.74), "إربد": (35.80, 32.50, 35.90, 32.59),
    "الجزائر العاصمة": (2.90, 36.65, 3.25, 36.82), "وهران": (-0.75, 35.62, -0.52, 35.78),
    "طرابلس (المركز وتاجوراء وسوق الجمعة وعين زارة)": (13.05, 32.75, 13.40, 32.92),
    "بنغازي": (19.95, 32.02, 20.20, 32.20), "مصراتة": (15.00, 32.30, 15.15, 32.42),
}

MAIN_ROADS = {"motorway": 100, "trunk": 80, "primary": 60, "secondary": 50, "tertiary": 40,
              "motorway_link": 50, "trunk_link": 40, "primary_link": 40, "secondary_link": 35, "unclassified": 35}
SEG_M = 120.0


def category(tag: str) -> str:
    base = tag.split(" ")[0]
    if base.startswith("overture="):
        words = base[len("overture="):].lower()
        for cat, marks in OVERTURE_WORDS:
            if any(m in words for m in marks):
                return cat
        return "place"
    if base in OSM_LOOKUP:
        return OSM_LOOKUP[base]
    if base.startswith("shop="):
        return "shop"
    return "place"


def display_name(name_ar, name_en, alt):
    """**العربيُّ أوّلاً، ثمّ المحلّيّ، ثمّ الفرنسيّ/الإنجليزيّ** — وما لا اسمَ له يعود فارغاً فلا يُرسم."""
    if name_ar:
        return name_ar.strip()
    alts = [a.strip() for a in (alt or "").split(" | ") if a.strip()]
    arabic = next((a for a in alts if ARABIC.search(a)), None)
    return arabic or (alts[0] if alts else None) or (name_en or "").strip() or None


def export_places(stats):
    db = sqlite3.connect(f"file:{os.path.join(WORK, 'places.sqlite')}?mode=ro", uri=True)
    cols = {r[1] for r in db.execute("PRAGMA table_info(places)")}
    okey = "okey" if "okey" in cols else "NULL"
    rows = db.execute(f"SELECT cc, kind, tag, name_ar, name_en, alt, lat, lng, rank, src, {okey} FROM places WHERE kind IN ('poi', 'building')")
    n = 0
    # **ملفٌّ لكلِّ تكبيرِ بدءٍ لا مفتاحُ `tippecanoe.minzoom`** (قِيس ١٨/١١): tippecanoe 2.49 أسقط مع ذلك المفتاح ٩٨٪ من نقاط عيّنةٍ
    # في عمّان عند z16 (٦٬٤٥٩ ⇐ ١٠٧)، وبدونه بقيت كلُّها — فالمجموعةُ تُبنى وحدَها بـ`-Z<N>` في `map-data.yml` ثمّ تُدمج بـ`tile-join`.
    files = {}
    try:
        for cc, kind, tag, name_ar, name_en, alt, lat, lng, rank, src, key in rows:
            name = display_name(name_ar, name_en, alt)
            if not name:
                continue
            cat = category(tag or "") if kind == "poi" else "place"
            props = {"n": name[:60], "c": cat, "r": int(rank or 0), "cc": cc}
            if key:
                # **مفتاحُ المكان** (SPEC §١٠٩-ب): اسمٌ عربيٌّ يكتبه المشرفُ في «أماكن بلا اسم عربي» يُرسم بهذا المفتاح في التطبيقين
                props["k"] = key
            if cat == "hospital" and " op=" in (tag or ""):
                props["o"] = tag.split(" op=")[1]  # public | private — من `operator:type`، وما لا وسمَ له لا يُوصف
            if name_en and name_en.strip() != props["n"]:
                props["e"] = name_en.strip()[:60]
            minzoom = max(MIN_ZOOM.get(cat, 16) - (1 if (rank or 0) >= 7 else 0), 11)
            if minzoom not in files:
                files[minzoom] = open(os.path.join(WORK, f"places-z{minzoom}.geojsonl"), "w", encoding="utf-8")
            files[minzoom].write(json.dumps({"type": "Feature", "properties": props,
                                  "geometry": {"type": "Point", "coordinates": [round(lng, 6), round(lat, 6)]}},
                                 ensure_ascii=False) + "\n")
            n += 1
            for city, (x0, y0, x1, y1) in CITY_BOXES.items():
                if x0 <= lng <= x1 and y0 <= lat <= y1:
                    stats["cities"].setdefault(city, {"places": {}, "streets_named": 0, "buildings": 0})
                    bucket = stats["cities"][city]["places"]
                    bucket[cat] = bucket.get(cat, 0) + 1
    finally:
        for f in files.values():
            f.close()
    stats["places_total"] = n
    print("places", n, flush=True)


def bearing(a, b):
    y = math.sin(math.radians(b[0] - a[0])) * math.cos(math.radians(b[1]))
    x = math.cos(math.radians(a[1])) * math.sin(math.radians(b[1])) - math.sin(math.radians(a[1])) * math.cos(math.radians(b[1])) * math.cos(math.radians(b[0] - a[0]))
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def metres(a, b):
    dx = (b[0] - a[0]) * 111320 * math.cos(math.radians((a[1] + b[1]) / 2))
    dy = (b[1] - a[1]) * 110540
    return math.hypot(dx, dy)


def speed_of(tags, cls):
    raw = (tags.get("maxspeed") or "").strip().lower()
    m = re.match(r"^(\d+)\s*(mph)?$", raw)
    if m:
        v = int(m.group(1))
        return round(v * 1.609) if m.group(2) else v
    return MAIN_ROADS[cls]


class Roads(osmium.SimpleHandler):
    def __init__(self, cc, roads, works, stats):
        super().__init__()
        self.cc, self.roads, self.works, self.stats = cc, roads, works, stats

    def way(self, w):
        tags = w.tags
        hw = tags.get("highway")
        pts = [(nd.lon, nd.lat) for nd in w.nodes if nd.location.valid()]
        if len(pts) < 2:
            return
        if hw and tags.get("name") and hw not in ("footway", "path", "steps", "cycleway", "track", "bridleway", "corridor", "proposed"):
            mid = pts[len(pts) // 2]
            for city, (x0, y0, x1, y1) in CITY_BOXES.items():
                if x0 <= mid[0] <= x1 and y0 <= mid[1] <= y1:
                    self.stats["cities"].setdefault(city, {"places": {}, "streets_named": 0, "buildings": 0})
                    self.stats["cities"][city]["streets_named"] += 1
        # ── الصيانةُ والإغلاقُ من أوسمة OSM — «صيانة» للبناء، و«طريق مغلق» للطريق الرئيسيّ الممنوع على السيّارات وحدَه
        work = None
        if hw == "construction" or (hw and tags.get("construction")):
            work = "works"
        elif hw in ("trunk", "primary", "secondary", "tertiary") and (tags.get("access") == "no" or tags.get("motor_vehicle") == "no"):
            work = "closed"
        if work:
            mid = pts[len(pts) // 2]
            self.works.write(json.dumps({"type": "Feature",  # تكبيرُ البدء ١٣ من `-Z13` في `map-data.yml` لا من مفتاحٍ هنا
                                         "properties": {"k": work, "n": (tags.get("name:ar") or tags.get("name") or "")[:60]},
                                         "geometry": {"type": "Point", "coordinates": [round(mid[0], 6), round(mid[1], 6)]}},
                                        ensure_ascii=False) + "\n")
            self.stats["works"][work] = self.stats["works"].get(work, 0) + 1
            return
        if hw not in MAIN_ROADS:
            return
        free = speed_of(tags, hw)
        name = (tags.get("name:ar") or tags.get("name") or "")[:60]
        oneway = 1 if tags.get("oneway") in ("yes", "1", "true") or hw.startswith("motorway") else 0
        seg, length = [pts[0]], 0.0
        for p in pts[1:]:
            length += metres(seg[-1], p)
            seg.append(p)
            if length >= SEG_M:
                self.roads.append((self.cc, w.id, hw, name, free, oneway, seg))
                seg, length = [p], 0.0
        if len(seg) >= 2:
            self.roads.append((self.cc, w.id, hw, name, free, oneway, seg))


def build_roads(stats):
    path = os.path.join(WORK, "roads.sqlite")
    if os.path.exists(path):
        os.remove(path)
    db = sqlite3.connect(path)
    db.executescript("""
    PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
    CREATE TABLE segments(id INTEGER PRIMARY KEY, cc TEXT, way INTEGER, cls TEXT, name TEXT, free INTEGER, oneway INTEGER,
                          b0 REAL, b1 REAL, coords TEXT);
    CREATE VIRTUAL TABLE seg_box USING rtree(id, x0, x1, y0, y1);
    """)
    works = open(os.path.join(WORK, "works.geojsonl"), "w", encoding="utf-8")
    total = 0
    for country, cc in COUNTRIES.items():
        roads = []
        h = Roads(cc, roads, works, stats)
        idx = os.path.join(WORK, f"roads-{cc}.idx")
        h.apply_file(os.path.join(WORK, "pbf", f"{country}.osm.pbf"), locations=True, idx=f"sparse_file_array,{idx}")
        os.remove(idx)
        rows, boxes = [], []
        for i, (c, way, cls, name, free, oneway, seg) in enumerate(roads, start=total + 1):
            xs, ys = [p[0] for p in seg], [p[1] for p in seg]
            rows.append((i, c, way, cls, name, free, oneway, round(bearing(seg[0], seg[-1]), 1), 0.0,
                         json.dumps([[round(x, 6), round(y, 6)] for x, y in seg])))
            boxes.append((i, min(xs), max(xs), min(ys), max(ys)))
        db.executemany("INSERT INTO segments VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
        db.executemany("INSERT INTO seg_box VALUES (?,?,?,?,?)", boxes)
        total += len(rows)
        print(cc, "segments", len(rows), flush=True)
    works.close()
    db.commit()
    db.execute("VACUUM")
    db.close()
    stats["road_segments"] = total


def count_buildings(stats):
    path = os.path.join(WORK, "buildings.geojsonl")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            feature = json.loads(line)
            ring = feature["geometry"]["coordinates"][0]
            if feature["geometry"]["type"] == "MultiPolygon":
                ring = ring[0]
            x, y = ring[0][0], ring[0][1]
            for city, (x0, y0, x1, y1) in CITY_BOXES.items():
                if x0 <= x <= x1 and y0 <= y <= y1:
                    stats["cities"].setdefault(city, {"places": {}, "streets_named": 0, "buildings": 0})
                    stats["cities"][city]["buildings"] += 1


def main():
    t0 = time.time()
    stats = {"cities": {}, "works": {}}
    export_places(stats)
    build_roads(stats)
    count_buildings(stats)
    stats["seconds"] = round(time.time() - t0)
    with open(os.path.join(WORK, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
