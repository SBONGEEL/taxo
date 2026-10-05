"""تشطيبُ أصوات TAXO المؤقّتة (§٦١-ك) — بما يأذن به الترخيص: قصٌّ وخفوتٌ وموازنةٌ وجهارة، ثمّ القياسُ بعده.

المصادرُ في `sources.json`: رابطُ كلِّ ملفٍّ الأصليّ وبصمتُه (sha256). **يُنزَّل ما ليس في `src/` وحدَه، وبتأنٍّ،
ويُرفض كلُّ ملفٍّ تغيّرت بصمتُه** — فما يُشطَّب اليومَ هو ما قُرئ ترخيصُه وقِيس. و`src/` و`out/` لا يُودَعان.

لكلِّ ملفّ: يُقصّ الصمتُ في أوّله (٢ م.ث قبل الضربة، ودخولٌ ليّنٌ ٣ م.ث) · ينتهي عند خفوته الطبيعيّ (−٦٠ د.ب) أو عند
الحدّ (٢٫٠ ث، وطلبُ الكبتن ٢٫٢ ث بالضبط) بخفوتٍ جيبيٍّ في آخره — لا قطع · يُقطع ما تحت ١٢٠ هـ · وتُقرَّب نبرتُه من نبرة
العائلة برفٍّ عالٍ عند ٢٫٥ ك.هـ لا يتجاوز ±٣ د.ب (نصفُ الفرق) · ويُخفَّف أسفلُه (−٣ د.ب عند ٣٥٠ هـ) إن كان يخفت في سمّاعة
هاتف · ثمّ الجهارة: −٢٢ LUFS أحاديّاً (كمثالَي المالك)، وطلبُ الكبتن −٢٠ — بلا تجاوزٍ لـ−١ dBTP.

الاستعمال:  python finish.py [--formats] [مفتاح ...]
  --formats  يُخرج أيضاً صيغَ التطبيقين: ogg لقنوات أندرويد، وcaf لإشعارات iOS (وmp3 للويب دائماً).
"""
import hashlib
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
from scipy import signal

from measure import FF, SR, envelope_db, lufs, true_peak_db

HERE = Path(__file__).parent
SRC, OUT = HERE / "src", HERE / "out"
UA = "Mozilla/5.0 (TAXO sound finishing)"
BANDS = [(150, 400), (400, 800), (800, 1600), (1600, 3200), (3200, 6400), (6400, 12000)]
TARGET_UPPER = (-14.0 + -20.0) / 2   # نبرةُ العائلة: ما فوق ١٫٦ ك.هـ نسبةً إلى الجسم (وسطُ المثالين تقريباً)


def fetch(entry: dict) -> Path:
    p = SRC / entry["file"]
    if not p.exists():
        SRC.mkdir(exist_ok=True)
        req = urllib.request.Request(entry["url"], headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            p.write_bytes(r.read())
        time.sleep(1)
    got = hashlib.sha256(p.read_bytes()).hexdigest()
    if got != entry["sha256"]:
        raise SystemExit(f"✗ {entry['file']}: البصمةُ تغيّرت — ليس الملفَّ الذي قُرئ ترخيصُه وقِيس. يُوقَف.")
    return p


def decode_stereo(path: Path) -> np.ndarray:
    p = subprocess.run([FF, "-hide_banner", "-nostdin", "-i", str(path), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True, check=True)
    return np.frombuffer(p.stdout, dtype=np.float32).astype(np.float64).reshape(-1, 2)


def biquad(kind: str, f0: float, gain_db: float = 0.0, q: float = 0.707):
    A = 10 ** (gain_db / 40); w0 = 2 * np.pi * f0 / SR; cw, sw = np.cos(w0), np.sin(w0); al = sw / (2 * q)
    if kind == "hp":
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]; a = [1 + al, -2 * cw, 1 - al]
    else:
        sa = 2 * np.sqrt(A) * al
        if kind == "hs":
            b = [A * ((A + 1) + (A - 1) * cw + sa), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - sa)]
            a = [(A + 1) - (A - 1) * cw + sa, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - sa]
        else:  # ls
            b = [A * ((A + 1) - (A - 1) * cw + sa), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - sa)]
            a = [(A + 1) + (A - 1) * cw + sa, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - sa]
    return np.array(b) / a[0], np.array(a) / a[0]


def bands(x: np.ndarray) -> np.ndarray:
    f, pxx = signal.welch(x, SR, nperseg=4096)
    v = np.array([10 * np.log10(pxx[(f >= lo) & (f < hi)].sum() + 1e-20) for lo, hi in BANDS])
    return v - v[1:3].max()


def phone(x: np.ndarray) -> np.ndarray:
    """سمّاعةُ هاتفٍ صغيرة — محاكاة: يضيع ما تحت ~٤٠٠ هـ ويخفت ما فوق ~٩ ك.هـ، ورنينٌ خفيفٌ حول ٢٫٥ ك.هـ."""
    b, a = signal.butter(2, 400 / (SR / 2), "high"); y = signal.lfilter(b, a, x)
    b, a = signal.butter(2, 9000 / (SR / 2), "low"); y = signal.lfilter(b, a, y)
    b, a = signal.iirpeak(2500 / (SR / 2), 1.2)
    return y + 0.4 * signal.lfilter(b, a, y)


def rcos(n: int) -> np.ndarray:
    return 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, n))


def finish(entry: dict, formats: bool) -> dict:
    opt = entry["opt"]
    x = decode_stereo(fetch(entry)).mean(axis=1)
    notes = []
    env, te = envelope_db(x, 0.001, 0.0005)
    s = max(0, int((te[np.argmax(env > env.max() - 50)] - 0.002) * SR))
    x = x[s:]
    if "len" in opt:   # طلبُ الكبتن: الطولُ بالضبط، فتوقيتُ تكراره كما اليوم
        n = int(opt["len"] * SR)
        end = n
        if "cycle_after" in opt:   # نغمةُ رنينٍ تبدأ دورتَها من جديد: يُنتهى قبل ضربتها التالية
            e2, t2 = envelope_db(x, 0.01, 0.005)
            i0 = np.searchsorted(t2, opt["cycle_after"])
            jumps = [i for i in range(i0, len(e2) - 4) if e2[i + 4] - e2[i] > 15]
            if jumps:
                end = min(n, int((t2[jumps[0]] - 0.015) * SR))
        y = x[:end].copy()
        fl = int(opt.get("fade", 0.12) * SR)
        y[-fl:] *= rcos(fl)[::-1]
        y = np.concatenate([y, np.zeros(max(0, n - len(y)))])[:n]
    else:
        e2, t2 = envelope_db(x, 0.01, 0.005)
        end_s = min(t2[np.where(e2 > e2.max() - 60)[0][-1]] + 0.05, 2.0)
        y = x[: int(end_s * SR)].copy()
        fl = int(min(0.25, 0.25 * end_s) * SR)
        y[-fl:] *= rcos(fl)[::-1]
    fi = int(0.003 * SR)
    y[:fi] *= rcos(fi)
    b, a = biquad("hp", 120); y = signal.lfilter(b, a, y)
    g = float(np.clip((TARGET_UPPER - float(np.mean(bands(y)[3:5]))) / 2, -3, 3))
    if abs(g) >= 0.5:
        b, a = biquad("hs", 2500, g); y = signal.lfilter(b, a, y)
    notes.append(f"lead {s / SR * 1000:.0f}ms trimmed; high-shelf {g:+.1f} dB @2.5k")
    if lufs(phone(y)) - lufs(y) < -1.5:
        b, a = biquad("ls", 350, -3.0); y = signal.lfilter(b, a, y)
        notes.append("low-shelf -3 dB @350 (phone)")
    # **−٢٢ للعائلة، وطلبُ الكبتن −٢٠** — **وما صُمّم أهدأ يقول جهارتَه في `opt.lufs`**
    # («وصلتُ» عند الكبتن: يقع وهو يقود، فصوتٌ يفزعه أسوأُ من صمت — §9.1)
    target = float(opt.get("lufs", -20.0 if entry["role"] == "request" else -22.0))
    y = y * 10 ** ((target - lufs(y)) / 20)
    tp = true_peak_db(y)
    if tp > -1.0:
        y = y * 10 ** ((-1.0 - tp) / 20)
        notes.append(f"gain reduced {tp + 1:.1f} dB for true peak")
    OUT.mkdir(exist_ok=True)
    key = entry["key"]
    wav = OUT / f"{key}.wav"
    pcm = np.clip(y, -1, 1).astype(np.float64)
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-f", "f64le", "-ar", str(SR), "-ac", "1", "-i", "-",
                    "-c:a", "pcm_s24le", str(wav)], input=pcm.tobytes(), check=True)
    enc = [("mp3", ["-ar", "44100", "-c:a", "libmp3lame", "-b:a", "192k"])]
    if formats:
        enc += [("ogg", ["-ar", "44100", "-c:a", "libvorbis", "-q:a", "6"]),
                ("caf", ["-ar", "44100", "-c:a", "pcm_s16le", "-f", "caf"])]
    for ext, args in enc:
        subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav), *args, str(OUT / f"{key}.{ext}")],
                       check=True)
    return {"key": key, "role": entry["role"], "len_s": round(len(y) / SR, 3), "lufs": round(lufs(y), 1),
            "tp_db": round(true_peak_db(y), 1), "phone_delta_db": round(lufs(phone(y)) - lufs(y), 1), "notes": notes}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    formats = "--formats" in sys.argv
    entries = [e for e in json.loads((HERE / "sources.json").read_text(encoding="utf-8")) if not args or e["key"] in args]
    for r in (finish(e, formats) for e in entries):
        print(f"{r['key']:7} {r['len_s']:.2f}s  {r['lufs']:6.1f} LUFS  TP {r['tp_db']:5.1f}  هاتف {r['phone_delta_db']:+.1f}  | {'; '.join(r['notes'])}")
