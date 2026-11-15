"""**بحثُ الأماكن من القرص** (قرارُ المالك ٢٠٢٦-١١-١٥) — فهرسُ SQLite FTS5 (trigram) مبنيٌّ خارج الخادم من OpenStreetMap وOverture،
يُقرأ للقراءة وحدَها، بلا مكتبةٍ خارجيّة؛ والذاكرةُ ذاكرةُ بايثون وذاكرةُ SQLite المؤقّتة (٣٢ MB لكلِّ اتصال، واتصالان) لا الفهرس.

GET /search?q=&cc=JO&lat=&lng=&limit=10 → {"items":[{id,name,name_en,kind,context,lat,lng,distance_m,src}]}
GET /health → {"ok":true,"places":N}
"""

from __future__ import annotations

import difflib
import json
import math
import os
import re
import sqlite3
import queue
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


def _km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    return math.hypot((lat2 - lat1) * 111.0, (lng2 - lng1) * 111.0 * math.cos(math.radians(lat1)))


def search(q: str, cc: str, near: tuple[float, float] | None, limit: int) -> list[dict]:
    query = norm(q)
    if len(query.replace(" ", "")) < 2 or cc not in COUNTRIES:
        return []
    if _pool.qsize() == 0 and not _started:
        _fill()
    with _Lease() as db:
        return _search(db, query, q, cc, near, limit)


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
        for row in db.execute(sql, (phrase, 150)):
            found[row["id"]] = row
        # **والأهمُّ أوّلاً بين المطابِق** — bm25 يفضّل الاسمَ القصير، فمطارٌ بأسمائه الخمسة يغرق تحت مئة مكتبٍ يحمل اسمَه
        for row in db.execute(sql.replace("ORDER BY fts.rank", "ORDER BY p.rank DESC, fts.rank"), (phrase, 40)):
            found.setdefault(row["id"], row)
    grams = _trigrams(query)
    if grams and len(found) < 60:
        marks = ",".join("?" * len(grams))
        counts = dict(db.execute(f"SELECT term, doc FROM temp.vocab WHERE term IN ({marks})", grams).fetchall())
        rare = sorted((g for g in grams if counts.get(g)), key=lambda g: counts[g])[:8]
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
    digits = set(re.findall(r"\d+", query))
    scored = []
    for row in found.values():
        names = row["nalt"].split(" | ")
        sim = _similarity(query, names)
        if sim < 0.55:
            continue
        score = sim + KIND_BONUS.get(row["kind"], 0) + row["rank"] * 0.01
        if row["src"] == "osm":  # **OSM محرَّرٌ بيد** — Overture يحمل مكاتبَ تتسمّى باسم المعلَم وتقع بعيداً عنه
            score += 0.06
        if digits:  # **«جامعة الجزائر 1» ليست «2»** — الرقمُ في الاستعلام يُطابَق حرفاً
            have = set(re.findall(r"\d+", row["nalt"]))
            score += 0.06 if digits <= have else -0.12
        if (row["kind"] == "street") != wants_street:
            score -= 0.15 if row["kind"] == "street" else 0.08
        dist = None
        if near:
            dist = _km(near[0], near[1], row["lat"], row["lng"])
            score += 0.12 * math.exp(-dist / 15.0)
        scored.append((score, dist, row))
    scored.sort(key=lambda s: -s[0])

    items, seen = [], set()
    for score, dist, row in scored:
        name = row["name_ar"] or row["name_en"] or row["alt"].split(" | ")[0]
        key = (norm(name), round(row["lat"], 3), round(row["lng"], 3))
        if key in seen:
            continue
        seen.add(key)
        context = [c for c in (row["ctx_local"], row["ctx_city"]) if c and c != name]
        items.append({
            "id": f"{row['src']}:{row['id']}", "name": name, "name_en": row["name_en"], "kind": row["kind"],
            "context": "، ".join(dict.fromkeys(context)), "lat": round(row["lat"], 6), "lng": round(row["lng"], 6),
            "distance_m": int(dist * 1000) if dist is not None else None, "src": row["src"],
            "score": round(score, 3),
        })
        if len(items) >= limit:
            break
    return items


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
            if url.path == "/health":
                if not _started:
                    _fill()
                with _Lease() as db:
                    count = db.execute("SELECT count(*) FROM places").fetchone()[0]
                return self._send(200, {"ok": True, "places": count})
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

    def log_message(self, *_args) -> None:  # **لا نصَّ بحثٍ في السجلّ** — ما يكتبه الراكبُ ليس للسجلّات
        return


def main() -> None:
    port = int(os.environ.get("PORT", "8090"))
    _fill()
    ThreadingHTTPServer.daemon_threads = True
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
