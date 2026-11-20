"""Builds places.sqlite (FTS5 trigram) from OSM PBFs + Overture places parquet. Runs OFF production.

usage: python -I build_index.py <workdir>   (workdir holds pbf/<country>.osm.pbf and overture_places.parquet)
"""
import math
import os
import re
import sqlite3
import sys
import time

import duckdb
import osmium

WORK = sys.argv[1]
OUT = os.path.join(WORK, "places.sqlite")
COUNTRIES = {"jordan": "JO", "algeria": "DZ", "libya": "LY"}

TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
ARABIC = re.compile(r"[؀-ۿ]")
FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي", "ك": "ك", "ی": "ي", "ھ": "ه"})


def norm(text: str) -> str:
    text = TASHKEEL.sub("", text or "").translate(FOLD).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


PLACE_KIND = {"city": ("city", 9), "town": ("town", 8), "village": ("village", 6), "suburb": ("district", 7),
              "neighbourhood": ("neighbourhood", 7), "quarter": ("neighbourhood", 7), "hamlet": ("village", 4),
              "locality": ("locality", 4), "borough": ("district", 7)}
POI_KEYS = ("amenity", "shop", "tourism", "leisure", "office", "healthcare", "aeroway", "historic", "railway",
            "public_transport", "man_made", "craft", "sport")
POI_RANK = {"aeroway": 9, "tourism": 6, "amenity": 6, "leisure": 5, "healthcare": 6, "historic": 6, "shop": 5,
            "office": 4, "railway": 5, "public_transport": 3, "man_made": 3, "craft": 3, "sport": 4}
STREET_TYPES = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
                "living_street", "pedestrian", "service", "road", "motorway_link", "trunk_link", "primary_link"}


def names(tags):
    alt = []
    for key in ("name", "name:ar", "name:en", "name:fr", "alt_name", "alt_name:ar", "official_name", "official_name:ar",
                "short_name", "old_name", "name:ar1", "loc_name"):
        v = tags.get(key)
        if v:
            alt.extend(part.strip() for part in v.split(";") if part.strip())
    ar = tags.get("name:ar") or next((n for n in alt if ARABIC.search(n)), None)
    en = tags.get("name:en") or tags.get("name:fr") or next((n for n in alt if not ARABIC.search(n)), None)
    return ar, en, list(dict.fromkeys(alt))


class Handler(osmium.SimpleHandler):
    def __init__(self, cc):
        super().__init__()
        self.cc = cc
        self.rows = []

    def _add(self, kind, rank, tags, lat, lng, extra_kind="", key=""):
        ar, en, alt = names(tags)
        if not alt:
            return
        # **المستشفى حكوميٌّ أم خاصّ** (أمرُ المالك ١٨/١١ السابع ٢-٢) — من `operator:type` وحدَه، وما لا وسمَ له لا يُوصف
        if extra_kind in ("amenity=hospital", "healthcare=hospital"):
            op = (tags.get("operator:type") or "").lower()
            if op in ("government", "public", "state", "military"):
                extra_kind += " op=public"
            elif op in ("private", "private_non_profit", "charitable", "ngo", "religious"):
                extra_kind += " op=private"
        # **مفتاحٌ ثابتٌ ووسمُ wikidata وعلامةٌ تجاريّة** (SPEC §١٠٩-ب): المفتاحُ يربط اسمَ اللوحة بالمكان عبر البناءات، وwikidata مصدرُ
        # الاسم العربيّ الثالث، **والعلامةُ تبقى كما تكتبها** فلا تُدرج في «بلا اسم عربي»
        wd = tags.get("wikidata") or tags.get("brand:wikidata") or ""
        brand = 1 if (tags.get("brand") or tags.get("brand:wikidata")) else 0
        self.rows.append((self.cc, kind, extra_kind, ar, en, alt, lat, lng, rank, key, wd, brand))

    def _classify(self, tags):
        place = tags.get("place")
        if place in PLACE_KIND:
            return PLACE_KIND[place] + ("",)
        for key in POI_KEYS:
            if key in tags:
                return ("poi", POI_RANK[key], f"{key}={tags[key]}")
        if tags.get("building") and tags.get("name"):
            return ("building", 3, "building")
        return None

    def node(self, n):
        if "name" not in n.tags and "name:ar" not in n.tags:
            return
        c = self._classify(n.tags)
        if c and n.location.valid():
            self._add(c[0], c[1], n.tags, n.location.lat, n.location.lon, c[2], f"n{n.id}")

    def way(self, w):
        tags = w.tags
        if "name" not in tags and "name:ar" not in tags:
            return
        pts = [(nd.lat, nd.lon) for nd in w.nodes if nd.location.valid()]
        if not pts:
            return
        if tags.get("highway") in STREET_TYPES:
            mid = pts[len(pts) // 2]
            self._add("street", 5 if tags["highway"] in ("motorway", "trunk", "primary", "secondary") else 4,
                      tags, mid[0], mid[1], "highway=" + tags["highway"], f"w{w.id}")
            return
        c = self._classify(tags)
        if c:
            lat = sum(p[0] for p in pts) / len(pts)
            lng = sum(p[1] for p in pts) / len(pts)
            self._add(c[0], c[1] + 1, tags, lat, lng, c[2], f"w{w.id}")

    def area(self, a):  # multipolygon relations only (ways handled above)
        if a.from_way():
            return
        tags = a.tags
        if "name" not in tags and "name:ar" not in tags:
            return
        c = self._classify(tags)
        if not c:
            return
        lats, lngs = [], []
        for ring in a.outer_rings():
            for nd in ring:
                if nd.location.valid():
                    lats.append(nd.lat)
                    lngs.append(nd.lon)
        if lats:
            self._add(c[0], c[1] + 1, tags, sum(lats) / len(lats), sum(lngs) / len(lngs), c[2], f"r{a.orig_id()}")


def cell(lat, lng, size):
    return (round(lat / size), round(lng / size))


def main():
    t0 = time.time()
    rows = []
    for country, cc in COUNTRIES.items():
        h = Handler(cc)
        idx = os.path.join(WORK, f"nodes-{cc}.idx")
        h.apply_file(os.path.join(WORK, "pbf", f"{country}.osm.pbf"), locations=True, idx=f"sparse_file_array,{idx}")
        os.remove(idx)
        print(cc, "osm rows", len(h.rows), round(time.time() - t0), "s", flush=True)
        rows.extend(h.rows)

    # streets: merge segments of the same name within ~1.1 km
    merged, seen = [], {}
    for r in rows:
        if r[1] != "street":
            merged.append(r)
            continue
        key = (r[0], norm(r[5][0]), cell(r[6], r[7], 0.01))
        if key in seen:
            continue
        seen[key] = True
        merged.append(r)
    rows = merged

    # context: nearest district/neighbourhood (<=2.5 km) and nearest city/town (<=25 km)
    areas = {"local": {}, "city": {}}
    for r in rows:
        if r[1] in ("district", "neighbourhood"):
            areas["local"].setdefault((r[0],) + cell(r[6], r[7], 0.05), []).append(r)
        elif r[1] in ("city", "town"):
            areas["city"].setdefault((r[0],) + cell(r[6], r[7], 0.5), []).append(r)

    def nearest(group, r, size, limit_km):
        best, bd = None, limit_km
        c = cell(r[6], r[7], size)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for a in areas[group].get((r[0], c[0] + dx, c[1] + dy), ()):
                    d = math.hypot((a[6] - r[6]) * 111, (a[7] - r[7]) * 111 * math.cos(math.radians(r[6])))
                    if d < bd and a is not r:
                        best, bd = a, d
        return best

    def label(r):
        return r[3] or r[4] or r[5][0]

    # Overture: skip a place OSM already has (same normalised name within ~150 m)
    osm_keys = set()
    for r in rows:
        for n in r[5]:
            osm_keys.add((norm(n),) + cell(r[6], r[7], 0.0015))
    ov = duckdb.connect().execute(
        "SELECT cc, name, name_ar, name_en, cat, confidence, lat, lng, locality, street, oid, brand_wd, brand_name FROM read_parquet(?) "
        "WHERE name IS NOT NULL AND confidence >= 0.5", [os.path.join(WORK, "overture_places.parquet")]).fetchall()
    added = 0
    for cc, name, n_ar, n_en, cat, conf, lat, lng, locality, street, oid, brand_wd, brand_name in ov:
        alts = [x for x in (name, n_ar, n_en) if x]
        k = norm(name)
        c = cell(lat, lng, 0.0015)
        if any((k, c[0] + dx, c[1] + dy) in osm_keys for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
            continue
        ar = n_ar or (name if ARABIC.search(name) else None)
        en = n_en or (None if ARABIC.search(name) else name)
        rows.append((cc, "poi", f"overture={cat or ''}", ar, en, list(dict.fromkeys(alts)), lat, lng,
                     4 + (1 if conf >= 0.8 else 0), f"o{oid}" if oid else "", brand_wd or "", 1 if (brand_wd or brand_name) else 0))
        added += 1
    print("overture added", added, "of", len(ov), flush=True)

    if os.path.exists(OUT):
        os.remove(OUT)
    db = sqlite3.connect(OUT)
    db.executescript("""
    PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA page_size=4096;
    CREATE TABLE places(id INTEGER PRIMARY KEY, cc TEXT, kind TEXT, tag TEXT, name_ar TEXT, name_en TEXT,
                        alt TEXT, ctx_local TEXT, ctx_city TEXT, lat REAL, lng REAL, rank INTEGER, src TEXT,
                        okey TEXT, wd TEXT, brand INTEGER);
    CREATE VIRTUAL TABLE fts USING fts5(n, content='', tokenize='trigram');
    """)
    batch, fts = [], []
    for i, r in enumerate(rows, 1):
        loc = nearest("local", r, 0.05, 2.5)
        city = nearest("city", r, 0.5, 25)
        src = "overture" if r[2].startswith("overture=") else "osm"
        batch.append((i, r[0], r[1], r[2], r[3], r[4], " | ".join(r[5]), label(loc) if loc else None,
                      label(city) if city else None, r[6], r[7], r[8], src, r[9] or None, r[10] or None, r[11]))
        fts.append((i, " ".join(dict.fromkeys(norm(n) for n in r[5]))))
        if len(batch) >= 50000:
            db.executemany("INSERT INTO places VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)
            db.executemany("INSERT INTO fts(rowid, n) VALUES (?,?)", fts)
            batch, fts = [], []
    db.executemany("INSERT INTO places VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)
    db.executemany("INSERT INTO fts(rowid, n) VALUES (?,?)", fts)
    db.execute("CREATE INDEX ix_places_cc ON places(cc)")
    db.execute("INSERT INTO fts(fts) VALUES ('optimize')")
    db.commit()
    db.execute("VACUUM")
    print(db.execute("SELECT cc, kind, count(*) FROM places GROUP BY cc, kind ORDER BY cc, 3 DESC").fetchall())
    db.close()
    print("size MB", round(os.path.getsize(OUT) / 1e6, 1), "total s", round(time.time() - t0))


main()
