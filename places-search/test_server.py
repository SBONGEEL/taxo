"""**ترتيبُ البحث المفتوح** (٢٠٢٦-١١-١٦) — فهرسٌ صغيرٌ مبنيٌّ هنا بشكل الفهرس الحقيقيّ (`postprocess.py`)، وثلاثُ حالاتٍ وقعت على الإنتاج:
مطارُ الجزائر تحت بلدةٍ تحمل اسمَه، ومكتبٌ في الجبيهة يتسمّى «مطار الملكه علياء»، و«جامعة الجزائر ١» بالرقم الهنديّ لا يجدها «1».
ودقّةُ الفهرس الحقيقيّ تُقاس باختبار الـ١٠٥ (`run105.py`) لا هنا.

usage: python3 -I places-search/test_server.py
"""
import importlib.util
import os
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp()
INDEX = os.path.join(TMP, "places.sqlite")
os.environ["PLACES_INDEX"] = INDEX
spec = importlib.util.spec_from_file_location("srv", os.path.join(HERE, "server.py"))
srv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(srv)

ROWS = [
    # cc, kind, name_ar, name_en, ctx_city, lat, lng, rank, src
    ("DZ", "town", "هواري بومدين", "Houari Boumediene", "حمام دباغ", 36.4155, 7.2870, 8, "osm"),
    ("DZ", "poi", "مطار الجزائر الدولي هواري بومدين", "Algiers International Houari Boumediene Airport", "باب الزوار", 36.7007, 3.2109, 10, "osm"),
    ("JO", "poi", "مطار الملكة علياء الدولي", "Queen Alia International Airport", "الجيزة", 31.7228, 35.9869, 10, "osm"),
    ("JO", "poi", "مطار الملكه علياء", None, "الجبيهة", 31.9781, 35.8656, 5, "overture"),
    ("JO", "poi", "مطار الملكة علياء _الأردن_عمان", None, "صويلح", 32.0242, 35.8503, 4, "overture"),
    ("JO", "poi", "مطار الملكة علياء للشحن الدولي", None, "الجيزة", 31.7235, 36.0003, 4, "overture"),
    ("JO", "poi", "صيدلية عين الباشا", None, "عين الباشا", 32.06, 35.83, 4, "overture"),
    ("JO", "town", "عين الباشا", "Ain al-Basha", "البلقاء", 32.07, 35.86, 8, "osm"),
    ("DZ", "poi", "جامعة الجزائر 2", None, "بن عكنون", 36.7507, 3.0153, 5, "overture"),
    ("DZ", "poi", 'المكتبة المركزية لجامعة الجزائر ١ "بن يوسف بن خدة"', None, "الجزائر", 36.7711, 3.0553, 4, "overture"),
    ("DZ", "poi", "مقام الشهيد", None, "عزيز", 35.8268, 2.4559, 7, "osm"),
    ("DZ", "poi", "مقام الشهيد", "Martyrs Memorial", "القبة", 36.7457, 3.0697, 7, "osm"),
]

db = sqlite3.connect(INDEX)
db.executescript("""
CREATE TABLE places(id INTEGER PRIMARY KEY, cc TEXT, kind TEXT, tag TEXT, name_ar TEXT, name_en TEXT,
                    alt TEXT, ctx_local TEXT, ctx_city TEXT, lat REAL, lng REAL, rank INTEGER, src TEXT, nalt TEXT);
CREATE VIRTUAL TABLE fts USING fts5(n, c, content='', tokenize='trigram');
""")
for i, (cc, kind, ar, en, city, lat, lng, rank, src) in enumerate(ROWS, 1):
    names = [n for n in (ar, en) if n]
    nalt = " | ".join(dict.fromkeys(srv.norm(n) for n in names))
    db.execute("INSERT INTO places VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (i, cc, kind, "", ar, en, " | ".join(names), None, city, lat, lng, rank, src, nalt))
    db.execute("INSERT INTO fts(rowid, n, c) VALUES (?,?,?)", (i, nalt.replace(" | ", " "), f"qq{cc.lower()}qq"))
db.commit()
db.close()

failures = []


def check(label, ok):
    print(("ok   " if ok else "FAIL ") + label)
    if not ok:
        failures.append(label)


top = srv.search("مطار هواري بومدين", "DZ", None, 5)
check("مطارُ الجزائر أوّلاً لا البلدة", bool(top) and top[0]["name"].startswith("مطار الجزائر"))

names = [i["context"] + "/" + i["name"] for i in srv.search("مطار الملكه علياء", "JO", None, 8)]
check("المطارُ الصحيحُ أوّلاً", bool(names) and "الجيزة" in names[0])
check("سميُّ المطار في الجبيهة يُسقط", not any("الجبيهة" in n for n in names))
check("سميُّه في صويلح يُسقط", not any("صويلح" in n for n in names))
check("ما في المطار نفسِه يبقى (الشحن)", any("للشحن" in n for n in names))

near_algiers = (36.77, 3.056)
hit = srv.search("جامعة الجزائر 1", "DZ", near_algiers, 5)
check("«1» يجد «١»", bool(hit) and "١" in hit[0]["name"])

pharmacy = srv.search("صيدلية عين الباشا", "JO", None, 5)
check("محلٌّ باسم بلدةٍ لا يُسقط", any(i["name"] == "صيدلية عين الباشا" for i in pharmacy))

martyrs = srv.search("مقام الشهيد", "DZ", None, 5)
check("بلا موقع: الذي في العاصمة أوّلاً", bool(martyrs) and martyrs[0]["context"].endswith("القبة"))
far = srv.search("مقام الشهيد", "DZ", (35.82, 2.45), 5)
check("وموقعُ الراكب يغلب العاصمة", bool(far) and far[0]["context"].endswith("عزيز"))

sys.exit(1 if failures else 0)
