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
    # محطّةُ القطار في المطار — كانت تتقدّمه حين يُكتب «بو مدين» مفصولاً (الإنتاج ٢٠٢٦-١١-١٦)
    ("DZ", "poi", "محطة مطار هواري بومدين", None, "باب الزوار", 36.6990, 3.2120, 6, "overture"),
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
    # أمرُ المالك §١٠٤ (٢٠٢٦-١١-١٦): الدوّارُ طريقٌ في OSM، والمحلُّ المسمّى باسمه كان يسبقه
    ("JO", "street", "دوار الداخلية", "Interior Roundabout", "عمان", 31.9615, 35.9078, 6, "osm"),
    ("JO", "poi", "رم للبصريات دوار الداخليه", None, "عمان", 31.9621, 35.9081, 6, "overture"),
    # دوّارٌ آخرُ لا يحمل «الداخلية» — كان يتقدّم المحلَّ لأنه دوّارٌ فحسب
    ("JO", "street", "دوار الكمالية", None, "صويلح", 32.0280, 35.8430, 6, "osm"),
    # المكانُ نفسُه ثلاثاً: من OSM، ومن Overture باللغتين في حقلٍ واحد، ونقطةٌ ثالثةٌ على بعد كيلومترين
    ("JO", "poi", "مكة مول", "Mecca Mall", "عمان", 31.9768, 35.8436, 7, "osm"),
    ("JO", "poi", "Mecca Mall | مكة مول", None, "عمان", 31.9770, 35.8438, 5, "overture"),
    ("JO", "poi", "مكة مول", None, "الجبيهة", 31.9900, 35.8550, 4, "overture"),
    ("JO", "poi", "سيتي مول", "City Mall", "عمان", 31.9787, 35.8341, 7, "osm"),
    # حيٌّ بالعربيّة، وصفٌّ آخرُ له باللاتينيّة وحدَها
    ("DZ", "district", "الأبيار", "El Biar", "الجزائر", 36.7680, 3.0300, 8, "osm"),
    ("DZ", "district", None, "El Biar", "الجزائر", 36.7700, 3.0330, 5, "overture"),
    ("DZ", "town", "الجزائر", "Alger", "الجزائر", 36.7538, 3.0588, 10, "osm"),
    # «أين أنا؟» (أمرُ المالك ٢٠٢٦-١١-١٩): مصحّةٌ يعرفها الناسُ أبعدُ قليلاً من محلٍّ بلا شأن، ومكانٌ أقربُ منهما باسمٍ لاتينيٍّ وحدَه
    ("LY", "town", "تاجوراء", "Tajoura", "طرابلس", 32.0100, 13.0100, 8, "osm"),
    ("LY", "poi", "مصحة ابن النفيس", None, "تاجوراء", 32.0010, 13.0005, 5, "overture"),
    ("LY", "poi", "محل الأمانة للهواتف", None, "تاجوراء", 32.0006, 13.0005, 4, "overture"),
    ("LY", "poi", None, "Tech Corner", "تاجوراء", 32.0003, 13.0005, 4, "overture"),
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
# **«بو مدين» مفصولةً خطأً** (أمرُ المالك ٢٠٢٦-١١-١٧، وقع على الإنتاج): المحطّةُ كانت تتقدّم المطار
for q in ("مطار هواري بو مدين", "مطار هوارى بو مدين", "مطار هواري بومدين"):
    top = srv.search(q, "DZ", None, 5)
    check(f"«{q}»: المطارُ أوّلاً لا المحطّة", bool(top) and top[0]["name"].startswith("مطار الجزائر"))
check("الوصلُ لا يمسّ ما لا كلمةَ قصيرةً فيه", srv._join_particles("مطار هواري بومدين") == "مطار هواري بومدين")
check("ولا يصل رقماً", srv._join_particles("جامعة الجزائر 1") == "جامعة الجزائر 1")

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

# ── أمرُ المالك §١٠٤ (٢٠٢٦-١١-١٦): الدوّار، والمطابقةُ العربيّة، والتكرار، والبلد، وذاكرةُ الأجوبة
amman = (31.9539, 35.9106)
for q, where in [(q, w) for q in ("دوار الداخلية", "دوار الداخليه", "دوّار الداخليّة", "دوار  الداخلية ") for w in (amman, None)]:
    got = srv.search(q, "JO", where, 5)
    check(f"«{q}»: الدوّارُ قبل المحلِّ المسمّى باسمه", bool(got) and got[0]["name"] == "دوار الداخلية")
    check(f"«{q}»: صنفُه دوّار", bool(got) and got[0]["cat"] == "roundabout")
for q in ("دوار الداخلية", "دوار الداخليى"):
    names = [i["name"] for i in srv.search(q, "JO", amman, 6)]
    check(f"«{q}»: دوّارٌ آخرُ لا يتقدّم ما يحمل «الداخلية»",
          "دوار الكمالية" not in names or names.index("دوار الكمالية") > names.index("رم للبصريات دوار الداخليه"))
    check(f"«{q}»: والدوّارُ المقصودُ أوّلاً ولو بخطأ إملاء", bool(names) and names[0] == "دوار الداخلية")
plain = srv.search("الداخلية", "JO", None, 5)
check("بلا «دوار» يُوجد الدوّارُ أيضاً", any(i["name"] == "دوار الداخلية" for i in plain))

for q in ("مكة مول", "مكه مول", "Mecca Mall", "mecca mall"):
    got = [i["name"] for i in srv.search(q, "JO", amman, 8)]
    check(f"«{q}»: مكة مول مرّةً واحدة", got.count("مكة مول") == 1)
    check(f"«{q}»: لا يُعرض الاسمُ بلغتين", not any("|" in n for n in got))
check("Latin «City Mall» يجد سيتي مول", any(i["name"] == "سيتي مول" for i in srv.search("City Mall", "JO", amman, 5)))
check("«سيتى مول» (ى) يجد سيتي مول", any(i["name"] == "سيتي مول" for i in srv.search("سيتى مول", "JO", amman, 5)))
check("«المكة مول» (بزيادة «ال») يجد مكة مول",
      any(i["name"] == "مكة مول" for i in srv.search("المكة مول", "JO", amman, 5)))

algiers = (36.7538, 3.0588)
for q in ("الابيار", "الأبيار", "el biar", "El Biar"):
    got = srv.search(q, "DZ", algiers, 6)
    check(f"«{q}»: الأبيار مرّةً واحدة", sum(1 for i in got if i["name"] in ("الأبيار", "El Biar")) == 1)
check("«Alger» يجد الجزائر", any(i["name"] == "الجزائر" for i in srv.search("Alger", "DZ", None, 5)))

check("لا نتيجةَ من بلدٍ آخر (الأبيار من الأردن)", srv.search("الأبيار", "JO", amman, 5) == [])
check("ولا مكة مول من الجزائر", srv.search("مكة مول", "DZ", algiers, 5) == [])
check("حرفٌ واحدٌ لا يُسأل", srv.search("د", "JO", amman, 5) == [])
# **حرفٌ زائدٌ يقطع كلَّ ثلاثيّ**: «el biyar» لا يشارك «el biar» ثلاثيّاً واحداً فلم يكن يُسأل عنه أصلاً
for q in ("el biyar", "el biarr", "elbiar"):
    names = [i["name"] for i in srv.search(q, "DZ", algiers, 5)]
    check(f"«{q}» تجد الأبيار", "الأبيار" in names[:2])
check("بلدٌ مجهولٌ لا يُسأل", srv.search("مكة مول", "XX", None, 5) == [])

first = srv.search("مكة مول", "JO", amman, 5)
first[0]["name"] = "عبث"
again = srv.search("مكة مول", "JO", amman, 5)
check("ذاكرةُ الأجوبة تُعيد نسخةً لا الأصل", again[0]["name"] == "مكة مول")
check("ولكلِّ نتيجةٍ صنفٌ للأيقونة", all(i.get("cat") for i in again))

# **التسخينُ قبل الحركة** (أمرُ المالك ٢٠٢٦-١١-١٦): قبل التسخين 503 «warming» للبحث والصحّة، وبعده يجيبان
import json as _json
import threading as _threading
import urllib.error as _uerr
import urllib.request as _ureq
from http.server import ThreadingHTTPServer as _Server


def _get(port, path):
    try:
        with _ureq.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
            return r.status, _json.loads(r.read())
    except _uerr.HTTPError as e:
        return e.code, _json.loads(e.read())


srv._ready.clear()
_httpd = _Server(("127.0.0.1", 0), srv.Handler)
_port = _httpd.server_address[1]
_threading.Thread(target=_httpd.serve_forever, daemon=True).start()
code, body = _get(_port, "/search?q=%D9%85%D9%83%D8%A9&cc=JO")
check("قبل التسخين: البحثُ 503 «warming» (الخلفيّةُ تكمل على Mapbox بلا علامة توقّف)", code == 503 and body.get("detail") == "warming")
check("وقبل التسخين: الصحّةُ 503", _get(_port, "/health")[0] == 503)
srv.warm()
check("التسخينُ يمرّ بكلِّ اتصالٍ ويُعلِن جاهزيّتَه", srv._ready.is_set() and srv.warm_stats.get("queries") == len(srv.WARM_QUERIES) * srv.WORKERS)
check("والمجمّعُ كاملٌ بعده (لا اتصالَ محبوس)", srv._pool.qsize() == srv.WORKERS)
code, body = _get(_port, "/search?q=%D9%85%D9%83%D8%A9%20%D9%85%D9%88%D9%84&cc=JO")
check("بعد التسخين: البحثُ يجيب", code == 200 and any(i["name"] == "مكة مول" for i in body["items"]))
code, body = _get(_port, "/health")
check("وبعده: الصحّةُ تجيب بأرقام التسخين", code == 200 and "queries_s" in body.get("warm", {}))

# ── الخريطةُ المفتوحة (أمرُ المالك ١٨/١١ السابع): مقاطعُ الطرق للمطابقة، والمربّعاتُ من mbtiles
import gzip as _gzip
import json as _j

_roads = sqlite3.connect(srv.ROADS)
_roads.executescript("""
CREATE TABLE segments(id INTEGER PRIMARY KEY, cc TEXT, way INTEGER, cls TEXT, name TEXT, free INTEGER, oneway INTEGER, b0 REAL, b1 REAL, coords TEXT);
CREATE VIRTUAL TABLE seg_box USING rtree(id, x0, x1, y0, y1);
""")
# طريقٌ شرقيٌّ باتجاهٍ واحد (٩٠°) على خطِّ عرض 32.0، وطريقٌ شماليٌّ باتجاهين بعده بمئتي متر
_roads.execute("INSERT INTO segments VALUES (1,'LY',10,'primary','الشط',60,1,90,0,?)", (_j.dumps([[13.000, 32.0], [13.001, 32.0]]),))
_roads.execute("INSERT INTO seg_box VALUES (1, 13.000, 13.001, 32.0, 32.0)")
_roads.execute("INSERT INTO segments VALUES (2,'LY',11,'secondary','',50,0,0,0,?)", (_j.dumps([[13.003, 31.999], [13.003, 32.001]]),))
_roads.execute("INSERT INTO seg_box VALUES (2, 13.003, 13.003, 31.999, 32.001)")
_roads.commit()
_roads.close()
got = srv.match([(32.0001, 13.0005, 92.0), (32.0001, 13.0005, 270.0), (32.0, 13.0031, 180.0), (32.01, 13.0, None)])
check("المطابقةُ: نقطةٌ على الطريق باتجاهه ⇐ مقطعُه", got[0] == 1)
check("ونقطةٌ عكسَ طريقٍ باتجاهٍ واحد ⇐ لا مقطع", got[1] is None)
check("وطريقٌ باتجاهين يُطابَق عكسَ رسمه", got[2] == 2)
check("وما بعُد أكثرَ من ثلاثين متراً ⇐ لا مقطع", got[3] is None)
check("والمقاطعُ تعود بهندستها وسرعتها الحرّة", srv.segments([1, 99]) == {"1": {"free": 60, "coords": [[13.0, 32.0], [13.001, 32.0]]}})

_mb = sqlite3.connect(os.path.join(srv.DATA_DIR, "places.mbtiles"))
_mb.execute("CREATE TABLE tiles(zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB)")
_mb.execute("INSERT INTO tiles VALUES (14, 8780, ?, ?)", ((1 << 14) - 1 - 6512, _gzip.compress(b"pbf")))
_mb.commit()
_mb.close()
check("المربّعُ يُقرأ بعكس الصفّ (TMS)", _gzip.decompress(srv.tile("places", 14, 8780, 6512)) == b"pbf")
check("ومربّعٌ غائبٌ ⇐ لا شيء", srv.tile("places", 14, 8780, 6513) is None)
with _ureq.urlopen(f"http://127.0.0.1:{_port}/tiles/places/14/8780/6512.pbf", timeout=5) as r:
    check("وعبر HTTP: مضغوطاً كما بُني، برأس X-Tile-Encoding لا Content-Encoding",
          r.headers.get("X-Tile-Encoding") == "gzip" and r.headers.get("Content-Encoding") is None and _gzip.decompress(r.read()) == b"pbf")
_req = _ureq.Request(f"http://127.0.0.1:{_port}/match", data=_j.dumps({"points": [[32.0001, 13.0005, 92]]}).encode(), method="POST")
with _ureq.urlopen(_req, timeout=5) as r:
    check("و/match عبر HTTP", _j.loads(r.read()) == {"segs": [1]})

near = srv.nearby(32.0002, 13.0005, "LY")
check("«أين أنا؟»: المنطقةُ وقربُ المعلم الذي يعرفه الناس — لا المحلُّ الأقرب ولا الاسمُ اللاتينيّ",
      near["label"] == "تاجوراء، قرب مصحة ابن النفيس" and near["landmark"] == "مصحة ابن النفيس")
check("والشارعُ المسمّى تحت النقطة يُقرأ معها", near["street"] == "الشط")
check("وبعيداً عن كلِّ معلمٍ وشارع ⇐ المنطقةُ وحدَها لا «طرابلس» العامّة", srv.nearby(32.0080, 13.0130, "LY")["label"] == "تاجوراء")
check("ودولةٌ ليست من الثلاث ⇐ لا شيء", srv.nearby(32.0, 13.0, "EG")["label"] is None)
with _ureq.urlopen(f"http://127.0.0.1:{_port}/nearby?lat=32.0002&lng=13.0005&cc=ly", timeout=5) as r:
    check("و/nearby عبر HTTP", _j.loads(r.read())["label"] == "تاجوراء، قرب مصحة ابن النفيس")
try:
    _ureq.urlopen(f"http://127.0.0.1:{_port}/nearby?cc=LY", timeout=5)
    check("ونداءٌ بلا إحداثيّات ⇐ 400 لا انهيار", False)
except _ureq.HTTPError as exc:
    check("ونداءٌ بلا إحداثيّات ⇐ 400 لا انهيار", exc.code == 400)

_httpd.shutdown()

sys.exit(1 if failures else 0)
