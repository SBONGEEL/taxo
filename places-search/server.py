"""**بحثُ الأماكن من القرص** (قرارُ المالك ٢٠٢٦-١١-١٥) — فهرسُ SQLite FTS5 (trigram) مبنيٌّ خارج الخادم من OpenStreetMap وOverture،
يُقرأ للقراءة وحدَها، بلا مكتبةٍ خارجيّة؛ والذاكرةُ ذاكرةُ بايثون وذاكرةُ SQLite المؤقّتة (٣٢ MB لكلِّ اتصال، واتصالان) لا الفهرس.

GET /search?q=&cc=JO&lat=&lng=&limit=10 → {"items":[{id,name,name_en,kind,context,lat,lng,distance_m,src}]}
GET /health → {"ok":true,"places":N}   (و503 {"detail":"warming"} حتى ينتهي التسخين — وكذا /search)
"""

from __future__ import annotations

import difflib
import json
import math
import os
import re
import sqlite3
import queue
import threading
import time
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

INDEX = os.environ.get("PLACES_INDEX", "/data/places.sqlite")
COUNTRIES = {"JO", "DZ", "LY"}

TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي", "ی": "ي", "ھ": "ه"})
#: **كلماتٌ لا تميّز** — تُحذف من الطرفين قبل قياس الشبه، فـ«مول» لا يرفع كلَّ مولٍ إلى رأس القائمة
GENERIC = {"شارع", "ش", "street", "st", "rue", "حي", "منطقه", "مدينه", "دوار", "طريق", "road", "ال"}
KIND_BONUS = {"city": 0.20, "town": 0.16, "district": 0.14, "neighbourhood": 0.14, "village": 0.08, "locality": 0.05,
              "poi": 0.06, "street": 0.06, "building": 0.02}

#: **عمّالٌ ثابتون واتصالاتٌ ثابتة** — نصفُ معالجٍ لا يُسرّعه عاملٌ ثالث، وطابورٌ يطول يُبطئ الجميع؛ فما زاد ينتظر ثانيةً ونصفاً
#: ثمّ يُردّ 503 في الحال — **والخلفيّةُ تُكمل على Mapbox** بدل أن تنتظر
WORKERS = int(os.environ.get("PLACES_WORKERS", "2"))
WAIT_SECONDS = 1.5
_pool: "queue.LifoQueue[sqlite3.Connection]" = queue.LifoQueue()


def norm(text: str) -> str:
    text = TASHKEEL.sub("", text or "").translate(FOLD).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _open() -> sqlite3.Connection:
    if True:
        db = sqlite3.connect(f"file:{INDEX}?mode=ro&immutable=1", uri=True, check_same_thread=False)
        db.execute("PRAGMA cache_size=-32000")
        db.execute("PRAGMA mmap_size=0")
        db.row_factory = sqlite3.Row
        # **مفرداتُ الفهرس في الذاكرة المؤقّتة** — كم اسماً يحمل كلَّ ثلاثيّة؛ فيُسأل الفهرسُ بأندرها لا بـ«مول» المشترَكة في عشرات الآلاف
        db.execute("CREATE VIRTUAL TABLE temp.vocab USING fts5vocab(main, 'fts', 'row')")
    return db


class Busy(Exception):
    pass


class _Lease:
    def __enter__(self) -> sqlite3.Connection:
        try:
            self.db = _pool.get(timeout=WAIT_SECONDS)
        except queue.Empty as exc:
            raise Busy from exc
        return self.db

    def __exit__(self, *exc) -> None:
        _pool.put(self.db)


def _quote(token: str) -> str:
    return '"' + token.replace('"', '""') + '"'


def _trigrams(text: str) -> list[str]:
    grams: list[str] = []
    for word in text.split():
        grams.extend(word[i:i + 3] for i in range(max(len(word) - 2, 0)))
        if len(word) == 3:
            grams.append(word)
    return list(dict.fromkeys(g for g in grams if len(g) == 3))


def _core(text: str) -> str:
    words = [w[2:] if w.startswith("ال") and len(w) > 4 else w for w in text.split()]
    return " ".join(w for w in words if w not in GENERIC) or text


#: **كلماتٌ عامّةٌ وزنُها خفيف** — «مطار» و«airport» لا تختار مطاراً من مطار؛ الاسمُ العلَمُ هو الذي يختار
COMMON = {"مطار", "airport", "aeroport", "international", "الدولي", "دولي", "مول", "mall", "جامعه", "university",
          "universite", "مستشفي", "hospital", "hopital", "chu", "centre", "center", "commercial", "مركز", "سوق", "souk",
          "souq", "حي", "hay", "cite", "مدرسه", "school", "مسجد", "mosque", "فندق", "hotel", "of", "de", "du", "la", "el", "al"}
STREET_WORDS = {"شارع", "street", "st", "rue", "boulevard", "bd", "avenue", "av", "طريق", "road"}
#: **الدوّار** (٢٠٢٦-١١-١٦، أمرُ المالك §١٠٤/٣) — في OSM طريقٌ (`kind = street`)، فكان يُعاقب كشارعٍ لم يُطلب: «دوار الداخلية» أعاد
#: «رم للبصريات دوار الداخليه» قبل الدوّار. **ومن كتب «دوار» طلب دوّاراً** — فلا عقوبةَ ويُزاد كقصد الصنف
ROUNDABOUT_WORDS = {"دوار", "roundabout", "rond", "rondpoint", "circle"}

#: **قصدُ الصنف** (٢٠٢٦-١١-١٦) — «مطار هواري بومدين» يطلب مطاراً، فبلدةٌ اسمُها «هواري بومدين» لا تتقدّمه.
#: كلمةُ الصنف خفيفةٌ في الشبه (`COMMON`) لأنها لا تختار مطاراً من مطار، **لكنها تختار المطارَ من البلدة** — فتُقرأ هنا قصداً
CATEGORY = {"مطار": "air", "airport": "air", "aeroport": "air", "جامعه": "uni", "university": "uni", "universite": "uni",
            "مستشفي": "hos", "hospital": "hos", "hopital": "hos", "chu": "hos", "مول": "mall", "mall": "mall"}
#: **عاصمةُ كلِّ بلد** — ميلٌ خفيفٌ حين لا موقعَ مع البحث (اللوحة، أو راكبٌ بلا إذن موقع): «مقام الشهيد» بأسمائه العشرين في
#: الجزائر يبدأ بالذي في العاصمة. وموقعُ الراكب إن وصل يغلبه (وزنُه ١٢٪ لا ٤٪)
CAPITALS = {"JO": (31.9539, 35.9106), "DZ": (36.7538, 3.0588), "LY": (32.8872, 13.1913)}
#: **سميُّ المعلَم** — مكانٌ من Overture يحمل اسمَ معلَمٍ كبيرٍ (OSM، رتبة ≥ ٨) ويقع أبعدَ من هذا عنه: مكتبُ سيّاراتٍ أو محلٌّ تسمّى
#: باسم المطار، لا المطار. **يُسقط** ولا يُؤخَّر، لأنه يُقرأ في القائمة «مطار الملكة علياء» ويأخذ الراكبَ إلى الجبيهة
NAMESAKE_KM = 5.0


#: **الأرقامُ بشكليها** (٢٠٢٦-١١-١٦) — الفهرسُ يحمل «جامعة الجزائر ١» بالهنديّة والراكبُ يكتب «1»؛ فيُسأل بالشكلين ويُقارَن بالقيمة
EASTERN = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
WESTERN = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _numbers(text: str) -> set[str]:
    return {str(int(d)) for d in re.findall(r"\d+", text)}


def _categories(text: str) -> set[str]:
    return {CATEGORY[w] for w in text.split() if w in CATEGORY}


def _word_cover(query: str, name: str) -> float:
    """**تغطيةُ كلمات الاستعلام** في الاسم، كلُّ كلمةٍ بأقرب كلمةٍ إليها (فيُتسامح في حرفٍ أو اثنين)، والعامّةُ بوزنٍ خفيف."""
    qwords = [w for w in query.split() if w]
    nwords = name.split()
    if not qwords or not nwords:
        return 0.0
    got = weight = 0.0
    for w in qwords:
        wt = 0.25 if w in COMMON else 1.0
        best = max(difflib.SequenceMatcher(None, w, n).ratio() for n in nwords)
        best = max(best, max((difflib.SequenceMatcher(None, w, n[2:]).ratio() for n in nwords if n.startswith("ال")), default=0))
        got += wt * (best if best >= 0.72 else 0.0)
        weight += wt
    extra = max(len([n for n in nwords if n not in COMMON]) - len([w for w in qwords if w not in COMMON]), 0)
    return got / weight - 0.03 * extra


def _similarity(query: str, names: list[str]) -> float:
    query = query.translate(WESTERN)
    names = [n.translate(WESTERN) for n in names]
    q = _core(query)
    best = 0.0
    for name in names:
        n = name  # **مطويٌّ سلفاً** في الفهرس (`nalt`)
        c = _core(n)
        score = max(difflib.SequenceMatcher(None, q, c).ratio(), difflib.SequenceMatcher(None, query, n).ratio(),
                    0.97 * _word_cover(query, n))
        if n.startswith(query) or c.startswith(q):
            score = max(score, 0.9 + 0.1 * len(q) / max(len(c), 1))
        elif query in n:
            score = max(score, 0.75 + 0.15 * len(query) / max(len(n), 1))
        best = max(best, score)
    return best


#: **المسافةُ التي يُعدّ فيها الاسمُ نفسُه المكانَ نفسَه** — حيٌّ أو مدينةٌ تتسع، ومحلٌّ أو معلمٌ نقطة
SAME_PLACE_KM = {"city": 3.0, "town": 2.0, "district": 1.5, "neighbourhood": 1.0, "village": 1.0, "locality": 1.0}
SAME_POINT_KM = 0.5
#: **والمعلمُ الكبيرُ يتسع كالحيّ** — مولٌ أو جامعةٌ أو مستشفى أو مطارٌ نقطتاه في OSM وOverture قد تتباعدان كيلومترين
#: («مكة مول ‹أم السماق›» و«مكة مول ‹التلاع الشرقي›»)، ولا يقوم معلمان كبيران بالاسم نفسِه في كيلومترين ونصف
SAME_SITE_KM = {"mall": 2.5, "university": 2.5, "hospital": 2.0, "airport": 5.0}


def _bare(word: str) -> str:
    """الكلمةُ بلا «ال» في أوّلها — «الداخليه» و«داخليه» واحدة"""
    return word[2:] if word.startswith("ال") and len(word) > 4 else word


def _words_present(words: list[str], nalt: str) -> bool:
    """**كلُّ كلمةٍ مطلوبةٍ في الاسم** — حرفاً أو بخطأ إملاءٍ واحد («الداخليى» تجد «الداخليه»)"""
    have = [_bare(w) for w in nalt.replace(" | ", " ").split()]
    for word in words:
        if word in have:
            continue
        if not any(len(word) >= 4 and difflib.SequenceMatcher(None, word, own).ratio() >= 0.8 for own in have):
            return False
    return True


def _parts(text: str | None) -> list[str]:
    return [part.strip() for part in (text or "").split("|") if part.strip()]


def _display_name(row: sqlite3.Row) -> str:
    """**اسمٌ واحدٌ يُعرض** — بعضُ صفوف Overture تحمل اللغتين في حقلٍ واحد («Mecca Mall | مكة مول»)، فيُعرض العربيُّ منهما."""
    parts = _parts(row["name_ar"]) or _parts(row["name_en"]) or _parts(row["alt"])
    arabic = [part for part in parts if re.search(r"[\u0600-\u06FF]", part)]
    return (arabic or parts or [""])[0]


def _name_set(row: sqlite3.Row, name: str) -> set[str]:
    return {norm(n) for n in [name, *_parts(row["name_ar"]), *_parts(row["name_en"])] if n}


def _radius(row: sqlite3.Row) -> float:
    return SAME_PLACE_KM.get(row["kind"]) or SAME_SITE_KM.get(_category_of(row), SAME_POINT_KM)


def _duplicate(row: sqlite3.Row, name: str, context: str, kept: list) -> bool:
    """**المكانُ نفسُه مرّتين** (أمرُ المالك §١٠٤/٧) — من OSM وOverture، أو بالعربيّة والإنجليزيّة («الأبيار» و«El Biar»، «مكة مول»
    و«Mecca Mall»)، أو باسمه وحيّه نفسَيهما («باب الزوار ‹حي دوزي 4›» مرّتين). الأوّلُ في الترتيب هو الباقي."""
    names = _name_set(row, name)
    own = norm(name)
    for other, other_names, other_name, other_context in kept:
        if own == other_name and context and context == other_context:
            return True
        if names & other_names:
            radius = max(_radius(row), _radius(other))
            if _km(row["lat"], row["lng"], other["lat"], other["lng"]) <= radius:
                return True
    return False


#: **صنفُ الأيقونة** (§١٠٤/١١) — من نوع الصفّ ثمّ من كلماتِ اسمه؛ والفهرسُ لا يحمل صنفَ المعلم، فالاسمُ هو الدليل
CAT_WORDS = (
    ("airport", {"مطار", "airport", "aeroport"}), ("mall", {"مول", "mall"}),
    ("hospital", {"مستشفي", "hospital", "hopital", "chu", "clinique"}), ("university", {"جامعه", "university", "universite"}),
    ("mosque", {"مسجد", "جامع", "mosque", "mosquee"}), ("restaurant", {"مطعم", "restaurant", "مقهي", "cafe", "كافيه", "coffee"}),
    ("hotel", {"فندق", "hotel"}), ("school", {"مدرسه", "school", "ecole", "lycee"}), ("pharmacy", {"صيدليه", "pharmacy", "pharmacie"}),
    ("bank", {"بنك", "bank", "banque"}), ("fuel", {"وقود", "بنزين", "fuel", "petrol", "naftal"}),
    ("park", {"حديقه", "منتزه", "park", "parc", "jardin"}),
)


def _category_of(row: sqlite3.Row) -> str:
    words = set(row["nalt"].replace(" | ", " ").split())
    # **الطريقُ طريقٌ أوّلاً** — «شارع مطار الملكة علياء» شارعٌ لا مطار، والدوّارُ طريقٌ اسمُه «دوار»؛ ومحلٌّ باسم الدوّار محلّ
    if row["kind"] == "street":
        return "roundabout" if words & ROUNDABOUT_WORDS else "street"
    for cat, marks in CAT_WORDS:
        if words & marks:
            return cat
    if row["kind"] == "street":
        return "street"
    if row["kind"] in ("city", "town", "village", "locality"):
        return "city"
    if row["kind"] in ("district", "neighbourhood"):
        return "district"
    return "place"


def _km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    return math.hypot((lat2 - lat1) * 111.0, (lng2 - lng1) * 111.0 * math.cos(math.radians(lat1)))


#: **ذاكرةُ الأجوبة** (§١٠٤/٨) — مفتاحُها النصُّ المطويُّ والبلدُ والموقعُ مقرَّباً إلى ~١ كم، فراكبان في الحيّ نفسِه يتشاركانها؛
#: والفهرسُ لا يتغيّر وهو قيد التشغيل (`immutable=1`) فلا يبلى ما فيها. **ولا يُكتب منها شيءٌ في سجلّ**
CACHE_SIZE = 4096
#: **سقفُ الثلاثيّ النادر** — عددُ الأماكن التي تحمله؛ وما فوقه شائعٌ لا يُسأل به في البحث المتسامح
COMMON_GRAM = 6000
_cache: "OrderedDict[tuple, list[dict]]" = OrderedDict()
_cache_lock = threading.Lock()


def _join_particles(query: str) -> str:
    """الكلمةُ القصيرة (≤ ٣ أحرف، لا رقم) موصولةً بالتي بعدها — «هواري بو مدين» ⇐ «هواري بومدين»، «ابو نصير» ⇐ «ابونصير»."""
    words = query.split()
    out: list[str] = []
    i = 0
    while i < len(words):
        w = words[i]
        if i + 1 < len(words) and len(w) <= 3 and not w.isdigit() and not words[i + 1].isdigit():
            out.append(w + words[i + 1])
            i += 2
            continue
        out.append(w)
        i += 1
    return " ".join(out)


def search(q: str, cc: str, near: tuple[float, float] | None, limit: int) -> list[dict]:
    query = norm(q)
    if len(query.replace(" ", "")) < 2 or cc not in COUNTRIES:
        return []
    key = (query, cc, (round(near[0], 2), round(near[1], 2)) if near else None, limit)
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return [dict(item) for item in _cache[key]]
    if _pool.qsize() == 0 and not _started:
        _fill()
    with _Lease() as db:
        items = _search(db, query, q, cc, near, limit)
        # **الاسمُ المفصولُ خطأً** (أمرُ المالك ٢٠٢٦-١١-١٧): «مطار هواري بو مدين» والفهرسُ يحمل «بومدين» كلمةً واحدة — فـ«بو» لا تطابق
        # شيئاً، ويسقط عن المطار ما يناله الاسمُ الصحيح (التطابقُ والبداية)، فتتقدّمه «محطة مطار هواري بومدين» بقصرها.
        # فيُسأل أيضاً بالكلمة القصيرة موصولةً بما بعدها، **ويُؤخذ الأعلى صدراً** — وصلٌ خاطئٌ («بن عكنون» ⇐ «بنعكنون») أدنى فلا يغلب
        joined = _join_particles(query)
        if joined != query:
            other = _search(db, joined, q, cc, near, limit)
            if other and (not items or other[0]["score"] > items[0]["score"]):
                items = other
    with _cache_lock:
        _cache[key] = items
        if len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return [dict(item) for item in items]


#: **بحوثُ التسخين** (أمرُ المالك ٢٠٢٦-١١-١٦): أسماءٌ حقيقيّةٌ من الدول الثلاث بأطوالٍ مختلفة — تمرّ بالفهرس وبمفردات الثلاثيّات
#: وبمسار الشبه، **على كلِّ اتصالٍ في المجمّع** (ذاكرةُ SQLite المؤقّتة لكلِّ اتصالٍ وحدَه)، ولا تُكتب في ذاكرة النتائج
WARM_QUERIES = (
    ("با", "JO", (31.95, 35.91)), ("دوار الداخلية", "JO", (31.95, 35.91)), ("مكه مول", "JO", (31.95, 35.91)),
    ("مستشفى", "JO", (32.55, 35.85)), ("Amman", "JO", None), ("الجامعه الاردنيه", "JO", None),
    ("Alger", "DZ", (36.75, 3.06)), ("باب الزوار", "DZ", (36.72, 3.18)), ("حي الصنوبر البحري", "DZ", (36.75, 3.06)),
    ("Oran", "DZ", None), ("طرابلس", "LY", (32.89, 13.19)), ("بنغازي", "LY", None),
)

#: **الخدمةُ لا تقبل بحثاً حقيقيّاً قبل أن تسخن** — المنفذُ مفتوحٌ من الثانية الأولى ويجيب 503 «warming»، والخلفيّةُ تقرأ 503
#: «مشغولةً لا ساقطة» فتكمل على Mapbox بلا علامة توقّف (`services/maps.py`)؛ **فلا يرى راكبٌ ثانيتين في الدقيقة الأولى**
_ready = threading.Event()
warm_stats: dict = {}


def warm() -> None:
    try:
        _warm()
    finally:
        _ready.set()


def _warm() -> None:
    """**يُقرأ الفهرسُ إلى ذاكرة النظام ثمّ تُجرى بحوثُ التسخين على كلِّ اتصال**، وبعدها وحدَها تُقبل الحركة (§١٠٤/٣).
    قبل هذا كان أوّلُ حرفٍ بعد إعادة الحاوية يقرأ القرصَ صفحةً صفحة: «با» ١٫١ ث و«Alger» ٣٫٤ ث باردين، والدقيقةُ الأولى تبلغ ثانيتين."""
    started = time.monotonic()
    try:
        with open(INDEX, "rb") as handle:
            while handle.read(8 << 20):
                pass
    except OSError:
        pass
    read_done = time.monotonic()
    leased = [_pool.get() for _ in range(WORKERS)]
    failed = 0
    try:
        for db in leased:
            for q, cc, near in WARM_QUERIES:
                try:
                    _search(db, norm(q), q, cc, near, 10)
                except Exception:  # noqa: BLE001 — **بحثُ تسخينٍ يسقط لا يُبقي الخدمةَ 503 إلى الأبد**؛ يُعدّ ويُطبع
                    failed += 1
    finally:
        for db in leased:
            _pool.put(db)
    warm_stats.update(failed=failed)
    warm_stats.update(read_s=round(read_done - started, 2), queries_s=round(time.monotonic() - read_done, 2),
                      queries=len(WARM_QUERIES) * WORKERS)
    _ready.set()
    print(f"places-search: ساخنة — قراءةُ الفهرس {warm_stats['read_s']} ث، و{warm_stats['queries']} بحثَ تسخينٍ في "
          f"{warm_stats['queries_s']} ث، وسقط منها {warm_stats.get('failed', 0)}", flush=True)


_started = False


def _fill() -> None:
    global _started
    _started = True
    for _ in range(WORKERS):
        _pool.put(_open())


def _search(db: sqlite3.Connection, query: str, q: str, cc: str, near: tuple[float, float] | None, limit: int) -> list[dict]:
    found: dict[int, sqlite3.Row] = {}
    country = f'c:"qq{cc.lower()}qq"'
    sql = "SELECT p.* FROM fts JOIN places p ON p.id = fts.rowid WHERE fts MATCH ? ORDER BY fts.rank LIMIT ?"
    if len(query) >= 3:
        phrase = f"{country} AND n:{_quote(query)}"
        if query.translate(EASTERN) != query:
            phrase = f"{country} AND (n:{_quote(query)} OR n:{_quote(query.translate(EASTERN))})"
        for row in db.execute(sql, (phrase, 150)):
            found[row["id"]] = row
        # **والأهمُّ أوّلاً بين المطابِق** — bm25 يفضّل الاسمَ القصير، فمطارٌ بأسمائه الخمسة يغرق تحت مئة مكتبٍ يحمل اسمَه
        for row in db.execute(sql.replace("ORDER BY fts.rank", "ORDER BY p.rank DESC, fts.rank"), (phrase, 40)):
            found.setdefault(row["id"], row)
    grams = _trigrams(query)
    # **حرفٌ زائدٌ يقطع كلَّ ثلاثيّ** («biyar» و«biar» لا يشتركان في ثلاثيٍّ واحد) — فللاستعلام القصير تُسأل ثلاثيّاتُ كلِّ صورةٍ
    # منه بحرفٍ محذوف أيضاً؛ والقياسُ بعدها (`_similarity`) هو الحَكَم، فلا يدخل ما لا يشبه
    if 0 < len(grams) <= 6:
        for word in query.split():
            if 4 <= len(word) <= 8:
                for at in range(len(word)):
                    grams += [g for g in _trigrams(word[:at] + word[at + 1:]) if g not in grams]
    if grams and len(found) < 60:
        marks = ",".join("?" * len(grams))
        counts = dict(db.execute(f"SELECT term, doc FROM temp.vocab WHERE term IN ({marks})", grams).fetchall())
        rare = sorted((g for g in grams if counts.get(g)), key=lambda g: counts[g])[:8]
        # **ثلاثيٌّ في كلِّ مكانٍ لا يدلّ على شيء** («el » و«ال ») — يملأ حدَّ الثلاثمئة بما لا يشبه المطلوب فيغيب المقصود:
        # «el biyar» لم يجد «El Biar». يُسقط ما زاد عن السقف ما بقي ثلاثيّان نادران يُسأل بهما
        uncommon = [g for g in rare if counts[g] <= COMMON_GRAM]
        if len(uncommon) >= 2:
            rare = uncommon
        if rare:
            fuzzy = f"{country} AND n:(" + " OR ".join(_quote(g) for g in rare) + ")"
            for row in db.execute(sql, (fuzzy, 300)):
                found.setdefault(row["id"], row)
    if not found and len(query) <= 3:
        for row in db.execute("SELECT * FROM places WHERE cc = ? AND (name_ar LIKE ? OR name_en LIKE ?) "
                              "ORDER BY rank DESC LIMIT 50", (cc, q + "%", q + "%")):
            found[row["id"]] = row

    # **غربالٌ رخيصٌ قبل القياس الغالي** — نسبةُ ما يشترك فيه الاسمُ من ثلاثيّات الاستعلام؛ فلا يُقاس بـdifflib إلا أقربُ ثمانين
    qgrams = set(_trigrams(query))
    if qgrams and len(found) > 80:
        def overlap(row: sqlite3.Row) -> float:
            return len(qgrams & set(_trigrams(row["nalt"]))) / len(qgrams)
        found = dict(sorted(found.items(), key=lambda kv: (-overlap(kv[1]), -kv[1]["rank"], kv[1]["src"] != "osm"))[:80])
    wants_street = any(w in STREET_WORDS for w in query.split())
    wants_roundabout = any(w in ROUNDABOUT_WORDS for w in query.split())
    #: **ما بعد «دوار» في الاستعلام** — الدوّارُ المقصودُ يحمله، و«دوار الكمالية» لا يتقدّم «… دوار الداخليه» لأنه دوّارٌ فحسب
    qrest = [_bare(w) for w in query.split() if w not in ROUNDABOUT_WORDS and _bare(w)]
    qcore = _core(query.translate(WESTERN))
    wanted = _categories(query)
    digits = _numbers(query)
    scored = []
    for row in found.values():
        names = row["nalt"].split(" | ")
        sim = _similarity(query, names)
        if sim < 0.55:
            continue
        score = sim + KIND_BONUS.get(row["kind"], 0) + row["rank"] * 0.01
        if wanted:
            score += 0.04 if wanted & _categories(row["nalt"]) else -0.12
        if row["src"] == "osm":  # **OSM محرَّرٌ بيد** — Overture يحمل مكاتبَ تتسمّى باسم المعلَم وتقع بعيداً عنه
            score += 0.06
        if digits:  # **«جامعة الجزائر 1» ليست «2»** — الرقمُ في الاستعلام يُطابَق حرفاً
            have = _numbers(row["nalt"])
            score += 0.06 if digits <= have else -0.25 if have else -0.12  # رقمٌ آخرُ أبعدُ من لا رقم
        roundabout = row["kind"] == "street" and any(w in ROUNDABOUT_WORDS for w in row["nalt"].split())
        on_target = roundabout and _words_present(qrest, row["nalt"])
        if wants_roundabout and on_target:
            score += 0.04
        elif (row["kind"] == "street") != wants_street:
            score -= 0.15 if row["kind"] == "street" else 0.08
        # **الاسمُ هو المطلوبُ نفسُه** لا ما يحمله في ذيله: «دوار الداخلية» قبل «رم للبصريات دوار الداخليه»
        # **ولا لشارعٍ لم يُطلب**: «Queen Alia Airport Street» يساوي «Queen Alia Airport» بعد حذف «Street» — والمطلوبُ المطار
        street_unasked = row["kind"] == "street" and not wants_street and not (wants_roundabout and on_target)
        if qcore and not street_unasked and any(_core(n.translate(WESTERN)) == qcore for n in names):
            score += 0.10
        dist = None
        if near:
            dist = _km(near[0], near[1], row["lat"], row["lng"])
            score += 0.12 * math.exp(-dist / 15.0)
        elif cc in CAPITALS:
            score += 0.04 * math.exp(-_km(*CAPITALS[cc], row["lat"], row["lng"]) / 30.0)
        scored.append((score, dist, row))
    scored.sort(key=lambda s: -s[0])
    landmarks = [(_core(n), row) for _, _, row in scored if row["src"] == "osm" and row["rank"] >= 8 and row["kind"] == "poi"
                 for n in row["nalt"].split(" | ") if n]

    def namesake(row: sqlite3.Row) -> bool:
        if row["src"] != "overture":
            return False
        for name in row["nalt"].split(" | "):
            core = _core(name)
            words = set(core.split())
            for mark, big in landmarks:
                same = len(mark) >= 6 and len(core) >= 6 and (mark in core or core in mark)
                if not same:
                    # **أو كلماتُه المميِّزةُ كلُّها والصنفُ نفسُه**: «مطار الملكة علياء _الأردن_عمان» مكتبٌ في صويلح لا المطار
                    own = {w for w in mark.split() if w not in COMMON}
                    same = bool(own) and len("".join(own)) >= 6 and own <= words                         and bool(_categories(mark) & _categories(core))
                if same and _km(big["lat"], big["lng"], row["lat"], row["lng"]) > NAMESAKE_KM:
                    return True
        return False

    scored = [s for s in scored if not namesake(s[2])]

    items, kept = [], []
    for score, dist, row in scored:
        name = _display_name(row)
        context = [c for c in (row["ctx_local"], row["ctx_city"]) if c and c != name]
        if _duplicate(row, name, "، ".join(dict.fromkeys(context)), kept):
            continue
        kept.append((row, _name_set(row, name), norm(name), "، ".join(dict.fromkeys(context))))
        items.append({
            "id": f"{row['src']}:{row['id']}", "name": name, "name_en": row["name_en"], "kind": row["kind"],
            "context": "، ".join(dict.fromkeys(context)), "lat": round(row["lat"], 6), "lng": round(row["lng"], 6),
            "distance_m": int(dist * 1000) if dist is not None else None, "src": row["src"],
            "cat": _category_of(row),
            "score": round(score, 3),
        })
        if len(items) >= limit:
            break
    return items


# ───────────────────────── الخريطةُ المفتوحة (أمرُ المالك ٢٠٢٦-١١-١٨ السابع) — مربّعاتٌ ومطابقةُ مقاطع، من القرص وحدَه
DATA_DIR = os.path.dirname(os.environ.get("PLACES_INDEX", "/data/places.sqlite"))
ROADS = os.environ.get("ROADS_INDEX", os.path.join(DATA_DIR, "roads.sqlite"))
MATCH_M = 30.0
MATCH_HEADING = 50.0


def _ro(path: str) -> sqlite3.Connection | None:
    """اتّصالٌ للقراءة لكلِّ طلب — رخيصٌ على ملفٍّ ثابت، ولا يتشارك خيطان اتّصالاً."""
    if not os.path.exists(path):
        return None
    return sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)


def tile(layer: str, z: int, x: int, y: int) -> bytes | None:
    db = _ro(os.path.join(DATA_DIR, f"{layer}.mbtiles"))
    if db is None:
        return None
    try:
        row = db.execute("SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                         (z, x, (1 << z) - 1 - y)).fetchone()
        return row[0] if row else None
    finally:
        db.close()


def _seg_metres(lat: float, lng: float, coords: list) -> float:
    """أقصرُ مسافةٍ من نقطةٍ إلى خطِّ المقطع (مستوٍ محلّيّ — يكفي لثلاثين متراً)."""
    kx, ky = 111_320 * math.cos(math.radians(lat)), 110_540
    best = float("inf")
    for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
        ax, ay = (x1 - lng) * kx, (y1 - lat) * ky
        bx, by = (x2 - lng) * kx, (y2 - lat) * ky
        dx, dy = bx - ax, by - ay
        t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


def match(points: list) -> list:
    """**أقربُ مقطعِ طريقٍ رئيسيٍّ** لكلِّ نقطة (≤ ٣٠ م، والاتجاهُ يوافق إن عُرف) — أو `None`. **ولا هويّةَ في المدخل ولا في السجلّ.**"""
    db = _ro(ROADS)
    if db is None:
        return [None] * len(points)
    out = []
    try:
        dlat = MATCH_M / 110_540
        for lat, lng, heading in points[:5000]:
            dlng = MATCH_M / (111_320 * max(math.cos(math.radians(lat)), 0.2))
            rows = db.execute(
                "SELECT s.id, s.b0, s.oneway, s.coords FROM seg_box b JOIN segments s ON s.id = b.id "
                "WHERE b.x0 <= ? AND b.x1 >= ? AND b.y0 <= ? AND b.y1 >= ?",
                (lng + dlng, lng - dlng, lat + dlat, lat - dlat)).fetchall()
            best, best_d = None, MATCH_M
            for seg_id, b0, oneway, coords in rows:
                if heading is not None:
                    diff = abs((heading - b0 + 180) % 360 - 180)
                    if diff > MATCH_HEADING and (oneway or abs(diff - 180) > MATCH_HEADING):
                        continue
                d = _seg_metres(lat, lng, json.loads(coords))
                if d < best_d:
                    best, best_d = seg_id, d
            out.append(best)
    finally:
        db.close()
    return out


def segments(ids: list) -> dict:
    db = _ro(ROADS)
    if db is None:
        return {}
    try:
        found = {}
        for seg_id in ids[:2000]:
            row = db.execute("SELECT free, coords FROM segments WHERE id=?", (int(seg_id),)).fetchone()
            if row:
                found[str(seg_id)] = {"free": row[0], "coords": json.loads(row[1])}
        return found
    finally:
        db.close()


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        args = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if url.path in ("/health", "/search") and not _ready.is_set():
                return self._send(503, {"detail": "warming"})
            if url.path == "/health":
                if not _started:
                    _fill()
                with _Lease() as db:
                    count = db.execute("SELECT count(*) FROM places").fetchone()[0]
                return self._send(200, {"ok": True, "places": count, "warm": warm_stats})
            if url.path.startswith("/tiles/"):
                parts = url.path.split("/")
                if len(parts) != 6 or parts[2] != "places" or not parts[5].endswith(".pbf"):
                    return self._send(404, {"detail": "not found"})
                data = tile(parts[2], int(parts[3]), int(parts[4]), int(parts[5][:-4]))
                if data is None:
                    self.send_response(204)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/x-protobuf")
                # **رأسٌ خاصٌّ لا `Content-Encoding`** — فلا يفكّه عميلُ الخلفيّة؛ والخلفيّةُ تُعلنه للهاتف كما هو
                if data[:2] == bytes((0x1F, 0x8B)):
                    self.send_header("X-Tile-Encoding", "gzip")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if url.path == "/search":
                near = None
                if args.get("lat") and args.get("lng"):
                    near = (float(args["lat"]), float(args["lng"]))
                limit = max(1, min(int(args.get("limit", 10)), 20))
                return self._send(200, {"items": search(args.get("q", "")[:80], args.get("cc", "").upper(), near, limit)})
            return self._send(404, {"detail": "not found"})
        except Busy:
            return self._send(503, {"detail": "busy"})
        except (ValueError, sqlite3.Error) as exc:
            return self._send(400, {"detail": str(exc)[:120]})

    def do_POST(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        try:
            length = min(int(self.headers.get("Content-Length") or 0), 2_000_000)
            body = json.loads(self.rfile.read(length) or b"{}")
            if url.path == "/match":
                return self._send(200, {"segs": match([(float(p[0]), float(p[1]), None if p[2] is None else float(p[2]))
                                                         for p in body.get("points", [])])})
            if url.path == "/segments":
                return self._send(200, {"segments": segments(body.get("ids", []))})
            return self._send(404, {"detail": "not found"})
        except (ValueError, TypeError, IndexError, sqlite3.Error) as exc:
            return self._send(400, {"detail": str(exc)[:120]})

    def log_message(self, *_args) -> None:  # **لا نصَّ بحثٍ في السجلّ** — ما يكتبه الراكبُ ليس للسجلّات
        return


def main() -> None:
    port = int(os.environ.get("PORT", "8090"))
    _fill()
    threading.Thread(target=warm, daemon=True).start()
    ThreadingHTTPServer.daemon_threads = True
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
