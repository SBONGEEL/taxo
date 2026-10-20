"""أصواتُ إشعارات المالك (SPEC §٨١/١٠) — **تُولَّد رياضيّاً هنا، لا تُنسخ ولا تُقتطع من تسجيل**.

كلُّ صوتٍ مجموعُ موجاتٍ جيبيّةٍ بغلافٍ أُسّيّ (وقليلٌ من ضجيجٍ مُرشَّحٍ في رنّة النقود) — فلا مصدرَ له غيرُ هذا الملفّ، ولا رخصةَ
يحتاجها غيرُ رخصة المشروع. يُشغَّل: python make_sounds.py <مجلَّد المخرَج> — ويكتب WAV بـ٤٤١٠٠ هرتز أحاديّ ١٦ بتاً.
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

RATE = 44_100
rng = np.random.default_rng(81)  # بذرةٌ ثابتة: الملفُّ نفسُه في كلِّ تشغيل


def t(seconds: float) -> np.ndarray:
    return np.arange(int(RATE * seconds)) / RATE


def env(length: int, attack: float, decay: float) -> np.ndarray:
    """غلافٌ: صعودٌ خطّيٌّ قصير ثمّ هبوطٌ أُسّيّ — **بلا نقرةٍ في البدء ولا قطعٍ في النهاية**."""
    x = np.arange(length) / RATE
    rise = np.clip(x / max(attack, 1e-4), 0, 1)
    fall = np.exp(-x / decay)
    tail = np.ones(length)
    fade = min(length, int(0.02 * RATE))
    tail[-fade:] = np.linspace(1, 0, fade)
    return rise * fall * tail


def bell(freq: float, seconds: float, decay: float, partials=((1.0, 1.0), (2.0, 0.35), (3.01, 0.18), (4.2, 0.08))) -> np.ndarray:
    x = t(seconds)
    wave_ = sum(amp * np.sin(2 * np.pi * freq * ratio * x) * np.exp(-x * ratio * 0.9 / decay) for ratio, amp in partials)
    return wave_ * env(len(x), 0.004, decay * 1.4)


def place(total: float, *parts: tuple[float, np.ndarray]) -> np.ndarray:
    out = np.zeros(int(RATE * total))
    for start, sound in parts:
        i = int(RATE * start)
        j = min(len(out), i + len(sound))
        out[i:j] += sound[: j - i]
    return out


def lowpass(signal: np.ndarray, cutoff: float) -> np.ndarray:
    alpha = 1 - np.exp(-2 * np.pi * cutoff / RATE)
    out = np.zeros_like(signal)
    acc = 0.0
    for i, value in enumerate(signal):
        acc += alpha * (value - acc)
        out[i] = acc
    return out


def normalize(signal: np.ndarray, peak_db: float) -> np.ndarray:
    peak = np.max(np.abs(signal)) or 1.0
    return signal / peak * (10 ** (peak_db / 20))


def money_in() -> np.ndarray:
    """**رنّةُ نقودٍ لطيفة**: جرسان صاعدان (مي٦ ثمّ لا٦) ولمعةٌ خفيفةٌ فوقهما."""
    sparkle_noise = rng.standard_normal(int(RATE * 0.18))
    sparkle = (sparkle_noise - lowpass(sparkle_noise, 5000)) * env(len(sparkle_noise), 0.002, 0.04) * 0.25
    return normalize(place(1.0, (0.0, bell(1318.5, 0.9, 0.22)), (0.09, bell(1760.0, 0.9, 0.28)), (0.0, sparkle)), -3)


def money_out() -> np.ndarray:
    """**مالٌ خارجٌ أو معلَّق**: نغمتا خشبٍ هادئتان هابطتان — خبرٌ لا احتفال."""
    marimba = ((1.0, 1.0), (3.9, 0.12))
    return normalize(place(0.75, (0.0, bell(784.0, 0.6, 0.16, marimba)), (0.13, bell(587.3, 0.6, 0.2, marimba))), -4)


def account() -> np.ndarray:
    """**نغمةٌ خفيفةٌ ناعمة**: دو٦ تنزلق إلى صول٦ بهجومٍ ليّن."""
    x = t(0.7)
    freq = 1046.5 + (1568.0 - 1046.5) * np.clip(x / 0.12, 0, 1) ** 0.6
    phase = 2 * np.pi * np.cumsum(freq) / RATE
    tone = (np.sin(phase) + 0.15 * np.sin(2 * phase)) * env(len(x), 0.025, 0.22)
    return normalize(tone, -5)


def problem() -> np.ndarray:
    """**تنبيهٌ مميّزٌ غيرُ حادّ**: ثالثةٌ صغرى هابطةٌ مرّتين (لا٥ ← فا#٥) بموجةٍ مدوَّرة."""
    def note(freq: float, seconds: float) -> np.ndarray:
        x = t(seconds)
        body = np.sin(2 * np.pi * freq * x) + 0.18 * np.sin(2 * np.pi * 3 * freq * x) + 0.06 * np.sin(2 * np.pi * 5 * freq * x)
        return body * env(len(x), 0.018, 0.16)

    return normalize(place(0.75, (0.0, note(880.0, 0.22)), (0.17, note(740.0, 0.3)), (0.38, note(880.0, 0.14)), (0.48, note(740.0, 0.26))), -3)


def ride() -> np.ndarray:
    """**نقرةٌ هادئة** — كتلةُ خشبٍ صغيرةٌ منخفضةُ الصوت، فلا تصخب ساعةُ الذروة."""
    x = t(0.14)
    knock = (np.sin(2 * np.pi * 1850 * x) + 0.4 * np.sin(2 * np.pi * 2960 * x)) * env(len(x), 0.001, 0.018)
    click_noise = rng.standard_normal(len(x))
    click = lowpass(click_noise, 3000) * env(len(x), 0.0005, 0.004) * 0.6
    return normalize(knock + click, -12)


def feedback() -> np.ndarray:
    """**رسالةٌ وصلت**: فقاعةٌ تصعد ثمّ نغمةٌ قصيرةٌ تستقرّ."""
    x = t(0.4)
    freq = 520 + 600 * np.clip(x / 0.06, 0, 1)
    phase = 2 * np.pi * np.cumsum(freq) / RATE
    tone = np.sin(phase) * env(len(x), 0.006, 0.12)
    return normalize(tone, -5)


SOUNDS = {
    "money_in": money_in,
    "money_out": money_out,
    "account": account,
    "problem": problem,
    "ride": ride,
    "feedback": feedback,
}


def write(path: Path, signal: np.ndarray) -> None:
    data = (np.clip(signal, -1, 1) * 32767).astype("<i2").tobytes()
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(data)


if __name__ == "__main__":
    target = Path(sys.argv[1])
    target.mkdir(parents=True, exist_ok=True)
    for name, make in SOUNDS.items():
        signal = make()
        write(target / f"alert_{name}.wav", signal)
        print(f"{name}: {len(signal) / RATE:.2f}s peak {20 * np.log10(np.max(np.abs(signal))):.1f} dBFS")
