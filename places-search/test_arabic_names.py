"""**الأسماءُ العربيّة** (SPEC §١٠٩-ب) — بلا شبكة: المطابقةُ بالاسم نفسِه في المكان نفسِه، ولا اسمَ مزدوجٌ ولا عامّيٌّ ولا تاريخيّ،
ومدنُ القياس نسخةُ `build_map_data.py` حرفاً.

usage: python3 -I places-search/test_arabic_names.py
"""
import ast
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("arabic_names", os.path.join(HERE, "arabic_names.py"))
an = importlib.util.module_from_spec(spec)
spec.loader.exec_module(an)

failures = []


def check(label, ok):
    print(("ok   " if ok else "FAIL ") + label)
    if not ok:
        failures.append(label)


check("اسمٌ عربيٌّ خالصٌ يُقبل", an.usable_arabic("  مستشفى   العبدلي ") == "مستشفى العبدلي")
check("والمزدوجُ لا يُقبل", an.usable_arabic("Sharia Amr - شارع الوادي") is None)
check("واللاتينيُّ لا يُقبل", an.usable_arabic("Abdali Hospital") is None)
check("ومفتاحُ المطابقة بلا علاماتٍ ولا حالة", an.latin_key("Hôpital  d'Oran") == an.latin_key("hopital d oran"))

features = [("1", "Abdali Hospital", "Abdali Hospital", "31.9600", "35.9100"),
            ("2", "Oran", "Oran", "35.6969", "-0.6331"),
            ("3", "Old Souk", "Old Souk", "32.0", "35.0")]
alternates = [
    ("1", "ar", "مستشفى العبدلي", "1", "", "", ""),
    ("1", "en", "Al-Abdali Hospital", "", "", "", ""),
    ("2", "ar", "وهران", "", "", "", ""),
    ("2", "ar", "الباهية", "", "", "1", ""),          # عامّيّ ⇐ لا
    ("3", "ar", "السوق القديم", "", "", "", "1"),     # تاريخيّ ⇐ لا
]
index = an.geonames_index(features, alternates)
check("بالاسم نفسِه في المكان نفسِه", an.geonames_match(index, ["Abdali Hospital"], 31.9601, 35.9102, "poi") == "مستشفى العبدلي")
check("وباسمٍ بديلٍ لاتينيّ", an.geonames_match(index, ["Al-Abdali Hospital"], 31.9601, 35.9102, "poi") == "مستشفى العبدلي")
check("وبعيداً ⇐ لا", an.geonames_match(index, ["Abdali Hospital"], 31.99, 35.95, "poi") is None)
check("والمدينةُ بمسافتها الأوسع، والعامّيُّ لا يغلب", an.geonames_match(index, ["Oran"], 35.71, -0.62, "city") == "وهران")
check("والتاريخيُّ وحدَه لا يُعطي اسماً", an.geonames_match(index, ["Old Souk"], 32.0, 35.0, "poi") is None)
check("ولا مطابقةَ بالشبه", an.geonames_match(index, ["Abdali Hospita"], 31.9601, 35.9102, "poi") is None)

with open(os.path.join(HERE, "build_map_data.py"), encoding="utf-8") as handle:
    tree = ast.parse(handle.read())
boxes = next(ast.literal_eval(node.value) for node in tree.body
             if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "CITY_BOXES")
check("مدنُ القياس نسخةُ build_map_data حرفاً", boxes == an.CITY_BOXES)
check("ولكلِّ مدينةٍ دولتها", set(an.CITY_OF_CC) == set(an.CITY_BOXES))
check("ونقطةٌ في عمّان مدينتُها عمّان", an.city_of(31.96, 35.91) == "عمّان")

# ── **الفرنسيُّ في الجزائر اسمٌ محلّيّ** (أمرُ المالك ٢٠٢٦-١١-٢٠ الثاني، البند ٤) — `main()` على قاعدةٍ صغيرةٍ بلا شبكة
import json  # noqa: E402
import sqlite3  # noqa: E402
import tempfile  # noqa: E402

an.wikidata_labels = lambda ids: {}
an.load_geonames = lambda cc: (_ for _ in ()).throw(RuntimeError("offline"))
with tempfile.TemporaryDirectory() as work:
    db = sqlite3.connect(os.path.join(work, "places.sqlite"))
    db.execute("CREATE TABLE places(id INTEGER PRIMARY KEY, cc TEXT, kind TEXT, tag TEXT, name_ar TEXT, name_en TEXT, alt TEXT, ctx_local TEXT,"
               " ctx_city TEXT, lat REAL, lng REAL, rank INTEGER, src TEXT, okey TEXT, wd TEXT, brand INTEGER, name_fr TEXT)")
    oran = (35.70, -0.63)
    db.executemany("INSERT INTO places VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        (1, "DZ", "poi", "amenity=pharmacy", None, None, "Pharmacie Centrale", None, None, *oran, 4, "osm", "n1", "", 0, "Pharmacie Centrale"),
        (2, "DZ", "poi", "amenity=cafe", None, None, "Café Riche", None, None, *oran, 4, "osm", "n2", "", 0, None),
        (3, "DZ", "poi", "amenity=hospital", None, None, "EHU Oran", None, None, *oran, 6, "osm", "n3", "", 0, None),
        (4, "JO", "poi", "amenity=clinic", None, None, "Clinique X", None, None, 31.96, 35.91, 4, "osm", "n4", "", 0, "Clinique X"),
        (5, "DZ", "poi", "amenity=bank", "بنك الجزائر", None, "بنك الجزائر", None, None, *oran, 4, "osm", "n5", "", 0, None),
    ])
    db.commit()
    db.close()
    sys.argv = ["arabic_names.py", work]
    an.main()
    db = sqlite3.connect(os.path.join(work, "places.sqlite"))
    rows = db.execute("SELECT okey, cat, prio FROM missing_ar ORDER BY cc, prio, rank DESC").fetchall()
    db.close()
    stats = json.load(open(os.path.join(work, "arabic_stats.json"), encoding="utf-8"))
check("الصيدليّةُ باسمها الفرنسيّ ليست «بلا اسم» في الجزائر", "n1" not in [r[0] for r in rows])
check("وفي الأردن الفرنسيُّ لا يُغني عن العربيّ", "n4" in [r[0] for r in rows])
check("والمستشفى قبل المقهى", [r[0] for r in rows if r[0] in ("n2", "n3")] == ["n3", "n2"])
check("والفئةُ وترتيبُها مكتوبان", ("n3", "hospital", 0) in rows)
oran_stats = stats["cities"]["وهران"]
check("وأرقامُ وهران: عربيٌّ وفرنسيٌّ وناقص", (oran_stats["arabic"], oran_stats["french"], oran_stats["missing"]) == (1, 1, 2))
check("والناقصُ اللاتينيُّ يُعدّ ولا يُخفى", oran_stats["missing_latin_only"] == 2)
check("وغيابُ GeoNames مكتوبٌ لا مسكوت", any("geonames" in e for e in stats["errors"]))

sys.exit(1 if failures else 0)
