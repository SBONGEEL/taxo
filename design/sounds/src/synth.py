"""«بيب بيب TAXO» — مُركِّبٌ أصليٌّ من الصفر (numpy): لا عيّنة ولا مكتبةَ أصوات، فالحقوقُ كلُّها لـTAXO.

العائلة: «بيب بيب» (نغمتان قصيرتان في نطاق ١–٣ كيلوهرتز يخترق ضجيجَ السيّارة) + توقيعٌ قصير «تا-كسو» (فاصلةٌ صاعدة: خامسةٌ ثمّ أوكتاف).
ثلاثةُ أنماط × ثلاثةُ أصوات (طلبُ الكبتن يدور · «الكابتن وصل» · تحديثٌ لطيف).
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

SR = 48000
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
OUT.mkdir(parents=True, exist_ok=True)


def t(sec: float) -> np.ndarray:
    return np.arange(int(sec * SR)) / SR


def env(n: int, attack: float = 0.004, release: float = 0.03, decay: float | None = None) -> np.ndarray:
    e = np.ones(n)
    a = max(1, int(attack * SR))
    r = max(1, int(release * SR))
    e[:a] = np.linspace(0, 1, a)
    e[-r:] *= np.linspace(1, 0, r)
    if decay is not None:
        e *= np.exp(-np.arange(n) / SR / decay)
    return e


def beep(freq: float, dur: float, *, bright: float = 0.25) -> np.ndarray:
    """بيبٌ نظيف: جيبٌ ومعه توافقيّان خفيفان — يُسمع في سمّاعة هاتفٍ رخيص ولا يخدش."""
    x = t(dur)
    s = np.sin(2 * np.pi * freq * x) + bright * np.sin(2 * np.pi * 2 * freq * x) + 0.5 * bright * np.sin(2 * np.pi * 3 * freq * x)
    return s * env(len(x), 0.004, 0.025)


def bell(freq: float, dur: float, *, decay: float = 0.35, ratio: float = 2.76, index: float = 1.2) -> np.ndarray:
    """جرسٌ بتعديل التردّد (FM) — رنينٌ معدنيٌّ لطيف."""
    x = t(dur)
    mod = index * np.exp(-x / (decay * 0.6)) * np.sin(2 * np.pi * freq * ratio * x)
    s = np.sin(2 * np.pi * freq * x + mod)
    return s * env(len(x), 0.002, 0.05, decay)


def marimba(freq: float, dur: float, *, decay: float = 0.28) -> np.ndarray:
    """ضربةٌ خشبيّةٌ دافئة (مارِمبا مركَّبة): أساسيٌّ وجزئيّان غيرُ متوافقين يخبوان أسرع."""
    x = t(dur)
    s = (np.sin(2 * np.pi * freq * x) * np.exp(-x / decay)
         + 0.35 * np.sin(2 * np.pi * freq * 3.93 * x) * np.exp(-x / (decay * 0.25))
         + 0.15 * np.sin(2 * np.pi * freq * 9.2 * x) * np.exp(-x / (decay * 0.1)))
    return s * env(len(x), 0.002, 0.04)


def pad(freqs: list[float], dur: float, level: float = 0.18) -> np.ndarray:
    x = t(dur)
    s = sum(np.sin(2 * np.pi * f * x) + 0.3 * np.sin(2 * np.pi * f * 1.003 * x) for f in freqs)
    return level * s * env(len(x), 0.08, 0.25)


def place(track: np.ndarray, sound: np.ndarray, at: float, gain: float = 1.0) -> None:
    i = int(at * SR)
    j = min(len(track), i + len(sound))
    track[i:j] += gain * sound[: j - i]


def echo(x: np.ndarray, delay: float = 0.11, fb: float = 0.28, mix: float = 0.25) -> np.ndarray:
    d = int(delay * SR)
    y = x.copy()
    for k in range(1, 5):
        if d * k >= len(x):
            break
        y[d * k:] += mix * (fb ** (k - 1)) * x[: len(x) - d * k]
    return y


def finish(x: np.ndarray, peak_db: float = -1.0) -> np.ndarray:
    x = x - np.mean(x)
    # مرشّحٌ عالٍ لطيف (١٥٠ هرتز) — السمّاعاتُ الصغيرة لا تحمل الجهير، وطاقتُه تُضيع الارتفاع
    alpha = 1 / (1 + 2 * np.pi * 150 / SR)
    y = np.zeros_like(x)
    prev_x = prev_y = 0.0
    for i, v in enumerate(x):
        prev_y = alpha * (prev_y + v - prev_x)
        prev_x = v
        y[i] = prev_y
    peak = np.max(np.abs(y)) or 1.0
    return y / peak * (10 ** (peak_db / 20))


def write(name: str, x: np.ndarray) -> None:
    pcm = np.clip(x, -1, 1)
    data = (pcm * 32767).astype("<i2").tobytes()
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data)
    print("WROTE", name, f"{len(x) / SR:.2f}s")


# النغماتُ (هرتز) — G6 للبيب، والتوقيعُ C6 → G6 → C7 («تا-كسو»)
G6, C6, E6, G5, C7, A5, CS6, E5, B5 = 1568.0, 1046.5, 1318.5, 784.0, 2093.0, 880.0, 1108.7, 659.3, 987.8

# ------------------------------------------------------------------ النمط ١ — إلكترونيٌّ نظيف + جرسٌ قصير


def opt1_signature(track: np.ndarray, at: float, gain: float = 0.8) -> None:
    for k, f in enumerate((C6, G6, C7)):
        place(track, bell(f, 0.6, decay=0.22), at + 0.075 * k, gain * (0.9 if k < 2 else 0.75))


def opt1_driver() -> np.ndarray:
    cycle = 2.6
    x = np.zeros(int(cycle * SR))
    for k in range(2):  # «بيب بيب» مرّتين
        base = k * 0.62
        place(x, beep(G6, 0.12), base)
        place(x, beep(G6, 0.12), base + 0.2)
    opt1_signature(x, 1.32)
    return x


def opt1_rider() -> np.ndarray:
    x = np.zeros(int(1.5 * SR))
    place(x, beep(G6, 0.1, bright=0.15), 0.0, 0.8)
    place(x, beep(G6, 0.1, bright=0.15), 0.17, 0.8)
    for k, f in enumerate((G6, C7)):
        place(x, bell(f, 0.8, decay=0.28), 0.42 + 0.09 * k, 0.75)
    return x


def opt1_update() -> np.ndarray:
    x = np.zeros(int(0.8 * SR))
    place(x, bell(G6, 0.6, decay=0.18, index=0.6), 0.0, 0.6)
    place(x, bell(C7, 0.6, decay=0.2, index=0.6), 0.08, 0.5)
    return x


# ------------------------------------------------------------------ النمط ٣ — موسيقيٌّ دافئ (مارِمبا + وسادة)


def opt3_driver() -> np.ndarray:
    cycle = 2.8
    x = np.zeros(int(cycle * SR))
    for k in range(2):
        base = k * 0.6
        place(x, marimba(A5 * 2, 0.35), base, 0.9)
        place(x, marimba(A5 * 2, 0.35), base + 0.18, 0.9)
    phrase = ((A5, 1.3), (CS6, 1.42), (E6, 1.54), (A5 * 2, 1.7))
    for f, at in phrase:
        place(x, marimba(f, 0.9, decay=0.4), at, 0.85)
    place(x, pad([A5 / 2, CS6 / 2, E6 / 2], 1.2), 1.3)
    return echo(x, 0.12, 0.3, 0.18)


def opt3_rider() -> np.ndarray:
    x = np.zeros(int(1.8 * SR))
    place(x, marimba(A5 * 2, 0.3), 0.0, 0.8)
    place(x, marimba(A5 * 2, 0.3), 0.16, 0.8)
    for f, at in ((E6, 0.4), (A5 * 2, 0.52)):
        place(x, marimba(f, 1.0, decay=0.45), at, 0.85)
    place(x, pad([A5 / 2, E6 / 2], 1.0, 0.12), 0.4)
    return echo(x, 0.12, 0.3, 0.15)


def opt3_update() -> np.ndarray:
    x = np.zeros(int(0.9 * SR))
    place(x, marimba(E6, 0.7, decay=0.3), 0.0, 0.6)
    place(x, marimba(A5 * 2, 0.7, decay=0.35), 0.1, 0.55)
    return echo(x, 0.1, 0.25, 0.12)


# ------------------------------------------------------------------ النمط ٢ — «بيب بيب» ثمّ «TAXO» بصوت (الصوتُ يُضاف من ElevenLabs)


def opt2_beeps_driver() -> np.ndarray:
    x = np.zeros(int(1.3 * SR))
    for k in range(2):
        base = k * 0.6
        place(x, beep(G6, 0.12), base)
        place(x, beep(G6, 0.12), base + 0.2)
    return x


def opt2_beeps_rider() -> np.ndarray:
    x = np.zeros(int(0.45 * SR))
    place(x, beep(G6, 0.1, bright=0.15), 0.0, 0.8)
    place(x, beep(G6, 0.1, bright=0.15), 0.17, 0.8)
    return x


if __name__ == "__main__":
    write("opt1_driver_cycle", finish(opt1_driver()))
    write("opt1_rider", finish(opt1_rider()))
    write("opt1_update", finish(opt1_update(), -6.0))
    write("opt3_driver_cycle", finish(opt3_driver()))
    write("opt3_rider", finish(opt3_rider()))
    write("opt3_update", finish(opt3_update(), -6.0))
    write("opt2_beeps_driver", finish(opt2_beeps_driver()))
    write("opt2_beeps_rider", finish(opt2_beeps_rider()))
