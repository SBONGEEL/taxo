"""**الاسمُ العربيُّ من أربعة مصادرَ مفتوحة، وما بقي بلا اسمٍ يُكتب في قائمة** (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-ب).

usage: python -I arabic_names.py <workdir>
  reads/writes  <workdir>/places.sqlite   (بعد build_index.py وقبل postprocess.py — فيدخل الاسمُ العربيُّ البحثَ أيضاً)
  downloads     Wikidata (labels.ar، CC0) و GeoNames (alternateNames بلغة ar، CC-BY 4.0) — خارج الإنتاج، في `map-data.yml`
  writes        <workdir>/arabic_stats.json   (أرقامُ كلِّ مدينة: بمصدرها، والعلاماتُ كما هي، والباقي بلا اسم)

**الترتيب**: OSM `name:ar` وOverture `names.common.ar` (يأخذهما `build_index.py` سلفاً) ⇐ Wikidata عبر وسم `wikidata` ⇐ GeoNames
بالاسم نفسِه في المكان نفسِه. **لا ترجمةَ آليّةَ ولا نقحرة**: ما لم يكتبه أحدٌ بالعربيّة في مصدرٍ لا يُكتب.
**والعلامةُ التجاريّةُ تبقى كما تكتبها العلامة** — لا تُملأ ولا تُدرج في القائمة.

وما بقي ⇐ جدولُ `missing_ar` في `places.sqlite` نفسِه، يقرؤه `server.py` (`/missing-ar`) فتعرضه اللوحةُ «أماكن بلا اسم عربي»،
والمشرفُ يكتب الاسم فيُرسم في التطبيقين بمفتاح المكان (`okey`) — بلا انتظار البناء القادم.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import sqlite3
import sys
import time
import unicodedata
import urllib.request
import zipfile

ARABIC = re.compile(r"[؀-ۿ]")
LETTERS_ONLY = re.compile(r"[^0-9a-z؀-ۿ ]+")
COUNTRIES = ("JO", "DZ", "LY")
#: **مدنُ القياس** — نسخةُ `CITY_BOXES` في `build_map_data.py` حرفاً (يقيس تساويهما `test_arabic_names.py`)
CITY_BOXES = {  # (lng_min, lat_min, lng_max, lat_max)
    "عمّان": (35.75, 31.85, 36.05, 32.10), "مادبا": (35.76, 31.69, 35.83, 31.74), "إربد": (35.80, 32.50, 35.90, 32.59),
    "الجزائر العاصمة": (2.90, 36.65, 3.25, 36.82), "وهران": (-0.75, 35.62, -0.52, 35.78),
    "طرابلس (المركز وتاجوراء وسوق الجمعة وعين زارة)": (13.05, 32.75, 13.40, 32.92),
    "بنغازي": (19.95, 32.02, 20.20, 32.20), "مصراتة": (15.00, 32.30, 15.15, 32.42),
}
CITY_OF_CC = {"عمّان": "JO", "مادبا": "JO", "إربد": "JO", "الجزائر العاصمة": "DZ", "وهران": "DZ",
              "طرابلس (المركز وتاجوراء وسوق الجمعة وعين زارة)": "LY", "بنغازي": "LY", "مصراتة": "LY"}
#: **ما يظهر على الخريطة** — ما ترسمه مربّعاتُنا (`build_map_data.export_places`)، فالقائمةُ لا تحمل ما لا يُرى
MAP_KINDS = ("poi", "building")
#: **مسافةُ «المكان نفسُه»** لمطابقة GeoNames — الحيُّ والمدينةُ أوسعُ من نقطة
SAME_KM = {"city": 4.0, "town": 3.0, "village": 1.5, "district": 2.0, "neighbourhood": 1.2, "locality": 1.2}
POINT_KM = 0.4
USER_AGENT = "TAXO-open-map-build/1.0 (open data build; no personal data)"


def latin_key(text: str) -> str:
    """**مفتاحُ مطابقة الاسم** — بلا تشكيلٍ ولا علاماتٍ ولا حالةِ أحرف؛ لا يُعرض."""
    folded = unicodedata.normalize("NFKD", text or "")
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch)).casefold()
    return " ".join(LETTERS_ONLY.sub(" ", folded).split())


def city_of(lat: float, lng: float) -> str | None:
    for city, (x0, y0, x1, y1) in CITY_BOXES.items():
        if x0 <= lng <= x1 and y0 <= lat <= y1:
            return city
    return None


def km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    return math.hypot((lat2 - lat1) * 111.0, (lng2 - lng1) * 111.0 * math.cos(math.radians(lat1)))


def usable_arabic(text: str | None) -> str | None:
    """**اسمٌ عربيٌّ خالص** — ما فيه حرفٌ عربيٌّ ولا لاتينيٌّ معه (اسمٌ مزدوجٌ «Sharia … - شارع …» ليس اسماً عربيّاً)."""
    if not text:
        return None
    text = " ".join(text.split())
    if not ARABIC.search(text) or re.search(r"[A-Za-z]", text):
        return None
    return text[:120]


# ── Wikidata ─────────────────────────────────────────────────────────────────────────────────────────────────────────


def _get(url: str, attempts: int = 4) -> bytes:
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except Exception:  # noqa: BLE001 — الشبكةُ تتعثّر؛ يُعاد ثمّ يُرفع
            if attempt == attempts - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def wikidata_labels(ids: list[str]) -> dict[str, str]:
    """`labels.ar` لكلِّ معرِّف — خمسون في الطلب (حدُّ `wbgetentities`)، والغائبُ لا يعود."""
    found: dict[str, str] = {}
    for start in range(0, len(ids), 50):
        chunk = ids[start:start + 50]
        url = ("https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=labels&languages=ar&ids="
               + "|".join(chunk))
        body = json.loads(_get(url))
        for qid, entity in (body.get("entities") or {}).items():
            label = usable_arabic(((entity.get("labels") or {}).get("ar") or {}).get("value"))
            if label:
                found[qid] = label
        time.sleep(0.2)
    return found


# ── GeoNames ─────────────────────────────────────────────────────────────────────────────────────────────────────────


def _zip_lines(data: bytes, name: str):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        with archive.open(name) as handle:
            yield from csv.reader(io.TextIOWrapper(handle, encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE)


def geonames_index(features: list[tuple], alternates: list[tuple]) -> dict[str, list[tuple[float, float, str]]]:
    """**اسمٌ لاتينيٌّ ⇐ مواضعُ لها اسمٌ عربيّ** — `features`: (id, name, ascii, lat, lng)، `alternates`: (id, lang, name, preferred,
    short, colloquial, historic). العربيُّ المفضَّلُ أوّلاً، والعامّيُّ والتاريخيُّ لا يُؤخذان."""
    arabic: dict[str, tuple[int, str]] = {}
    latin: dict[str, set[str]] = {}
    for gid, lang, name, preferred, short, colloquial, historic in alternates:
        if colloquial == "1" or historic == "1":
            continue
        if lang == "ar":
            label = usable_arabic(name)
            if label:
                score = (2 if preferred == "1" else 0) + (0 if short == "1" else 1)
                if gid not in arabic or score > arabic[gid][0]:
                    arabic[gid] = (score, label)
        elif lang in ("", "en", "fr") and not ARABIC.search(name or ""):
            latin.setdefault(gid, set()).add(latin_key(name))
    index: dict[str, list[tuple[float, float, str]]] = {}
    for gid, name, ascii_name, lat, lng in features:
        if gid not in arabic:
            continue
        for key in {latin_key(name), latin_key(ascii_name), *latin.get(gid, ())}:
            if key:
                index.setdefault(key, []).append((float(lat), float(lng), arabic[gid][1]))
    return index


def geonames_match(index, names: list[str], lat: float, lng: float, kind: str) -> str | None:
    """**الاسمُ نفسُه في المكان نفسِه** — والأقربُ إن تعدّد؛ ولا مطابقةَ بالشبه."""
    limit = SAME_KM.get(kind, POINT_KM)
    best, best_km = None, limit
    for name in names:
        if ARABIC.search(name):
            continue
        for g_lat, g_lng, label in index.get(latin_key(name), ()):
            d = km(lat, lng, g_lat, g_lng)
            if d <= best_km:
                best, best_km = label, d
    return best


def load_geonames(cc: str) -> dict:
    base = "https://download.geonames.org/export/dump/"
    features = [(row[0], row[1], row[2], row[4], row[5]) for row in _zip_lines(_get(f"{base}{cc}.zip"), f"{cc}.txt") if len(row) > 5]
    alternates = [(row[1], row[2], row[3], row[4], row[5], row[6], row[7])
                  for row in _zip_lines(_get(f"{base}alternatenames/{cc}.zip"), f"{cc}.txt") if len(row) > 7]
    return geonames_index(features, alternates)


# ── البناء ───────────────────────────────────────────────────────────────────────────────────────────────────────────


def main() -> None:
    work = sys.argv[1]
    db = sqlite3.connect(os.path.join(work, "places.sqlite"))
    cols = {r[1] for r in db.execute("PRAGMA table_info(places)")}
    if "src_ar" not in cols:
        db.execute("ALTER TABLE places ADD COLUMN src_ar TEXT")
    db.execute("UPDATE places SET src_ar = src WHERE name_ar IS NOT NULL AND src_ar IS NULL")
    stats: dict = {"cities": {}, "errors": []}

    rows = db.execute("SELECT id, cc, kind, alt, lat, lng, wd, brand FROM places WHERE name_ar IS NULL").fetchall()
    print("without arabic before", len(rows), flush=True)

    # ١) Wikidata — العلامةُ لا تُملأ
    wanted = {}
    for pid, _cc, _kind, _alt, _lat, _lng, wd, brand in rows:
        qid = (wd or "").split(";")[0].strip()
        if qid.startswith("Q") and not brand:
            wanted.setdefault(qid, []).append(pid)
    filled: dict[int, tuple[str, str]] = {}
    try:
        labels = wikidata_labels(sorted(wanted))
        for qid, label in labels.items():
            for pid in wanted[qid]:
                filled[pid] = (label, "wikidata")
    except Exception as exc:  # noqa: BLE001 — **يُكتب في الأرقام ولا يُسكت**: «صفرٌ من Wikidata» غيرُ «لم يُسأل»
        stats["errors"].append(f"wikidata: {str(exc)[:160]}")
    print("wikidata", len(filled), "of", len(wanted), flush=True)

    # ٢) GeoNames — لكلِّ دولة
    for cc in COUNTRIES:
        try:
            index = load_geonames(cc)
        except Exception as exc:  # noqa: BLE001
            stats["errors"].append(f"geonames {cc}: {str(exc)[:160]}")
            continue
        before = len(filled)
        for pid, row_cc, kind, alt, lat, lng, _wd, brand in rows:
            if row_cc != cc or pid in filled or brand:
                continue
            label = geonames_match(index, [a for a in (alt or "").split(" | ") if a], lat, lng, kind)
            if label:
                filled[pid] = (label, "geonames")
        print("geonames", cc, len(filled) - before, flush=True)

    db.executemany(
        "UPDATE places SET name_ar = ?, src_ar = ?, alt = alt || ' | ' || ? WHERE id = ?",
        [(label, source, label, pid) for pid, (label, source) in filled.items()],
    )

    # ٣) ما بقي بلا اسمٍ عربيّ ⇐ القائمة (ما يُرسم على الخريطة وحدَه، والعلاماتُ خارجها)
    db.executescript("""
    DROP TABLE IF EXISTS missing_ar;
    CREATE TABLE missing_ar(okey TEXT PRIMARY KEY, cc TEXT, city TEXT, name TEXT, tag TEXT, rank INTEGER, lat REAL, lng REAL);
    """)
    missing = []
    for okey, cc, tag, alt, ctx_city, lat, lng, rank in db.execute(
        f"SELECT okey, cc, tag, alt, ctx_city, lat, lng, rank FROM places "
        f"WHERE name_ar IS NULL AND COALESCE(brand, 0) = 0 AND okey IS NOT NULL AND kind IN {MAP_KINDS}"
    ):
        city = city_of(lat, lng) or ctx_city or "—"
        name = next((a for a in (alt or "").split(" | ") if a), "")
        missing.append((okey, cc, city, name[:120], (tag or "").split(" ")[0], int(rank or 0), lat, lng))
    db.executemany("INSERT OR IGNORE INTO missing_ar VALUES (?,?,?,?,?,?,?,?)", missing)
    db.execute("CREATE INDEX ix_missing_cc_city ON missing_ar(cc, city, rank DESC)")

    # ٤) الأرقامُ لكلِّ مدينة — على ما يُرسم
    for kind_filter in (MAP_KINDS,):
        for lat, lng, src_ar, brand, has_ar in db.execute(
            f"SELECT lat, lng, src_ar, COALESCE(brand, 0), name_ar IS NOT NULL FROM places WHERE kind IN {kind_filter}"
        ):
            city = city_of(lat, lng)
            if not city:
                continue
            bucket = stats["cities"].setdefault(city, {"cc": CITY_OF_CC[city], "places": 0, "arabic": 0, "osm": 0, "overture": 0,
                                                       "wikidata": 0, "geonames": 0, "brand_as_written": 0, "missing": 0})
            bucket["places"] += 1
            if has_ar:
                bucket["arabic"] += 1
                bucket[src_ar if src_ar in ("osm", "overture", "wikidata", "geonames") else "osm"] += 1
            elif brand:
                bucket["brand_as_written"] += 1
            else:
                bucket["missing"] += 1
    db.commit()
    db.close()
    with open(os.path.join(work, "arabic_stats.json"), "w", encoding="utf-8") as out:
        json.dump(stats, out, ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
