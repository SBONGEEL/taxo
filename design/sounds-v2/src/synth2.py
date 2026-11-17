"""المجموعةُ الثانية «بيب بيب TAXO» — خمسةُ خيارات، كلٌّ: نغمةُ الكبتن (دورة) · «الكابتن وصل» · أربعُ نسخٍ ناعمة.

كلُّ صوتٍ هنا **مُركَّبٌ من الصفر بالرياضيات** (numpy): البوقُ نغمتان موسيقيّتان مرشَّحتان لا تسجيلُ بوقٍ حقيقيّ، واللحنُ
أصيلٌ كُتب هنا نوتةً نوتة. والصوتُ البشريُّ «TAXO» من صوتٍ **مصمَّمٍ من وصفٍ نصّيّ** في ElevenLabs (لا استنساخ).
"""
import wave
from pathlib import Path

import numpy as np

SR = 48000
D = Path(__file__).parent
OUT = D / "out"
OUT.mkdir(exist_ok=True)


def t(sec):
    return np.arange(int(SR * sec)) / SR


def env(n, a=0.006, r=0.05, hold=None):
    e = np.ones(n)
    na, nr = int(SR * a), int(SR * r)
    e[:na] = np.linspace(0, 1, na) if na else 1
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr) ** 1.5
    return e


def lowpass(x, fc):
    # مرشِّحٌ أحاديُّ القطب مرّتين — نعومةٌ بلا رنين
    a = np.exp(-2 * np.pi * fc / SR)
    for _ in range(2):
        y = np.empty_like(x)
        acc = 0.0
        for i in range(len(x)):
            acc = (1 - a) * x[i] + a * acc
            y[i] = acc
        x = y
    return x


def lp_fast(x, fc):
    # نفسُ المرشِّح بالتصفية الأسّيّة عبر التلافيف القصيرة (أسرع)
    a = np.exp(-2 * np.pi * fc / SR)
    k = (1 - a) * a ** np.arange(int(SR * 0.01))
    y = np.convolve(x, k)[: len(x)]
    return np.convolve(y, k)[: len(x)]


def saw(f, tt):
    # منشارٌ محدودُ التوافقيّات
    y = np.zeros_like(tt)
    for k in range(1, int(min(18, 9000 / max(float(np.max(f)), 1))) + 1):
        y += ((-1) ** (k + 1)) * np.sin(2 * np.pi * k * f * tt) / k
    return y * 0.6


def sine(f, tt):
    # جيبيٌّ ومعه ثالثةٌ خفيفة — بوقٌ مستديرٌ ناعم
    return np.sin(2 * np.pi * f * tt) + 0.18 * np.sin(2 * np.pi * 3 * f * tt)


def square(f, tt):
    y = np.zeros_like(tt)
    for k in range(1, int(min(15, 9000 / max(float(np.max(f)), 1))) + 1, 2):
        y += np.sin(2 * np.pi * k * f * tt) / k
    return y * 0.8


def honk(f1, f2, dur, wave_fn, cutoff, bend=0.0):
    """نقرةُ بوقٍ واحدة: نغمتان (الفاصلُ يقرّر الطابع)، **وبصوتٍ موسيقيٍّ مرشَّح** لا بوقِ سيّارةٍ في الخارج."""
    tt = t(dur)
    glide = 1 + bend * np.minimum(tt / 0.04, 1)
    x = wave_fn(f1 * glide, tt) + 0.8 * wave_fn(f2 * glide, tt)
    x = lp_fast(x, cutoff) * env(len(tt), 0.008, 0.05)
    return x


def bell(f, dur, bright=1.0, decay=3.0):
    """جرسٌ FM — ماريمبا/جرسٌ زجاجيّ بحسب `bright`."""
    tt = t(dur)
    mod = np.sin(2 * np.pi * f * 3.5 * tt) * bright * np.exp(-tt * 9)
    x = np.sin(2 * np.pi * f * tt + 2.2 * mod) * np.exp(-tt * decay)
    x += 0.25 * np.sin(2 * np.pi * 2 * f * tt) * np.exp(-tt * decay * 2)
    return x * env(len(tt), 0.002, 0.03)


def pad(f, dur, level=0.15):
    tt = t(dur)
    x = sum(np.sin(2 * np.pi * f * m * tt) / m for m in (1, 2, 3))
    return x * level * env(len(tt), 0.08, 0.3)


def note(name):
    names = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[pitch] + 12 * (octave + 1) - 69) / 12)


def place(buf, x, at, gain=1.0):
    i = int(at * SR)
    end = min(len(buf), i + len(x))
    buf[i:end] += x[: end - i] * gain
    return buf


def reverb(x, wet=0.18, size=0.06):
    y = x.copy()
    for k, g in ((size, 0.5), (size * 1.7, 0.35), (size * 2.9, 0.22), (size * 4.3, 0.13)):
        d = int(SR * k)
        y[d:] += x[:-d] * g * wet * 3
    return y


def read_voice(name):
    with wave.open(str(D / "raw" / f"{name}.wav")) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768


def norm(x, peak_db=-1.0, rms_db=-16.0):
    """ارتفاعٌ موحَّد: RMS نحو −16 dBFS، **والقمّةُ لا تتجاوز −1 dBFS** (لا قصّ)."""
    x = x - np.mean(x)
    rms = np.sqrt(np.mean(x ** 2)) + 1e-12
    x = x * (10 ** (rms_db / 20) / rms)
    peak = np.max(np.abs(x))
    lim = 10 ** (peak_db / 20)
    if peak > lim:
        # حدٌّ ناعم: يضغط ما فوق 70% من الحدّ بدل القصّ
        knee = 0.7 * lim
        over = np.abs(x) > knee
        x[over] = np.sign(x[over]) * (knee + (lim - knee) * np.tanh((np.abs(x[over]) - knee) / (lim - knee)))
    return x


def write(name, x):
    x = np.clip(x, -1, 1)
    with wave.open(str(OUT / f"{name}.wav"), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


# ═══════════════ الخياراتُ الخمسة — بوقٌ وصوتٌ ولحنٌ مختلفةٌ في كلٍّ
OPTIONS = {
    1: dict(  # ناعمٌ أنيق: بوقٌ ناعمٌ مستدير (مثلّث/جيبيّ)، أجراسٌ زجاجيّة، صوتٌ دافئٌ هادئ
        title="soft-elegant", horn=(note("E5"), note("G#5"), sine, 2600, 0.0), honk_len=0.11, gap=0.09,
        voice="taxo_warm_b", motif=["E5", "G#5", "B5", "E6"], rhythm=[0.18, 0.18, 0.18, 0.5], bright=0.6, decay=3.5,
        bass="E3"),
    2: dict(  # مشرقٌ نشيط: بوقٌ مربّعٌ لامع، ماريمبا سريعة، صوتٌ مشرق
        title="bright-energetic", horn=(note("A5"), note("C#6"), square, 4200, 0.03), honk_len=0.09, gap=0.07,
        voice="taxo_bright_c", motif=["A5", "C#6", "E6", "A6", "E6", "A6"], rhythm=[0.11, 0.11, 0.11, 0.2, 0.11, 0.35], bright=1.4, decay=5.0,
        bass="A3"),
    3: dict(  # هادئٌ فاخر: بوقٌ منخفضٌ دافئ، أجراسٌ بطيئةٌ وفراشٌ ناعم، صوتٌ دافئٌ بطيء
        title="calm-premium", horn=(note("D5"), note("F#5"), saw, 1800, 0.0), honk_len=0.13, gap=0.11,
        voice="taxo_warm_d", motif=["D5", "A5", "F#5", "D6"], rhythm=[0.26, 0.26, 0.26, 0.7], bright=0.4, decay=2.4,
        bass="D3"),
    4: dict(  # ودودٌ شابّ: بوقٌ بانحناءةٍ صاعدةٍ مرحة، لحنٌ متقافز، صوتٌ شابّ
        title="friendly-young", horn=(note("G5"), note("B5"), saw, 3400, 0.06), honk_len=0.1, gap=0.08,
        voice="taxo_bright_a", motif=["G5", "B5", "D6", "B5", "G6"], rhythm=[0.13, 0.13, 0.13, 0.13, 0.45], bright=1.0, decay=4.2,
        bass="G3"),
    5: dict(  # أفضلُ فكرة: البوقُ نفسُه أوّلُ نوتتين في اللحن — «بيب بيب» يصير موسيقى، و«TAX-OH» تحطّ على قرارها
        title="best-idea", horn=(note("F5"), note("A5"), square, 3000, 0.02), honk_len=0.1, gap=0.08,
        voice="taxo_warm_c", motif=["F5", "A5", "C6", "F6", "C6"], rhythm=[0.14, 0.14, 0.14, 0.3, 0.5], bright=0.9, decay=3.2,
        bass="F3", horn_is_melody=True),
}


def honk_pair(o):
    f1, f2, fn, cut, bend = o["horn"]
    h = honk(f1, f2, o["honk_len"], fn, cut, bend)
    buf = np.zeros(int(SR * (2 * o["honk_len"] + o["gap"] + 0.05)))
    place(buf, h, 0, 0.55)
    place(buf, h, o["honk_len"] + o["gap"], 0.6)
    return buf


def motif(o, scale=1.0, gain=0.5):
    total = sum(o["rhythm"]) + 1.2
    buf = np.zeros(int(SR * total))
    at = 0.0
    for n, r in zip(o["motif"], o["rhythm"]):
        place(buf, bell(note(n) * scale, max(r, 0.25) + 0.9, o["bright"], o["decay"]), at, gain)
        at += r
    place(buf, pad(note(o["bass"]), at + 0.6), 0, 0.6)
    return buf


def arrived(o):
    """«الكابتن وصل» — نحو ثانيتين: بيب بيب ثمّ «TAXO» كتاكسي وصل الباب."""
    v = read_voice(o["voice"])
    hp = honk_pair(o)
    buf = np.zeros(int(SR * 2.1))
    place(buf, hp, 0.0)
    place(buf, v, len(hp) / SR - 0.02, 0.95)
    # تذييلٌ موسيقيٌّ قصير يُغلق الجملة
    place(buf, bell(note(o["motif"][-1]), 0.9, o["bright"] * 0.6, o["decay"]), len(hp) / SR + len(v) / SR + 0.02, 0.3)
    return reverb(buf, 0.12)


def ringtone(o):
    """نغمةُ الكبتن — **دورةٌ واحدةٌ تُكرَّر حتى القبول أو الرفض أو المهلة**: بيب بيب + «TAXO» مرّةً، ثمّ لحنٌ مرّتين بلا صوت.
    **فالصوتُ البشريُّ مرّةً كلَّ ~٧ ثوانٍ لا أكثر**، واللحنُ (أجراسُ هاتف) يحمل الرنينَ فلا يُظنّ بوقاً في الطريق."""
    v = read_voice(o["voice"])
    hp = honk_pair(o)
    m = motif(o)
    mlen = sum(o["rhythm"]) + 0.35
    cycle = len(hp) / SR + len(v) / SR + 0.25 + 3 * mlen + 0.6
    buf = np.zeros(int(SR * cycle))
    place(buf, hp, 0.0)
    at = len(hp) / SR - 0.02
    place(buf, v, at, 0.95)
    at += len(v) / SR + 0.25
    place(buf, m, at)
    place(buf, motif(o, 1.0, 0.45), at + mlen)
    # **ثالثةٌ أخفض بأوكتاف** — تطيل الدورةَ إلى نحو سبع ثوانٍ فلا يعود الصوتُ البشريُّ سريعاً، وتنوّع فلا يُملّ
    place(buf, motif(o, 0.5, 0.5), at + 2 * mlen)
    # نبضٌ خفيفٌ تحت اللحن يجعله «يرنّ» كهاتف ويُسمع في سيّارةٍ صاخبة
    for k in range(int((cycle - at) / 0.5)):
        place(buf, bell(note(o["bass"]) * 2, 0.2, 0.3, 14), at + k * 0.5, 0.18)
    return reverb(buf, 0.1)


def soft(o, kind):
    """النسخُ الناعمة القصيرة — من لحن الخيار نفسِه، بلا صوتٍ بشريّ."""
    ns = o["motif"]
    seq = {
        "accepted": ([ns[0], ns[1]], [0.12, 0.4]),                      # «قُبل»: صعودٌ من نوتتين
        "started": ([ns[0], ns[2]], [0.14, 0.45]),                      # «بدأت»: قفزةٌ إلى الأمام
        "ended": ([ns[2], ns[1], ns[0]], [0.12, 0.12, 0.5]),            # «انتهت»: نزولٌ يستقرّ
        "payment": ([ns[0], ns[2], ns[-1]], [0.09, 0.09, 0.55]),        # «نجح الدفع»: ثلاثٌ صاعدةٌ لامعة
    }[kind]
    buf = np.zeros(int(SR * (sum(seq[1]) + 0.9)))
    at = 0.0
    for n, r in zip(*seq):
        place(buf, bell(note(n), r + 0.7, o["bright"] * 0.7, o["decay"] + 1), at, 0.5)
        at += r
    if kind == "accepted":
        # نقرةُ بوقٍ واحدةٌ هامسة — التوقيعُ نفسُه بأخفّ صوته
        f1, f2, fn, cut, bend = o["horn"]
        place(buf, honk(f1, f2, 0.07, fn, cut * 0.7, bend), 0.0, 0.18)
    return reverb(buf, 0.1)


if __name__ == "__main__":
    for n, o in OPTIONS.items():
        write(f"option{n}_driver_ride_request", norm(ringtone(o), rms_db=-15))
        write(f"option{n}_rider_captain_arrived", norm(arrived(o), rms_db=-15))
        for kind in ("accepted", "started", "ended", "payment"):
            write(f"option{n}_soft_{kind}", norm(soft(o, kind), rms_db=-19))
        print("option", n, o["title"])
