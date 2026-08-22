"""صورةُ الكبتن كما يراها الراكب — **واحدةٌ للجميع في شكلها وطولها**.

**العلّةُ شكلٌ عام** (قرارُ المالك 2026-08-22): **امتيازٌ يُمنح لفئةٍ يصير
علامةً عليها إن كان غيابُه مرئياً.** فالإعفاءُ من الصورة — وهو حمايةٌ للسائقة
— كان **يكشفها بالزمن**: كلُّ كبتنٍ غيرِ مُعفى يرفع صورتَه ليُعتمد فتُراجَع
وتظهر، **فمن لا تظهر صورتُه أبداً مُعفاةٌ، أي امرأة**.

**والردُّ الواحدُ كان متطابقاً فعلاً** (٤٠٤ بنفس الجسم) — **ولم يكن ذلك
كافياً**: الوشايةُ في الحالة المستقرّة لا في اللحظة. **فالحمايةُ ألّا يُميَّز
المُعفى**، لا أن يُمنح الإعفاء.

---

**فالعقدُ صار**: كلُّ نداءٍ يردّ **٢٠٠ بصورة** — الحقيقيةَ لمن رُوجعت
صورتُه، **وحرفَ اسمه مرسوماً** لمن سواه. **وثلاثُ قنواتٍ تُغلق معاً**:

1. **رمزُ الحالة**: ٢٠٠ دائماً — فلا ٤٠٤ يُعدّ.
2. **النوع**: `image/jpeg` دائماً — ولو كان الأصلُ PNG، فيُعاد ترميزُه.
3. **الطول**: **ثابتٌ بالبايت** (`FRAME_BYTES`) — تُحشى الصورةُ بعدَ نهايتها
   حتى تبلغه. **ولولا الحشو لبقي الطولُ قناة**: صورةُ وجهٍ ٤٠ كيلوبايت وحرفٌ
   مرسومٌ ٣ — ومن يعدّ البايتات يعرف أيَّهما.

**والحشوُ بعد علامة نهاية JPEG** (`FFD9`): كلُّ قارئٍ يقف عندها، فالبايتاتُ
بعدها لا تُفكّ ولا تُرسم — **ولا تُغيّر الصورة**.

**ولا حقلَ `has_photo` ولا ما يشبهه** (قرارُ المالك): الطلبُ هو الجواب،
وحقلٌ ثانٍ يعيد الوشايةَ من بابٍ آخر.
"""

from __future__ import annotations

import hashlib
import io

from PIL import Image, ImageDraw, ImageFont

#: **قياسُ العرض لا قياسُ التخزين**: التطبيقان يرسمانها في دائرةٍ ≤ ٩٦ بكسل،
#: فـ٢٥٦ تكفي لشاشةٍ بكثافة ٣× ولا تحمّل شبكةَ كبتنٍ يعمل بالبيانات.
SIZE = 256

#: **طولُ الإطار ثابتٌ لأن الطولَ قناة.** واختيرَ فوقَ أكبرِ ترميزٍ متوقَّعٍ
#: لصورةٍ بهذا القياس (قِيس: وجهٌ حقيقيٌّ ≈ ١٨–٣٤ ك.ب عند الجودة ٧٥)، فيبقى
#: هامشٌ ولا يُرفض شيء. **ومن تجاوزه** تُخفَّض جودتُه حتى يدخل — ولا يُقصّ.
FRAME_BYTES = 65_536

_QUALITIES = (75, 60, 45, 30, 20)

#: ألوانُ الخلفية — من لوحة التصميم، **ومشتقةٌ من الاسم لا عشوائية**: الأيقونةُ
#: نفسُها لصاحبها في كلِّ رحلة، فلا يُقرأ تبدّلُ اللون تبدّلَ شخص.
_BACKGROUNDS = (
    (0x1F, 0x2A, 0x37), (0x2B, 0x2F, 0x45), (0x33, 0x2A, 0x3E),
    (0x1E, 0x35, 0x38), (0x3A, 0x2E, 0x26), (0x27, 0x33, 0x2A),
)


def _initial(name: str) -> str:
    cleaned = (name or "").strip()
    return cleaned[0] if cleaned else "؟"


def _letter_image(name: str) -> Image.Image:
    """حرفٌ على خلفيةٍ — **نظيرُ ما كان التطبيقُ يرسمه**، فلا يتغيّر ما يُرى."""
    digest = hashlib.blake2s(name.encode(), digest_size=2).digest()
    background = _BACKGROUNDS[digest[0] % len(_BACKGROUNDS)]
    canvas = Image.new("RGB", (SIZE, SIZE), background)
    draw = ImageDraw.Draw(canvas)
    letter = _initial(name)
    # **خطُّ المكتبة الافتراضيُّ يكفي**: حرفٌ واحدٌ في دائرة، ولا نحمّل الصورةَ
    # ملفَّ خطٍّ عربيٍّ لأجل محرفٍ واحد
    try:
        font = ImageFont.load_default(size=SIZE // 2)
    except TypeError:  # pragma: no cover - نسخةٌ أقدم لا تقبل الحجم
        font = ImageFont.load_default()
    box = draw.textbbox((0, 0), letter, font=font)
    draw.text(
        ((SIZE - (box[2] - box[0])) / 2 - box[0], (SIZE - (box[3] - box[1])) / 2 - box[1]),
        letter,
        font=font,
        fill=(0xE6, 0xEA, 0xF0),
    )
    return canvas


def _encoded(image: Image.Image) -> bytes:
    """أصغرُ ترميزٍ يدخل الإطار — **ولا قصَّ**: صورةٌ مقصوصةٌ لا تُفكّ."""
    for quality in _QUALITIES:
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality, optimize=True)
        data = buffer.getvalue()
        if len(data) <= FRAME_BYTES:
            return data
    return data  # pragma: no cover - آخرُ جودةٍ هي الأصغر


def render(photo: bytes | None, *, name: str) -> bytes:
    """صورةُ الكبتن **بطولٍ ثابتٍ ونوعٍ واحد** — حقيقيةً كانت أو حرفاً.

    **وفشلُ فكِّ الصورة يُعامَل كغيابها**: ملفٌّ تالفٌ على القرص لا يجوز أن
    يُخرج ٥٠٠ **فيصير العطبُ نفسُه قناةً** — من يرى خطأً يعرف أن ثمّة ملفاً.
    """
    image: Image.Image | None = None
    if photo:
        try:
            with Image.open(io.BytesIO(photo)) as opened:
                image = opened.convert("RGB")
                image.thumbnail((SIZE, SIZE))
                framed = Image.new("RGB", (SIZE, SIZE), (0x1F, 0x2A, 0x37))
                framed.paste(
                    image, ((SIZE - image.width) // 2, (SIZE - image.height) // 2)
                )
                image = framed
        except Exception:
            image = None

    data = _encoded(image if image is not None else _letter_image(name))
    # **الحشوُ بعد `FFD9`**: القارئُ يقف عند علامة النهاية، فما بعدها لا يُرسم
    return data + b"\x00" * (FRAME_BYTES - len(data))
