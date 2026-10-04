"""أصواتُ TAXO 2.0 — تُصنع من الصفر بهذا الملفّ وحدَه: لا عيّنة، ولا صوتَ من مكتبةٍ أو تطبيقٍ آخر (SPEC §٦١-ح).

كلُّ صوتٍ **نغماتٌ تُركَّب حسابياً** (جمعُ موجاتٍ جيبيةٍ بغلافٍ يتلاشى — «جرسُ TAXO») — فالأصلُ هو هذا النصّ، والملكيةُ لـTAXO.
والعائلةُ واحدة لأنّ الأصواتَ كلَّها **من التوقيع نفسِه**: نوتتاه، وصوتُه، وسلّمُه.

    python make_sounds.py <out_dir>

ويُخرج لكلِّ صوت: `<name>.wav` (٤٨ ك.هـ، ١٦ بت، أحادي) — ومعه `report.json` بالمدّة والجهارة والذروة لكلِّ ملفّ.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import signal

SR = 48_000

# ── السلّم — من نوتتي التوقيع (البذرة: نغمةُ اللقاء في الترحيب) ────────────────────────────────────────
# تُضبط من `SEED` أدناه؛ وكلُّ نوتةٍ أخرى درجةٌ من سلّمها الخماسيّ فلا تتنافر الأصواتُ إن تتابعت.
SEED = (659.26, 987.77)  # تُستبدل بنوتتي الترحيب حين تُقرأ من الشيفرة


def pentatonic(root: float) -> list[float]:
    """السلّمُ الخماسيُّ الكبير على الجذر، ثلاثةُ دواوين — درجاتٌ لا تتنافر أيّاً كان ترتيبُها."""
    steps = [0, 2, 4, 7, 9]
    return [root * 2 ** ((12 * octave + step) / 12) for octave in range(-1, 3) for step in steps]


@dataclass(frozen=True)
class Voice:
    """«جرسُ TAXO»: جزئياتٌ بنِسَبٍ ثابتة، ولكلٍّ منها تلاشيه — فالأعلى يخبو أسرع، كما تفعل المطرقةُ على المعدن الرقيق."""

    partials: tuple[tuple[float, float, float], ...]  # (نسبةُ التردّد، السعة، زمنُ التلاشي بالثواني)
    attack: float = 0.004
    click: float = 0.0  # نقرةُ المطرقة — ضوضاءٌ قصيرةٌ في الحزمة العليا تعطي الحدّ


BELL = Voice(
    partials=((1.0, 1.0, 0.42), (2.0, 0.32, 0.22), (3.0, 0.12, 0.14), (4.16, 0.07, 0.09), (5.43, 0.03, 0.05)),
    attack=0.003,
    click=0.025,
)
BRIGHT = Voice(  # للتنبيه الذي يجب أن يُسمع على الطريق: الجزئياتُ العليا أقوى وأطول
    partials=((1.0, 1.0, 0.36), (2.0, 0.46, 0.26), (3.0, 0.26, 0.18), (4.16, 0.16, 0.12), (5.43, 0.08, 0.08)),
    attack=0.002,
    click=0.035,
)
SOFT = Voice(  # للخطأ: أدكنُ وأقصر — يُخبر ولا يوبّخ
    partials=((1.0, 1.0, 0.24), (2.0, 0.18, 0.12), (3.0, 0.05, 0.08)),
    attack=0.008,
    click=0.0,
)


def note(freq: float, length: float, voice: Voice, gain: float = 1.0, seed: int = 0) -> np.ndarray:
    """نوتةٌ تُضرب ثمّ تُكتم: تخبو بطبعها حتى `length`، ثمّ **تُكتم كتماً ليّناً** (كيدٍ ترفع المطرقة) — لا قطعٌ والصوتُ مسموع.

    وقِيس أن القطعَ عيب: الصيغةُ الأولى كانت تنهي النوتةَ عند `length` وسعتُها ما زالت ٤٠٪ — فتُسمع طقطقةٌ في وسط الصوت.
    """
    damp = 0.07  # زمنُ الكتم بالثواني — سريعٌ بلا طقطقة
    n = int(SR * (length + 6 * damp))
    t = np.arange(n) / SR
    out = np.zeros(n)
    rng = np.random.default_rng(seed)
    held = np.where(t < length, 1.0, np.exp(-(t - length) / damp))
    for ratio, amp, decay in voice.partials:
        f = freq * ratio
        if f >= SR / 2 * 0.9:
            continue
        phase = rng.uniform(0, 2 * np.pi)
        out += amp * np.exp(-t / decay) * np.sin(2 * np.pi * f * t + phase)
    out *= held
    # الهجمةُ نصفُ جيبٍ لا خطّ — بدايةٌ بلا نقرةٍ عريضة الطيف
    k = max(1, int(SR * voice.attack))
    out[:k] *= np.sin(np.linspace(0, np.pi / 2, k)) ** 2
    if voice.click > 0:
        burst = rng.standard_normal(n) * np.exp(-t / 0.004)
        sos = signal.butter(2, [2000, 5000], btype="bandpass", fs=SR, output="sos")
        out += voice.click * signal.sosfilt(sos, burst)
    return out * gain


def place(events: list[tuple[float, np.ndarray]], total: float) -> np.ndarray:
    buf = np.zeros(int(SR * total) + 1)
    for start, clip in events:
        i = int(SR * start)
        j = min(len(buf), i + len(clip))
        buf[i:j] += clip[: j - i]
    return buf


def fade_tail(x: np.ndarray, ms: float = 150) -> np.ndarray:
    k = min(len(x) // 3, int(SR * ms / 1000))
    x = x.copy()
    x[-k:] *= np.cos(np.linspace(0, np.pi / 2, k)) ** 2
    return x


# ── قياسُ الجهارة: ترشيحُ K من ITU-R BS.1770 على الجزء الحيّ من الصوت ─────────────────────────────────────
def k_weight(x: np.ndarray) -> np.ndarray:
    # المرحلةُ الأولى: رفٌّ عالٍ (+4 د.ب فوق ~1.5 ك.هـ) — معاملاتُ المعيار لـ48 ك.هـ
    b1 = [1.53512485958697, -2.69169618940638, 1.19839281085285]
    a1 = [1.0, -1.69065929318241, 0.73248077421585]
    # المرحلةُ الثانية: مرشّحُ تمريرٍ عالٍ (RLB)
    b2 = [1.0, -2.0, 1.0]
    a2 = [1.0, -1.99004745483398, 0.99007225036621]
    return signal.lfilter(b2, a2, signal.lfilter(b1, a1, x))


def active_loudness(x: np.ndarray) -> float:
    """جهارةُ الجزء الحيّ (LKFS تقريباً): متوسّطُ القدرة الموزونة على النوافذ التي تعلو −٢٠ د.ب عن أعلاها — فالذيلُ الصامتُ لا يخفضها."""
    y = k_weight(x)
    win = int(0.05 * SR)
    hop = win // 2
    powers = np.array([np.mean(y[i : i + win] ** 2) for i in range(0, max(1, len(y) - win), hop)])
    powers = powers[powers > 0]
    if len(powers) == 0:
        return -120.0
    gate = powers.max() * 10 ** (-20 / 10)
    live = powers[powers >= gate]
    return -0.691 + 10 * np.log10(np.mean(live))


def phone_speaker(x: np.ndarray) -> np.ndarray:
    """سمّاعةُ هاتفٍ رخيص تقريباً: لا شيءَ تحت ~٥٠٠ هـ، وتخبو فوق ~٧ ك.هـ."""
    sos_hp = signal.butter(4, 500, btype="highpass", fs=SR, output="sos")
    sos_lp = signal.butter(2, 7000, btype="lowpass", fs=SR, output="sos")
    return signal.sosfilt(sos_lp, signal.sosfilt(sos_hp, x))


def true_peak_db(x: np.ndarray) -> float:
    up = signal.resample_poly(x, 4, 1)
    return 20 * np.log10(np.max(np.abs(up)) + 1e-12)


TARGET_LKFS = -16.0
CEILING_DBTP = -1.0


def master(x: np.ndarray) -> np.ndarray:
    """إلى الجهارة نفسِها كلَّها، ثمّ سقفُ الذروة الحقيقية — بلا ضغطٍ يسطّح الصوت."""
    x = fade_tail(x)
    gain = 10 ** ((TARGET_LKFS - active_loudness(x)) / 20)
    x = x * gain
    peak = true_peak_db(x)
    if peak > CEILING_DBTP:
        x = x * 10 ** ((CEILING_DBTP - peak) / 20)
    return x


def write_wav(path: Path, x: np.ndarray) -> None:
    from scipy.io import wavfile

    pcm = np.clip(np.round(x * 32767), -32768, 32767).astype(np.int16)
    wavfile.write(path, SR, pcm)
