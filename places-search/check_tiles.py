"""**كلُّ مكانٍ في المدخل في بلاطةٍ عند أقصى تكبير** — حارسُ `map-data.yml` (قِيس ٢٠٢٦-١١-١٨).

    python check_tiles.py work/places.mbtiles work/places.geojsonl work/works.geojsonl

**العلّةُ مقيسة**: أوّلُ بناءٍ (التشغيل 44334108854) أدخل ٢٦٩٬٤٩٤ مكاناً **وخرج منه عند z16 ‏٦٦٬٥٦٥** — `--drop-densest-as-needed`
ومعدّلُ الإسقاط الافتراضيُّ أسقطا ثلاثةَ أرباعها بلا خطأٍ ولا تحذير، **والبناءُ أخضر**. فهذا يعدّ ما في طبقتَي `places` و`works` عند
أقصى تكبيرٍ (كلُّ عنصرٍ في بلاطته مرّةً — الحاشيةُ لا تُعدّ) ويقارنه بأسطر المدخل، ويُسقط البناءَ إن نقص واحد.

**وما لا يقيسه — مكتوب**: المباني (يُسمح بإسقاط أكثفها في التكبير البعيد عمداً، لخفّة البلاطة على الهاتف)، ولا صحّةَ الاسم أو الفئة.
"""

from __future__ import annotations

import gzip
import sqlite3
import sys


def _varint(b: bytes, i: int) -> tuple[int, int]:
    shift = result = 0
    while True:
        byte = b[i]
        i += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, i
        shift += 7


def _fields(b: bytes):
    i = 0
    while i < len(b):
        key, i = _varint(b, i)
        field, wire = key >> 3, key & 7
        if wire == 0:
            value, i = _varint(b, i)
        elif wire == 2:
            n, i = _varint(b, i)
            value = b[i : i + n]
            i += n
        elif wire == 1:
            value, i = b[i : i + 8], i + 8
        elif wire == 5:
            value, i = b[i : i + 4], i + 4
        else:
            raise ValueError(f"wire type {wire}")
        yield field, value


def _packed(b: bytes) -> list[int]:
    out, i = [], 0
    while i < len(b):
        v, i = _varint(b, i)
        out.append(v)
    return out


def own_points(tile: bytes, layer: str) -> int:
    """عناصرُ الطبقة التي تقع نقطتُها الأولى داخل البلاطة (لا في حاشيتها)."""
    count = 0
    for field, layer_bytes in _fields(tile):
        if field != 3:
            continue
        name, extent, features = None, 4096, []
        for lf, lv in _fields(layer_bytes):
            if lf == 1:
                name = lv.decode()
            elif lf == 5:
                extent = lv
            elif lf == 2:
                features.append(lv)
        if name != layer:
            continue
        for feature in features:
            geometry = next((_packed(v) for f, v in _fields(feature) if f == 4), [])
            if len(geometry) < 3:
                continue
            x = (geometry[1] >> 1) ^ -(geometry[1] & 1)
            y = (geometry[2] >> 1) ^ -(geometry[2] & 1)
            count += 0 <= x < extent and 0 <= y < extent
    return count


def main() -> None:
    mbtiles, *sources = sys.argv[1:]
    db = sqlite3.connect(mbtiles)
    top = db.execute("select max(zoom_level) from tiles").fetchone()[0]
    expected = {}
    for path in sources:
        layer = path.rsplit("/", 1)[-1].split(".")[0]
        with open(path, encoding="utf-8") as f:
            expected[layer] = sum(1 for line in f if line.strip())
    found = dict.fromkeys(expected, 0)
    for (data,) in db.execute("select tile_data from tiles where zoom_level = ?", (top,)):
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        for layer in found:
            found[layer] += own_points(data, layer)
    bad = False
    for layer, want in expected.items():
        got = found[layer]
        print(f"{layer}: المدخل {want} · في البلاطات عند z{top} {got}")
        # **سماحةُ واحدٍ في الألف**: نقطةٌ على حدِّ بلاطتين بالضبط قد تُحسب في جارتها — والإسقاطُ الذي أمسكناه ثلاثةُ أرباع لا جزءٌ من ألف
        bad |= got < want * 0.999
    if bad:
        sys.exit("✗ البلاطاتُ أسقطت عناصرَ — اقرأ خيارات tippecanoe (‎-r1 ‎--no-feature-limit لهذه الطبقات)")
    print("✓ كلُّ عنصرٍ في بلاطةٍ عند أقصى تكبير")


if __name__ == "__main__":
    main()
