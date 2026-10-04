"""تأليفُ المجموعة: كلُّ صوتٍ أحداثٌ (زمن · نوتة · صوت · شدّة) من السلّم نفسِه — ثمّ المعالجةُ نفسُها للجميع.

السلّم: **خماسيُّ ري الكبير** (D E F# A B) — يحوي نغماتِ «التوقيع» القائم في التطبيقين (A4 · D5 · E5) فلا تنقطع الهوية،
وأيُّ نغمتين منه متجاورتان لا تتنافران. **والتوقيعُ «تا-كسو»** نوتتان صاعدتان بمسافة رابعةٍ تامّة (A5 ← D6): مقطعا الاسم،
والهبوطُ على الأساس «ري» — «وصلنا».
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from make_sounds import BELL, BRIGHT, SOFT, SR, Voice, active_loudness, master, note, phone_speaker, place, true_peak_db, write_wav  # noqa: E402

# النغماتُ بالهرتز — خماسيُّ ري الكبير
D5, E5, Fs5, A5, B5 = 587.33, 659.26, 739.99, 880.00, 987.77
D6, E6, Fs6, A6 = 1174.66, 1318.51, 1479.98, 1760.00
A4, D4 = 440.00, 293.66


def ev(t: float, f: float, length: float, voice: Voice = BELL, gain: float = 1.0, body: float = 0.22) -> list[tuple[float, np.ndarray]]:
    """نوتةٌ ومعها ظلُّها بديوانٍ أدنى خافتاً — جسدٌ في السمّاعة، ويختفي بلا ضررٍ في سمّاعة الهاتف."""
    out = [(t, note(f, length, voice, gain, seed=int(f * 7 + t * 1000)))]
    if body > 0:
        out.append((t, note(f / 2, length * 0.9, SOFT, gain * body, seed=int(f * 3 + t * 777))))
    return out


SOUNDS: dict[str, dict] = {}


def sound(name: str, title: str, purpose: str, total: float, events: list[tuple[float, np.ndarray]], target_offset: float = 0.0) -> None:
    SOUNDS[name] = {"title": title, "purpose": purpose, "total": total, "events": events, "offset": target_offset}


# ١) التوقيع — «تا-كسو»
sound(
    "taxo-signature", "توقيعُ TAXO",
    "البذرة: نوتتان صاعدتان «تا-كسو» تهبطان على الأساس. يُعزف حيث يُعزف التوقيعُ اليوم (أوّلُ لمسةٍ بعد الدخول).",
    0.95,
    ev(0.00, A5, 0.55, gain=0.85) + ev(0.13, D6, 0.80, gain=1.0),
)

# ٢) طلبٌ جديد عند الكبتن — التوقيعُ مرّتين ثمّ ثالثةً تصعد؛ ٢٫٢ ث كدورة اليوم، فتبقى حلقةُ التكرار كما هي
offer = []
for start in (0.00, 0.40):
    offer += ev(start, A5, 0.32, BRIGHT, 0.80) + ev(start + 0.11, D6, 0.40, BRIGHT, 0.95)
offer += ev(0.80, A5, 0.30, BRIGHT, 0.82) + ev(0.91, D6, 0.30, BRIGHT, 0.92) + ev(1.02, Fs6, 0.95, BRIGHT, 1.0)
sound(
    "captain-new-request", "طلبُ رحلةٍ جديد — الكبتن",
    "أهمُّها: «تا-كسو» مرّتين ثمّ ثالثةٌ تصعد إلى نغمةٍ أعلى وتطول. واضحٌ يلفت على الطريق بإيقاعه لا بحدّته، "
    "ومدّتُه ٢٫٢ ثانية كنغمة اليوم فيتكرّر حتى يُجاب بالتوقيت نفسِه.",
    2.20, offer,
)

# ٣) انتهت مهلةُ الطلب أو ذهب لغيره — التوقيعُ مقلوباً، خافتاً
sound(
    "captain-request-gone", "الطلبُ لم يعد لك — الكبتن",
    "التوقيعُ هابطاً بهدوء: انتهت المهلة أو قبله كبتنٌ آخر أو ألغاه الراكب. يُخبر ولا يلوم.",
    0.75, ev(0.00, D6, 0.40, BELL, 0.8) + ev(0.14, A5, 0.55, BELL, 0.75),
)

# ٤) قبِل الكبتن — الراكب: التوقيعُ ثمّ ثالثةٌ تكمل الوتر الكبير («نعم»)
sound(
    "rider-captain-accepted", "قبِل الكبتنُ رحلتك — الراكب",
    "التوقيعُ ثمّ نغمةٌ ثالثةٌ تكمل الوتر صعوداً: خبرٌ طيّب — وُجد كبتنُك.",
    0.95, ev(0.00, A5, 0.40, BELL, 0.85) + ev(0.11, D6, 0.45, BELL, 0.9) + ev(0.22, Fs6, 0.70, BELL, 0.95),
)

# ٥) الكبتنُ يقترب — نقرتان رقيقتان على الأساس
sound(
    "rider-captain-near", "الكبتنُ يقترب — الراكب",
    "نقرتان رقيقتان على نغمةٍ واحدة: استعدّ. (لا حدثَ يطلقه اليوم — يحتاج «الاقتراب» من الخلفية.)",
    0.60, ev(0.00, D6, 0.30, BELL, 0.75, body=0.15) + ev(0.15, D6, 0.40, BELL, 0.85, body=0.15),
)

# ٦) الكبتنُ وصل — الراكب: جرسُ بابٍ بنغمات TAXO (هبوطٌ ثمّ عودة)
sound(
    "rider-captain-arrived", "الكبتنُ وصل — الراكب",
    "جرسُ بابٍ من نغمات TAXO — هبوطٌ ثمّ عودة: كبتنُك عند نقطة اللقاء، اخرج إليه. أوضحُ أصوات الراكب.",
    1.05, ev(0.00, D6, 0.45, BRIGHT, 0.9) + ev(0.17, A5, 0.45, BRIGHT, 0.85) + ev(0.34, D6, 0.70, BRIGHT, 0.95),
)

# ٧) تأكيدٌ خافتٌ لفعل الكبتن نفسِه (وصلتُ) — نقرةٌ واحدة
sound(
    "captain-confirm", "تأكيدُ فعلك — الكبتن",
    "نقرةٌ واحدةٌ خافتة حين يضغط الكبتنُ «وصلتُ»: سُمع فعلُك، بلا ضجيج.",
    0.45, ev(0.00, A5, 0.20, SOFT, 0.6, body=0.0) + ev(0.07, D6, 0.35, BELL, 0.8, body=0.1),
)

# ٨) بدأت الرحلة — صعودٌ سريعٌ «انطلقنا»
sound(
    "trip-started", "بدأت الرحلة — الاثنان",
    "ثلاثُ نغماتٍ صاعدةٍ سريعة: انطلقنا.",
    0.80, ev(0.00, A5, 0.30, BELL, 0.8) + ev(0.09, D6, 0.32, BELL, 0.88) + ev(0.18, E6, 0.60, BELL, 0.95),
)

# ٩) انتهت الرحلة — قفلةٌ تهبط وتستقرّ على الأساس
sound(
    "trip-ended", "انتهت الرحلة — الاثنان",
    "قفلةٌ تهبط ثمّ تستقرّ على الأساس: وصلنا، والرحلةُ تمّت.",
    1.10, ev(0.00, E6, 0.30, BELL, 0.8) + ev(0.12, D6, 0.30, BELL, 0.82) + ev(0.24, A5, 0.32, BELL, 0.85)
    + ev(0.40, D6, 0.85, BELL, 1.0),
)

# ١٠) نجح الدفع أو الشحن — بريقٌ صاعد
sound(
    "payment-success", "نجح الدفعُ أو الشحن — الاثنان",
    "ثلاثُ نغماتٍ تصعد سريعاً إلى بريق: وصل المال. للدفع والشحن والتحصيل وما قُيّد في المحفظة.",
    0.85, ev(0.00, D6, 0.28, BRIGHT, 0.8, body=0.15) + ev(0.07, Fs6, 0.30, BRIGHT, 0.85, body=0.12)
    + ev(0.14, A6, 0.65, BRIGHT, 0.95, body=0.1),
)

# ١١) رسالةُ محادثةٍ جديدة — نقرتان خفيفتان صاعدتان
sound(
    "chat-message", "رسالةٌ جديدة في المحادثة — الاثنان",
    "نقرتان خفيفتان صاعدتان: وصلتك رسالة. أقصرُ الأصوات وأخفّها — تتكرّر في المحادثة فلا تثقل.",
    0.45, ev(0.00, B5, 0.20, BELL, 0.7, body=0.1) + ev(0.08, E6, 0.32, BELL, 0.85, body=0.1),
)

# ١٢) إشعارٌ عامّ — التوقيعُ مصغَّراً: نغمةُ تمهيدٍ ونغمة
sound(
    "notify", "إشعارٌ عامّ — الاثنان",
    "التوقيعُ مصغَّراً: لمسةُ تمهيدٍ ثمّ نغمةُ الأساس. لكلِّ ما سوى ذلك.",
    0.65, ev(0.00, A5, 0.14, BELL, 0.55, body=0.0) + ev(0.06, D6, 0.55, BELL, 0.95),
)

# ١٣) خطأ — ليّن: هبوطُ درجةٍ واحدةٍ بصوتٍ أدكن
sound(
    "error-soft", "خطأ — الاثنان",
    "هبوطُ درجةٍ واحدةٍ بصوتٍ أدكنَ وأقصر: شيءٌ لم يتمّ — يُخبر ولا يوبّخ.",
    0.55, ev(0.00, E5, 0.28, SOFT, 0.9, body=0.2) + ev(0.15, D5, 0.38, SOFT, 0.95, body=0.2),
)

# ١٤) إرشادُ المنعطف — لـ«صوت الإرشاد» إن أُقرّ
sound(
    "turn-cue", "منعطفٌ قريب — الكبتن",
    "نقرتان متساويتان قصيرتان قبل المنعطف: لـ«صوت الإرشاد» في الإعدادات إن أُقرّ — بلا كلام.",
    0.40, ev(0.00, A5, 0.16, BELL, 0.8, body=0.0) + ev(0.12, A5, 0.24, BELL, 0.85, body=0.0),
)


def main(out: Path) -> None:
    import make_sounds

    out.mkdir(parents=True, exist_ok=True)
    report = []
    for name, spec in SOUNDS.items():
        raw = place(spec["events"], spec["total"])
        # الهدفُ نفسُه للجميع، وانحرافُ بعضها مقصودٌ ومكتوب (الخطأُ أليَن، والطلبُ أوضح بدرجة)
        saved = make_sounds.TARGET_LKFS
        make_sounds.TARGET_LKFS = saved + spec["offset"]
        x = master(raw)
        make_sounds.TARGET_LKFS = saved
        path = out / f"{name}.wav"
        write_wav(path, x)
        low = float(np.sum(np.abs(np.fft.rfft(x))[: int(500 * len(x) / SR)] ** 2) / np.sum(np.abs(np.fft.rfft(x)) ** 2))
        report.append(
            {
                "file": path.name,
                "title": spec["title"],
                "purpose": spec["purpose"],
                "seconds": round(len(x) / SR, 2),
                "lkfs": round(active_loudness(x), 1),
                "lkfs_phone": round(active_loudness(phone_speaker(x)), 1),
                "true_peak_dbtp": round(true_peak_db(x), 1),
                "below_500hz_share": round(low, 3),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for row in report:
        print(f"{row['file']:28} {row['seconds']:5}s  {row['lkfs']:6} LKFS  phone {row['lkfs_phone']:6}  TP {row['true_peak_dbtp']:5}  <500Hz {row['below_500hz_share']}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
