"""يقيس كلَّ مرشَّحٍ مقابلَ مثالَي المالك — لا يسمع، يقيس.

الخصائصُ نفسُها للمثالين وللمرشَّحين، بالطريقة نفسِها (أحاديٌّ عند 48 ك.هـ):
النقاء (بُعدُ الجزئيّات عن الأقوى) · الضجيج (تسطّحُ الطيف) · النغميّة · السطوع ·
الحدّة (٢–٦ ك.هـ وما فوق ٥) · ما يضيع في سمّاعة الهاتف (تحت ٤٠٠ هـ) · الهجمة ·
الخفوت (ميلُه ونهايتُه) · الصفير (هضبةٌ بلا خفوت) · الانزلاق (كرتونيّ) · اتّجاهُ النغمات ·
الطولُ المسموع · الجهارة (BS.1770 بالبوّابة).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import signal

def _ffmpeg() -> str:
    """ffmpeg من المتغيّر FFMPEG، أو من المسار، أو من حزمة imageio-ffmpeg — وغيابُه يوقف ولا يُقرأ سلامة."""
    import os
    import shutil
    p = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # noqa: BLE001
        raise SystemExit("ffmpeg مفقود — ثبّته أو عيّن FFMPEG") from exc


FF = _ffmpeg()
SR = 48000
HERE = Path(__file__).parent
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# مرشّحُ K لـ48 ك.هـ (ITU-R BS.1770-4)
KB1 = ([1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585])
KB2 = ([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621])


def decode(path: Path):
    p = subprocess.run([FF, "-hide_banner", "-nostdin", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True)
    x = np.frombuffer(p.stdout, dtype=np.float32).astype(np.float64)
    info = p.stderr.decode("utf-8", "replace")
    line = next((l for l in info.splitlines() if "Audio:" in l), "")
    src = {
        "codec": (re.search(r"Audio: (\w+)", line) or [None, None])[1],
        "sr": int((re.search(r"(\d+) Hz", line) or [0, 0])[1]),
        "kbps": int((re.search(r"(\d+) kb/s", line) or [0, 0])[1]),
        "stereo": ("stereo" in line) or ("2 channels" in line),
    }
    return x, src


def note_name(f: float) -> str:
    if f <= 0:
        return "-"
    m = 69 + 12 * np.log2(f / 440.0)
    k = int(round(m))
    return f"{NAMES[k % 12]}{k // 12 - 1}"


def lufs(x: np.ndarray) -> float:
    y = signal.lfilter(*KB2, signal.lfilter(*KB1, x))
    blk, hop = int(0.4 * SR), int(0.1 * SR)
    if len(y) < blk:
        return float(-0.691 + 10 * np.log10(np.mean(y ** 2) + 1e-20))
    ms = np.array([np.mean(y[i:i + blk] ** 2) for i in range(0, len(y) - blk + 1, hop)])
    l = -0.691 + 10 * np.log10(ms + 1e-20)
    g = ms[l > -70]
    if not len(g):
        return -99.0
    rel = -0.691 + 10 * np.log10(g.mean()) - 10
    g2 = ms[(l > -70) & (l > rel)]
    return float(-0.691 + 10 * np.log10(g2.mean()))


def true_peak_db(x: np.ndarray) -> float:
    up = signal.resample_poly(x, 4, 1)
    return float(20 * np.log10(np.max(np.abs(up)) + 1e-12))


def envelope_db(x: np.ndarray, win_s=0.005, hop_s=0.0025):
    win, hop = int(win_s * SR), int(hop_s * SR)
    n = max(1, (len(x) - win) // hop)
    idx = np.arange(n) * hop
    e = np.sqrt(np.array([np.mean(x[i:i + win] ** 2) for i in idx]) + 1e-14)
    return 20 * np.log10(e), idx / SR


def analyze(path: Path) -> dict:
    x, src = decode(path)
    if len(x) < SR * 0.05:
        return {"file": path.name, "error": "too short / undecodable"}
    peak = np.max(np.abs(x)) + 1e-12
    env, te = envelope_db(x)
    pk = env.max()
    act = np.where(env > pk - 45)[0]
    start = te[act[0]]
    end60 = te[np.where(env > pk - 60)[0][-1]]
    aud30 = te[np.where(env > pk - 30)[0][-1]] - start
    aud40 = te[np.where(env > pk - 40)[0][-1]] - start
    lead_silence = start
    tail_db = float(np.max(env[-8:]) - pk) if len(env) > 8 else 0.0  # آخرُ ٢٠ م.ث تقريباً

    # الطيفُ القصير
    nper, hop = 2048, 256
    f, t, Z = signal.stft(x, fs=SR, nperseg=nper, noverlap=nper - hop, boundary=None, padded=False)
    P = np.abs(Z) ** 2
    fe = P.sum(axis=0)
    fe_db = 10 * np.log10(fe + 1e-20)
    live = fe_db > fe_db.max() - 30
    w = fe[live] / fe[live].sum()
    Pl = P[:, live]

    band = (f > 300) & (f < 8000)
    flat = np.exp(np.mean(np.log(Pl[band] + 1e-20), axis=0)) / (np.mean(Pl[band], axis=0) + 1e-20)
    centroid = (f[:, None] * Pl).sum(axis=0) / (Pl.sum(axis=0) + 1e-20)
    tot = Pl[f > 100].sum(axis=0) + 1e-20
    hf = Pl[f > 5000].sum(axis=0) / tot
    pres = Pl[(f > 2000) & (f < 6000)].sum(axis=0) / tot
    low = Pl[(f > 60) & (f < 400)].sum(axis=0) / (Pl[f > 60].sum(axis=0) + 1e-20)

    # النغميّةُ والنقاء: قممٌ بارزةٌ في كلِّ إطار
    rich_l, tonal_l = [], []
    sel = (f > 150) & (f < 12000)
    fi = np.where(sel)[0]
    for j in range(Pl.shape[1]):
        s = Pl[sel, j]
        sdb = 10 * np.log10(s + 1e-20)
        med = signal.medfilt(sdb, 41)
        pk_idx, _ = signal.find_peaks(sdb, prominence=6, distance=4)
        pk_idx = [k for k in pk_idx if sdb[k] > med[k] + 10 and sdb[k] > sdb.max() - 60]
        if not pk_idx:
            rich_l.append(0.0); tonal_l.append(0.0); continue
        pw = np.array([s[max(0, k - 3):k + 4].sum() for k in pk_idx])
        tonal_l.append(float(pw.sum() / (s.sum() + 1e-20)))
        top = pw.max()
        others = pw.sum() - top
        rich_l.append(float(10 * np.log10(others / top + 1e-6)))
    richness = float(np.sum(np.array(rich_l) * w))
    tonality = float(np.sum(np.array(tonal_l) * w))

    # البدايات
    logm = np.log(P + 1e-12)
    flux = np.maximum(0, np.diff(logm, axis=1))[(f > 100) & (f < 10000)].sum(axis=0)
    flux = np.concatenate([[0], flux])
    flux_n = flux / (flux.max() + 1e-12)
    gate = fe_db > fe_db.max() - 35
    on_idx, _ = signal.find_peaks(flux_n * gate, height=0.18, distance=int(0.07 * SR / hop))
    onsets = [float(t[k]) for k in on_idx]
    if not onsets:
        onsets = [float(start)]

    # النغماتُ ودرجاتُها
    notes = []
    for k, on in enumerate(onsets):
        a = int((on + 0.02) * SR)
        b = min(len(x), a + int(0.10 * SR))
        if b - a < 512:
            continue
        seg = x[a:b] * np.hanning(b - a)
        spec = np.abs(np.fft.rfft(seg, 1 << 15)) ** 2
        fr = np.fft.rfftfreq(1 << 15, 1 / SR)
        bm = (fr > 150) & (fr < 5000)
        i = int(np.argmax(spec * bm))
        f0 = float(fr[i])
        notes.append({"t": round(on, 3), "hz": round(f0, 1), "note": note_name(f0)})
    steps = [12 * np.log2(notes[i]["hz"] / notes[i - 1]["hz"]) for i in range(1, len(notes))]
    if len(notes) >= 2:
        total = 12 * np.log2(notes[-1]["hz"] / notes[0]["hz"])
        direction = "up" if total >= 2 else ("down" if total <= -2 else "level")
    else:
        total, direction = 0.0, "single"

    # الانزلاقُ داخلَ النغمة: تُتبَع **الجزئيّةُ نفسُها** إطاراً بإطار (نافذةُ ±٣٪ حول
    # موضعها السابق) — لا «أقوى قمّةٍ في كلِّ إطار»، فتلك تقفز بين الجزئيّات في الأجراس
    # فتُقرأ انزلاقاً وليست به. والنغمةُ المضروبةُ ثابتةُ الدرجة (< ٠٫٣ نصف صوت).
    bounds = onsets + [t[-1]]
    glide = 0.0
    f4, t4, Z4 = signal.stft(x, fs=SR, nperseg=4096, noverlap=4096 - 256, boundary=None, padded=False)
    A4 = np.abs(Z4)
    df = f4[1] - f4[0]
    bm4 = np.where((f4 > 150) & (f4 < 6000))[0]

    def interp(col, b):
        if b <= 0 or b >= len(col) - 1:
            return f4[b]
        a, m, c = (np.log(col[b - 1] + 1e-12), np.log(col[b] + 1e-12), np.log(col[b + 1] + 1e-12))
        den = a - 2 * m + c
        return f4[b] + (0.5 * (a - c) / den if den else 0.0) * df

    for k, on in enumerate(onsets):
        j0 = np.searchsorted(t4, on + 0.03)
        j1 = np.searchsorted(t4, min(bounds[k + 1] - 0.01, on + 0.5))
        if j1 - j0 < 5:
            continue
        jpk = j0 + int(np.argmax(A4[bm4][:, j0:j1].max(axis=0)))
        b = bm4[int(np.argmax(A4[bm4, jpk]))]
        fq, am = [], []
        for j in range(jpk, j1):
            col = A4[:, j]
            wdt = max(2, int(b * 0.03))
            lo, hi = max(1, b - wdt), min(len(col) - 2, b + wdt)
            b = lo + int(np.argmax(col[lo:hi + 1]))
            fq.append(interp(col, b)); am.append(col[b])
        am = np.array(am); fq = np.array(fq)
        keep = 20 * np.log10(am / (am.max() + 1e-12) + 1e-12) > -20
        if keep.sum() < 5:
            continue
        st = 12 * np.log2(fq[keep] / fq[keep][0])
        glide = max(glide, float(np.max(np.abs(st))))

    # الهجمةُ والخفوتُ والهضبة
    e1, t1 = envelope_db(x, 0.002, 0.001)
    # الهجمة: من أوّل صعودٍ إلى **أوّل قمّة** (لا أعلى قمّةٍ في ١٢٠ م.ث — تلك قد تكون
    # النغمةَ الثانيةَ الأعلى، فتُقرأ الضربةُ الخفيفةُ «انتفاخاً» وليست به)
    s_ms = int(start * 1000)
    seg = e1[s_ms: s_ms + 200]
    attack_ms = 0.0
    if len(seg) > 5:
        sm = np.convolve(seg, np.ones(3) / 3, mode="same")
        rising = 0
        for i in range(1, len(sm) - 3):
            if sm[i + 1] <= sm[i] and sm[i + 2] <= sm[i] and sm[i] > seg.max() - 25:
                rising = i
                break
        else:
            rising = int(np.argmax(sm))
        lo = seg[0]
        hi = sm[rising]
        a10 = int(np.argmax(sm >= lo + 0.1 * (hi - lo)))
        attack_ms = float(max(0, rising - a10))
    last_on = int(onsets[-1] * 1000)
    tail = e1[last_on:]
    tp = int(np.argmax(tail[:200])) if len(tail) else 0
    after = tail[tp:tp + 400]
    slope = 0.0
    if len(after) > 40:
        tt = np.arange(len(after)) / 1000.0
        good = after > after[0] - 40
        if good.sum() > 20:
            slope = float(np.polyfit(tt[good], after[good], 1)[0])
    plateau_ms = 0.0
    for k in range(len(onsets)):
        a = int(onsets[k] * 1000)
        b = int(bounds[k + 1] * 1000)
        ee = e1[a:b]
        if len(ee) < 30:
            continue
        p = ee.max()
        run = best = 0
        for v in ee:
            run = run + 1 if v > p - 3 else 0
            best = max(best, run)
        plateau_ms = max(plateau_ms, float(best))

    return {
        "file": path.name,
        "src": src,
        "dur_file": round(len(x) / SR, 3),
        "lead_silence_ms": round(lead_silence * 1000, 1),
        "audible30_s": round(float(aud30), 3),
        "audible40_s": round(float(aud40), 3),
        "end60_s": round(float(end60), 3),
        "tail_db": round(tail_db, 1),
        "lufs": round(lufs(x), 1),
        "tp_db": round(true_peak_db(x), 1),
        "peak_db": round(float(20 * np.log10(peak)), 1),
        "centroid_hz": round(float(np.sum(centroid * w)), 0),
        "flatness": round(float(np.sum(flat * w)), 4),
        "tonality": round(tonality, 3),
        "richness_db": round(richness, 1),
        "hf_ratio": round(float(np.sum(hf * w)), 4),
        "presence_ratio": round(float(np.sum(pres * w)), 3),
        "low_ratio": round(float(np.sum(low * w)), 3),
        "attack_ms": round(attack_ms, 1),
        "decay_db_per_s": round(slope, 1),
        "plateau_ms": round(plateau_ms, 0),
        "glide_st": round(glide, 2),
        "n_notes": len(notes),
        "notes": notes,
        "steps_st": [round(s, 1) for s in steps],
        "span_st": round(float(total), 1),
        "direction": direction,
    }


if __name__ == "__main__":
    files = [Path(p) for p in sys.argv[1:]]
    out = []
    for p in files:
        try:
            out.append(analyze(p))
        except Exception as e:  # ملفٌّ واحدٌ لا يُسقط القياس كلَّه
            out.append({"file": p.name, "error": repr(e)})
    print(json.dumps(out, ensure_ascii=False))
