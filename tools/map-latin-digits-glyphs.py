#!/usr/bin/env python3
"""**أرقامُ الخريطة لاتينيّة** (أمرُ المالك ٢٠٢٦-١١-١٨ الثاني: «يجب أن تكون الأرقامُ لاتينيّة») — يبني نطاقَ الخطّ العربيّ بأرقامٍ لاتينيّة.

**العلّة**: أسماءُ OpenStreetMap العربيّة تحمل أحياناً خاناتٍ عربيّةً-هنديّة («شارع ٢٠»، «الدائري الثاني ٢»)، والخريطةُ ترسم النصَّ كما
في البلاطة — **ولا تعبيرَ في MapLibre يبدّل حرفاً بحرف**. **فيُبدَّل الشكلُ لا النصّ**: نسخةٌ من نطاق `1536-1791` (العربيّ) لكلِّ خطٍّ
من خطوط النمط، **رسمُ ٠–٩ (U+0660–0669) و۰–۹ (U+06F0–06F9) فيها هو رسمُ 0–9** من نطاق `0-255` للخطّ نفسِه، وكلُّ ما عداها كما هو حرفاً.
والتطبيقُ يطلب هذا النطاقَ وحدَه من ملفّاته (`transformRequest` في `lib/open-map-style.ts`)، وبقيّةُ النطاقات من OpenFreeMap كما كانت.

**والاتّجاهُ لا يتغيّر**: الخانةُ العربيّةُ-الهنديّةُ صنفُها في ثنائيّة الاتّجاه «رقمٌ عربيّ» تُرسم سلسلتُه من اليسار كاللاتينيّ — فـ«شارع ٢٠»
يُرى «شارع 20» بترتيبه.

**والرخصة**: خطوطُ Noto بـSIL Open Font License 1.1 — التعديلُ والتوزيعُ مأذونان، **ولا اسمَ محجوزاً** في رخصة Noto؛ والإسنادُ في `public/map-glyphs/LICENSE`.

    python3 tools/map-latin-digits-glyphs.py            # يجلب ويبني في customer-app/public/map-glyphs وdriver-app/public/map-glyphs
    python3 tools/map-latin-digits-glyphs.py --check    # يقيس المبنيَّ دون جلب: كلُّ ٠–٩ فيه بشكل 0–9، وكلُّ ما عداها كما في الأصل
"""

from __future__ import annotations

import pathlib
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = "https://tiles.openfreemap.org/fonts/{stack}/{range}.pbf"
STACKS = ("Noto Sans Regular", "Noto Sans Bold")
ARABIC = "1536-1791"
LATIN = "0-255"
APPS = ("customer-app", "driver-app")
SWAPS = {0x660 + d: 0x30 + d for d in range(10)} | {0x6F0 + d: 0x30 + d for d in range(10)}
LICENSE = """Noto Sans — Copyright 2022 The Noto Project Authors (https://github.com/notofonts/latin-greek-cyrillic)
SIL Open Font License, Version 1.1 — https://openfontlicense.org

Glyph ranges here are derived from the OpenFreeMap font PBFs (https://openfreemap.org): the Arabic range 1536-1791
with U+0660–0669 and U+06F0–06F9 drawn as the Latin digits 0–9 of the same font. Everything else is unchanged.
Built by tools/map-latin-digits-glyphs.py.
"""


def _varint(b: bytes, i: int) -> tuple[int, int]:
    r = s = 0
    while True:
        c = b[i]
        i += 1
        r |= (c & 0x7F) << s
        s += 7
        if c < 0x80:
            return r, i


def _enc_varint(v: int) -> bytes:
    out = bytearray()
    while True:
        c = v & 0x7F
        v >>= 7
        if v:
            out.append(c | 0x80)
        else:
            out.append(c)
            return bytes(out)


def _fields(b: bytes):
    i = 0
    while i < len(b):
        key, i = _varint(b, i)
        f, t = key >> 3, key & 7
        if t == 0:
            v, i = _varint(b, i)
        elif t == 2:
            n, i = _varint(b, i)
            v = b[i : i + n]
            i += n
        else:
            raise ValueError(f"نوعُ حقلٍ غيرُ متوقَّع {t}")
        yield f, t, v


def _field(f: int, t: int, v) -> bytes:
    if t == 0:
        return _enc_varint(f << 3) + _enc_varint(v)
    return _enc_varint((f << 3) | 2) + _enc_varint(len(v)) + v


def _glyph_map(pbf: bytes) -> dict[int, bytes]:
    out = {}
    for f, _, stack in _fields(pbf):
        if f != 1:
            continue
        for g, _, raw in _fields(stack):
            if g == 3:
                gid = next(v for ff, _, v in _fields(raw) if ff == 1)
                out[gid] = raw
    return out


def _with_id(raw: bytes, gid: int) -> bytes:
    return b"".join(_field(f, t, gid if f == 1 else v) for f, t, v in _fields(raw))


def latinise(arabic: bytes, latin: bytes) -> bytes:
    digits = _glyph_map(latin)
    out = bytearray()
    for f, t, stack in _fields(arabic):
        if f != 1:
            out += _field(f, t, stack)
            continue
        body = bytearray()
        for g, gt, raw in _fields(stack):
            if g == 3:
                gid = next(v for ff, _, v in _fields(raw) if ff == 1)
                if gid in SWAPS and SWAPS[gid] in digits:
                    raw = _with_id(digits[SWAPS[gid]], gid)
            body += _field(g, gt, raw)
        out += _field(1, 2, bytes(body))
    return bytes(out)


def _fetch(stack: str, rng: str) -> bytes:
    url = SOURCE.format(stack=urllib.parse.quote(stack), range=rng)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "taxo-build"}), timeout=30) as r:
        return r.read()


def _target(app: str, stack: str) -> pathlib.Path:
    return ROOT / app / "public" / "map-glyphs" / stack / f"{ARABIC}.pbf"


def check() -> int:
    bad = 0
    for app in APPS:
        for stack in STACKS:
            p = _target(app, stack)
            if not p.exists():
                print(f"✗ {p.relative_to(ROOT)} غائب")
                bad += 1
                continue
            glyphs = _glyph_map(p.read_bytes())
            for gid in SWAPS:
                fields = {f: v for f, _, v in _fields(glyphs[gid])}
                if fields.get(1) != gid:
                    print(f"✗ {p.relative_to(ROOT)}: U+{gid:04X} بلا معرّفه")
                    bad += 1
            # **الصفرُ اللاتينيُّ أعرضُ من النقطة العربيّة** — شكلٌ لم يُبدَّل يبقى بعرض ٤
            zero = {f: v for f, _, v in _fields(glyphs[0x660])}
            if zero.get(3, 0) <= 4:
                print(f"✗ {p.relative_to(ROOT)}: ٠ ما زال نقطةً عربيّة")
                bad += 1
    print("✓ أرقامُ الخريطة لاتينيّةُ الشكل في التطبيقين" if not bad else f"✗ {bad} عطباً")
    return 1 if bad else 0


def build() -> int:
    for stack in STACKS:
        arabic, latin = _fetch(stack, ARABIC), _fetch(stack, LATIN)
        out = latinise(arabic, latin)
        for app in APPS:
            p = _target(app, stack)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(out)
            (p.parent.parent / "LICENSE").write_text(LICENSE, encoding="utf-8")
            print(f"✓ {p.relative_to(ROOT)} — {len(out)} بايت")
    return check()


if __name__ == "__main__":
    sys.exit(check() if "--check" in sys.argv else build())
