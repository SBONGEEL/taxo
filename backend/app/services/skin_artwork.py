"""بابُ رسومات المركبات — **يبتلع بايتات المشرف ويُخرج مقاسين** (2026-08-22).

**ومجالٌ جديدٌ بلا حارسٍ سابق**: كلُّ ما رُفع في هذا المشروع قبل اليوم مرّ
بـ`core/storage.save` — وثيقةٌ تُراجَع أو صورةُ وجه، **ولا واحدةٌ منها تُخدَم
لمتصفحٍ كملفٍّ قد يُفسَّر**. ورسمةُ المركبة تُخدَم للجميع وقد تكون **SVG**،
وهي مستندٌ برمجيٌّ كامل لا صورة: من يرفعها يرفع كوداً يعمل في أصلنا.

---

## ١) البابُ واحد، والحارسُ يحرسه

**كلُّ مسارٍ يأخذ `UploadFile` يمرّ بـ`storage.save` أو `skin_artwork.ingest`**
— و`tests/test_upload_doors.py` يمسح الشجرةَ ويُسقط البناءَ على بابٍ ثالث.
والقاعدةُ المكتوبةُ لا تكفي، وهو درسُ `check:flags` نفسُه.

## ٢) والنوعُ من البايتات لا من الترويسة

`Content-Type` حقلٌ يكتبه العميل. **والحكمُ هنا على المحتوى**: التوقيعُ
الثنائيُّ لِما هو نقطيّ — يُقرأ من `storage.sniff` **ولا يُكتب ثانيةً**،
فبيتان لقائمة توقيعاتٍ يفترقان أوّلَ إضافة — **ومحاولةُ تحليلٍ XML صارمة**
لِما يدّعي أنه SVG. وملفٌّ لا ينجح في أيِّهما يُرفض ولا يُخزَّن.

## ٣) والسقفان اثنان لا واحد — **وهذا هو بيتُ القصيد**

- **سقفُ البايتات** يُفرض **بالقراءة على دفعات** لا بـ`Content-Length` (يكتبها
  العميلُ أيضاً)، كما يفعل `storage.save`.
- **وسقفُ البكسل** — والأولُ **لا يغني عنه**: ملفُّ PNG حجمُه بضعُ كيلوبايتات
  قد يُفكّ إلى ٥٠٠٠٠×٥٠٠٠٠ بكسل، أي **غيغابايتاتٌ في ذاكرة الخادم**. فمن
  يقيس الحجمَ وحدَه يفتح بابَ إسقاطِ الخدمة **بملفٍّ يمرّ من كلِّ فحصٍ عنده**.
  `Image.MAX_IMAGE_PIXELS` يُضبط صراحةً، و`DecompressionBombError` تُترجَم
  رفضاً مفهوماً لا ٥٠٠.

## ٤) و**SVG قائمةُ سماحٍ ثم إعادةُ كتابة** — لا تنقيةُ نصّ

التنقيةُ بالحذف تُبقي ما لم يخطر ببال كاتبها. **فالشجرةُ تُحلَّل، ويُنسخ منها
المسموحُ وحدَه إلى شجرةٍ جديدة، وتُسلسَل هذه.** ما ليس في القائمة لا يُكتب
أصلاً — فلا يحتاج أحدٌ أن يتذكّره. والفرقُ بين الاثنين هو الفرقُ بين قائمةِ
منعٍ وقائمةِ سماح.

**والعرضُ عبر `<img>` لا يشغّل سكربتاً** — هذا صحيح، **ولا يُجعل الحارسَ
الوحيد**: التنقّلُ المباشر إلى عنوان الملف يفتحه **مستنداً**، فيعمل ما فيه في
أصلنا. فثلاثُ طبقاتٍ معاً: قائمةُ السماح، **وترويساتٌ متصلّبةٌ عند العرض**
(`default-src 'none'` و`sandbox` و`nosniff`)، ورفضُ الملفِّ كلِّه — لا تنظيفُه
— حين يحمل ما يُفسَّر.

## ٥) والمقاسان ثابتان

`512` لبطاقة المتجر و`128` للخريطة — **وعشراتُ الكباتن على شاشةٍ واحدة**،
فرسمةٌ بمقاس البطاقة على الخريطة تُحمّل شبكةَ راكبٍ يعمل بالبيانات بلا أن
يُرى منها بكسلٌ زائد.

**والقصُّ آليٌّ حول السيارة** لأن توليدات الذكاء الاصطناعي تترك فراغاً مختلفاً
حول كلِّ واحدة: صورتان بنفس المقاس تُرسمان بحجمين مختلفين على الخريطة، والفرقُ
**لا يُقرأ عطباً** بل يُقرأ «هذه المركبةُ أصغر».

**والقصُّ على قناة الشفافية وحدَها** — لا على لونٍ موحَّد: خلفيةٌ بيضاءُ تُقصّ
بلونها **تأكل سيارةً بيضاء**، والعطبُ حينها يقع على المركبة لا على الهامش.

## ٦) وSVG لا يُقصّ ولا يُصغَّر — **ويُقال ذلك ولا يُدَّعى**

هي رسمةٌ متجهيّةٌ تُرسم بأيِّ مقاس، فلا معنى لنسختين بحجمين من بايتاتها.
**وما يقع فعلاً** أن `width`/`height` تُكتبان بالمقاسين و`viewBox` واحدةٌ
لهما — فلا يبقى الملفُّ بلا مقاسٍ ذاتيٍّ يقفز به التخطيط قبل تحميله.
**والإطارُ مسؤوليةُ من رسمها**، ورسوماتُ `app/assets/skins/` مؤطَّرةٌ بالبناء.

## ٧) وهذا الملفُّ يكتب على القرص — **وهو الثاني بعد `core/storage`**

القاعدةُ أن `storage` وحدَه يلمس نظامَ الملفات، **والاستثناءُ مكتوبٌ لا صامت**:

- **ما هو نقطيٌّ يُكتب بـ`storage.save`** بعد المعالجة — فيُشمّ ثانيةً، ويُنقل
  ذرّيّاً، **ويُتحقَّق من حجمه على القرص قبل إعلان النجاح** (قاعدةُ 2026-08-20)،
  كلُّ ذلك بلا نسخةٍ ثانيةٍ من منطقه هنا.
- **وSVG وحدَه يُكتب هنا**، لأن `storage.sniff` لا يعرفه **ولا يجوز أن
  يعرفه**: توسيعُ التوقيعات ليقبل نصّاً يفتح `save` لكلِّ مستدعٍ آخر. والكتابةُ
  هنا **تعيد قواعدَ `save` الثلاث** — جذرٌ واحد (`storage.root`)، واسمٌ من
  عندنا، **وتحقّقٌ من الحجم بعد النقل** — ولا تخترع رابعة.
"""

from __future__ import annotations

import io
import json
import logging
import re
import tempfile
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import anyio
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

from app.core import storage
from app.core.exceptions import (
    DocumentFileMissing,
    DocumentTooLarge,
    UnsupportedDocument,
)

logger = logging.getLogger(__name__)

Slot = Literal["store", "map"]

#: **مقاسُ بطاقة المتجر** — تُرسم في شبكةٍ عرضُها لا يتجاوز ٢٥٦ بكسل CSS،
#: فـ٥١٢ تكفي شاشةً بكثافة ٢× ولا تُضاعف الحجمَ بلا أن يُرى.
STORE_PX = 512

#: **مقاسُ الخريطة** — العلامةُ ٣٠ بكسل CSS، أي ٩٠ بكسلَ جهازٍ عند ٣×؛
#: و١٢٨ فوقها بهامش، وهي ربعُ مساحةِ ٢٥٦ في الشبكة.
MAP_PX = 128

#: **سقفُ البايتات** — ضِعفا سقفِ المستندات: رسمةٌ شفّافةٌ بعمقٍ عالٍ أكبرُ من
#: صورةِ رخصة، **والرافعُ مشرفٌ على مكتب** لا كبتنٌ على بياناتِ هاتف.
MAX_UPLOAD_BYTES = 4 * 1024 * 1024

#: **سقفُ البكسل — والحجمُ لا يغني عنه** (التفصيل في رأس الملف).
#: ٤٠ مليوناً ≈ ٦٣٠٠×٦٣٠٠: فوقَ أيِّ توليدٍ معقول، وتحتَ ما يُسقط الخدمة.
MAX_PIXELS = 40_000_000

_CHUNK = 64 * 1024

#: تخبئةُ الرسمة **عامّة**: لا تحمل هويةَ أحد، وهي ثابتةٌ ما دام اسمُ ملفها
#: (اسمٌ عشوائيٌّ يتبدّل مع كلِّ رفع) — فالتخبئةُ لا تُقادم شيئاً.
CACHE_SECONDS = 30 * 24 * 3600

#: مجلّدُ الرسومات المولَّدة داخل الحزمة — **تُشحن مع الصورة** لا تُثبَّت
#: بربطٍ خارجيّ: حاويةٌ تحتاج ملفَّ تركيبٍ صحيحاً كي لا تُعطّل ميزةً صامتةً
#: **تعطّلها** (الشكلُ الثاني عشر، `otp-template-rules.json` بعينه).
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "skins"

#: لاحقةُ ملفِّ كلِّ خانةٍ داخل `ASSETS_DIR`.
_ASSET_SUFFIX: dict[str, str] = {"store": "-store.svg", "map": "-map.svg"}

#: **مفتاحُ الرسمة المولَّدة** — حروفٌ صغيرةٌ وأرقامٌ وشرطات، فلا يصير مساراً.
_ASSET_KEY = re.compile(r"^[a-z][a-z0-9-]{1,62}$")


# ════════════════════════════════════════════════ ١) القراءةُ المسقوفة


class _BytesReader:
    """يُلبس بايتاتٍ في يدنا ثوبَ `UploadFile` — فيقبلها `storage.save`."""

    def __init__(self, data: bytes) -> None:
        self._buffer = io.BytesIO(data)

    async def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)


async def read_capped(reader: storage.AsyncReader) -> bytes:
    """يقرأ الملفَ المرفوع **على دفعاتٍ** ويقف عند السقف.

    **ولا يُقرأ `Content-Length`**: يكتبه العميل، فتصديقُه يعني أن من يكذب
    فيه يرفع ما يشاء. والدفعاتُ تجعل الرفضَ يقع **عند تجاوز السقف** لا بعد
    ابتلاع الملف كلِّه — وهي قاعدةُ `storage.save` الثالثة نفسُها.
    """
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = await reader.read(_CHUNK)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise DocumentTooLarge(
                "حجم الرسمة أكبر من المسموح "
                f"({MAX_UPLOAD_BYTES // (1024 * 1024)} ميغابايت)"
            )
        chunks.append(chunk)
    if size == 0:
        raise UnsupportedDocument("الملف فارغ")
    return b"".join(chunks)


# ════════════════════════════════════════════════ ٢) تنقيةُ SVG


class UnsafeArtwork(UnsupportedDocument):
    """رسمةٌ تحمل ما لا يُخدَم — **تُرفض كاملةً ولا تُنظَّف**.

    من رفع ملفاً فيه سكربتٌ يجب أن يعرف أنه رُفض؛ وقبولُ نصفِه **يخفي أنه كان
    هناك** — وهي قاعدةُ «وجدانُ سرٍّ يوقف ولا يُنظَّف» في مجالٍ آخر.
    """

    code = "unsafe_artwork"
    message = "الرسمة تحمل عناصر غير مسموحة — يُقبل الرسمُ والتدرّجاتُ فقط"


#: **العناصرُ المسموحة** — رسمٌ وتدرّجاتٌ وقصٌّ ومرشّحاتُ ظلّ، لا أكثر.
#: وكلُّ ما ليس هنا **لا يُكتب في المُخرَج أصلاً**: `script` و`foreignObject`
#: و`image` و`use` و`a` و`style` و`animate*` — لا يُسمّى واحدٌ منها في قائمةِ
#: منعٍ تُنسى، بل يسقط بالسكوت عنه.
ALLOWED_TAGS = frozenset(
    {
        "svg", "g", "defs", "title", "desc",
        "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
        "linearGradient", "radialGradient", "stop", "clipPath", "mask",
        "filter", "feGaussianBlur", "feOffset", "feFlood", "feComposite",
        "feMerge", "feMergeNode", "feDropShadow", "feBlend",
    }
)

#: **ما يُصاح عليه ولا يُسقط بصمت**: فرقُ من رفع رسمةً فيها عنصرٌ زخرفيٌّ لا
#: نعرفه عمّن رفع كوداً. والأولُ يُهمَل، والثاني يُردّ في وجه صاحبه.
LOUD_TAGS = frozenset(
    {"script", "foreignObject", "iframe", "embed", "object", "handler", "use", "image"}
)

#: **السماتُ المسموحة** — هندسةٌ وطلاءٌ ووحدةُ عرض. ولا `on*` تمرّ لأنها ليست
#: هنا؛ والمنعُ الصريحُ لها باقٍ **طبقةً ثانية** في `_clean_attributes`،
#: وحارسان لبابٍ واحدٍ ليس تكراراً حين يكون أحدُهما قائمةً يوسّعها بشر.
ALLOWED_ATTRS = frozenset(
    {
        "id", "class", "d", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy",
        "r", "rx", "ry", "fx", "fy", "width", "height", "points",
        "viewBox", "preserveAspectRatio", "transform", "gradientUnits",
        "gradientTransform", "spreadMethod", "offset", "stop-color",
        "stop-opacity", "fill", "fill-opacity", "fill-rule", "stroke",
        "stroke-width", "stroke-opacity", "stroke-linecap", "stroke-linejoin",
        "stroke-dasharray", "stroke-dashoffset", "stroke-miterlimit",
        "opacity", "clip-path", "clip-rule", "mask", "filter", "style",
        "stdDeviation", "dx", "dy", "flood-color", "flood-opacity",
        "in", "in2", "result", "mode", "operator", "type", "values",
        "maskUnits", "clipPathUnits", "filterUnits", "vector-effect",
        "xmlns",
    }
)

#: **قيمةٌ ترجع إلى مرجعٍ داخليٍّ وحدَه**: `url(#grad)` نعم، و`url(http…)` أو
#: `url(//…)` لا — الأخيرةُ تجعل رسمةً **تنادي خادماً غريباً عند كلِّ عرض**،
#: فتُسرّب أن هذه اللوحةَ فُتحت ومتى. وهي قناةٌ لا يراها من ينظر إلى الشاشة.
_URL_REF = re.compile(r"url\(\s*['\"]?#[A-Za-z_][\w.:-]*['\"]?\s*\)", re.I)
_ANY_URL = re.compile(r"url\(", re.I)

#: **مخططاتٌ خطرةٌ في أيِّ قيمة** — تُرفض أينما وقعت.
_BAD_SCHEME = re.compile(r"(javascript|vbscript|data)\s*:", re.I)

#: ما يُرفض **قبل التحليل أصلاً**: انفجارُ الكيانات («billion laughs») يقع في
#: المُحلِّل نفسِه قبل أن يصل شيءٌ إلى قائمة السماح — فالحارسُ يسبقه.
_DOCTYPE = re.compile(r"<!\s*(DOCTYPE|ENTITY)", re.I)

_SVG_NS = "http://www.w3.org/2000/svg"
_XLINK_NS = "http://www.w3.org/1999/xlink"


def _local(tag: object) -> str:
    """اسمُ العنصر بلا فضاء الأسماء — `{ns}path` ← `path`."""
    text = tag if isinstance(tag, str) else ""
    return text.rsplit("}", 1)[-1]


def _safe_value(name: str, value: str) -> bool:
    """أتصلح هذه القيمةُ للكتابة؟ — **والشكُّ يُفسَّر رفضاً**."""
    if _BAD_SCHEME.search(value):
        return False
    if _ANY_URL.search(value) and not _URL_REF.fullmatch(value.strip()):
        return False
    lowered = value.lower()
    if name == "style" and ("@import" in lowered or "expression" in lowered):
        return False
    return True


def _clean_attributes(source: ET.Element, target: ET.Element) -> None:
    for raw, value in source.attrib.items():
        name = _local(raw)
        if name.lower().startswith("on"):
            raise UnsafeArtwork("الرسمة تحمل معالجَ حدث")
        if raw.startswith(f"{{{_XLINK_NS}}}") or name in {"href", "xlink:href"}:
            # **مرجعٌ خارجيٌّ يُرفض ولا يبقى منه شيء.** و`data:` مرفوضةٌ معه:
            # `data:text/html` في `href` مستندٌ كاملٌ يُهرَّب داخل رسمة
            raise UnsafeArtwork("الرسمة تشير إلى ملفٍّ خارجي")
        if name not in ALLOWED_ATTRS:
            continue
        if not _safe_value(name, value):
            raise UnsafeArtwork("الرسمة تحمل مرجعاً خارجياً في إحدى سماتها")
        target.set(name, value)


def _copy(source: ET.Element) -> ET.Element | None:
    """ينسخ عنصراً مسموحاً وأبناءَه — **ويُسقط ما ليس مسموحاً بلا ذكر**."""
    name = _local(source.tag)
    if name in LOUD_TAGS:
        raise UnsafeArtwork(f"الرسمة تحمل عنصر <{name}>")
    if name not in ALLOWED_TAGS:
        return None
    node = ET.Element(name)
    _clean_attributes(source, node)
    if source.text and source.text.strip():
        node.text = source.text
    for child in source:
        copied = _copy(child)
        if copied is not None:
            node.append(copied)
    return node


def sanitize_svg(data: bytes) -> ET.Element:
    """يحوّل بايتاتِ SVG إلى **شجرةٍ أُعيدت كتابتُها من قائمة السماح**.

    **ولا يُعاد النصُّ الأصليُّ أبداً** — ولو بعد حذفِ ما رُفض منه.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise UnsupportedDocument("ملفُّ SVG غير سليم") from error
    if _DOCTYPE.search(text):
        raise UnsafeArtwork("الرسمة تحمل إعلانَ نوعٍ أو كياناً")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise UnsupportedDocument("ملفُّ SVG غير سليم") from error
    if _local(root.tag) != "svg":
        raise UnsupportedDocument("الملف ليس رسمةَ SVG")
    cleaned = _copy(root)
    if cleaned is None:  # pragma: no cover - `svg` في القائمة دائماً
        raise UnsafeArtwork()
    return cleaned


def _svg_at(tree: ET.Element, size: int) -> bytes:
    """نسخةٌ بمقاسٍ ذاتيٍّ مكتوب — **و`viewBox` واحدةٌ للمقاسين**."""
    node = ET.Element("svg")
    for key, value in tree.attrib.items():
        if key not in {"width", "height"}:
            node.set(key, value)
    if "viewBox" not in node.attrib:
        # بلا إطارٍ معلوم لا معنى لمقاسٍ ثابت — ويُكتب مربّعٌ محايد
        node.set("viewBox", "0 0 100 100")
    node.set("xmlns", _SVG_NS)
    node.set("width", str(size))
    node.set("height", str(size))
    node.set("preserveAspectRatio", "xMidYMid meet")
    for child in tree:
        node.append(child)
    return ET.tostring(node, encoding="utf-8", xml_declaration=False)


# ════════════════════════════════════════════════ ٣) المعالجةُ النقطية


def _trim_and_fit(rgba: Image.Image, size: int) -> bytes:
    """يقصّ الهامشَ الشفاف، ثم يوسّط الرسمةَ في مربّعٍ بمقاسٍ ثابت."""
    box = rgba.getchannel("A").getbbox()
    cropped = rgba.crop(box) if box is not None else rgba
    if cropped.width == 0 or cropped.height == 0:  # pragma: no cover
        raise UnsupportedDocument("الرسمة فارغة")
    fitted = cropped.copy()
    fitted.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(fitted, ((size - fitted.width) // 2, (size - fitted.height) // 2))
    buffer = io.BytesIO()
    # WebP بشفافية: أصغرُ من PNG بكثيرٍ عند الجودة نفسِها، **و`storage.sniff`
    # يعرف توقيعَه** — فيُشمّ المُخرَجُ ثانيةً عند الكتابة
    canvas.save(buffer, format="WEBP", quality=90 if size > MAP_PX else 82, method=6)
    return buffer.getvalue()


# ════════════════════════════════════════════════ ٤) العَرض (بلا كتابة)


@dataclass(frozen=True, slots=True)
class RenderedArtwork:
    """ناتجُ المعالجة **في الذاكرة** — لا صفَّ ولا ملفّ.

    وهو ما تقرؤه المعاينةُ في اللوحة: **الرسمةُ بعد القصّ والتصغير**، لا
    الملفُّ الخام. **ومعاينةٌ تعرض الخامَ تكذب** — تُري المشرفَ حجماً غيرَ
    الذي سيُرسم، فيضبط نسبةَ العرض على ما لن يقع. وهي «التجربةُ الجافّة»
    نفسُها التي أثبتت إصلاحَ قوالب الرسائل: نفسُ السلسلة، بلا أن يُكتب شيء.
    """

    store: bytes
    map: bytes
    media_type: str
    extension: str
    #: مقاسُ الأصل قبل أيِّ لمس — `None` للمتجهيّة
    source_size: tuple[int, int] | None
    #: **ما بقي بعد القصّ** — يُعرض للمشرف، فالقصُّ الصامتُ يُقرأ خطأً في الرسمة
    trimmed: tuple[int, int, int, int] | None


def render(data: bytes) -> RenderedArtwork:
    """**النوعُ من البايتات**، ثم مساران: متجهيٌّ يُنقّى، ونقطيٌّ يُقصّ ويُصغَّر.

    **ولا `except Exception` عريضة**: خطأُ برمجةٍ يجب أن يبقى مرئياً (درسُ
    12-ط). والمُبتلَعُ هنا **مسمّى**: ملفٌّ لا يُفكّ، وقنبلةُ فكِّ ضغط.
    """
    if data.lstrip()[:1] == b"<":
        tree = sanitize_svg(data)
        return RenderedArtwork(
            store=_svg_at(tree, STORE_PX),
            map=_svg_at(tree, MAP_PX),
            media_type="image/svg+xml",
            extension=".svg",
            source_size=None,
            trimmed=None,
        )

    # **يُشمُّ أولاً**: ملفٌّ يدّعي أنه صورة يُرفض هنا **قبل** أن يصل إلى فاكِّ
    # الترميز — فلا يُبنى الرفضُ على استثناءٍ من مكتبة، ولا يُفكّ ما لم يُعرَف
    storage.sniff(data[:32])

    previous = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with Image.open(io.BytesIO(data)) as opened:
            width, height = opened.size
            # **يُقاس من الترويسة قبل `load()`**: فكُّ الضغط نفسُه هو الهجوم،
            # فقياسٌ بعده قياسٌ متأخّر
            if width * height > MAX_PIXELS:
                raise DocumentTooLarge(
                    "أبعاد الصورة أكبر من المسموح — قلّل مقاسها ثم أعد الرفع"
                )
            opened.load()
            rgba = opened.convert("RGBA")
    except Image.DecompressionBombError as error:
        # **قنبلةُ فكِّ الضغط رفضٌ لا ٥٠٠**: ملفٌّ صغيرٌ يُفكّ إلى غيغابايتات،
        # **والحجمُ وحدَه لا يراه** — وهو سببُ وجود السقف الثاني
        raise DocumentTooLarge(
            "أبعاد الصورة أكبر من المسموح — قلّل مقاسها ثم أعد الرفع"
        ) from error
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise UnsupportedDocument(
            "تعذّر فكُّ الصورة — الملف تالفٌ أو غيرُ مدعوم"
        ) from error
    finally:
        Image.MAX_IMAGE_PIXELS = previous

    box = rgba.getchannel("A").getbbox()
    return RenderedArtwork(
        store=_trim_and_fit(rgba, STORE_PX),
        map=_trim_and_fit(rgba, MAP_PX),
        media_type="image/webp",
        extension=".webp",
        source_size=(width, height),
        trimmed=box if box != (0, 0, width, height) else None,
    )


# ════════════════════════════════════════════════ ٥) الابتلاعُ والكتابة


@dataclass(frozen=True, slots=True)
class StoredArtwork:
    store_path: str
    map_path: str
    media_type: str
    source_size: tuple[int, int] | None
    trimmed: tuple[int, int, int, int] | None


async def _write_svg(data: bytes, *, folder: str) -> str:
    """يكتب SVG بقواعد `storage.save` الثلاث — **ولا يخترع رابعة**."""
    target_dir = storage.root() / folder
    await anyio.to_thread.run_sync(
        lambda: target_dir.mkdir(parents=True, exist_ok=True)
    )
    handle = await anyio.to_thread.run_sync(
        lambda: tempfile.NamedTemporaryFile(
            dir=target_dir, prefix=".part-", delete=False
        )
    )
    temp_path = Path(handle.name)
    try:
        await anyio.to_thread.run_sync(handle.write, data)
        await anyio.to_thread.run_sync(handle.flush)
    except BaseException:
        await anyio.to_thread.run_sync(handle.close)
        await anyio.to_thread.run_sync(temp_path.unlink, True)
        raise
    else:
        await anyio.to_thread.run_sync(handle.close)

    name = f"{uuid.uuid4().hex}.svg"
    final = target_dir / name
    await anyio.to_thread.run_sync(temp_path.replace, final)
    await anyio.to_thread.run_sync(final.chmod, 0o600)

    # **ولا يُقَرّ بالنجاح إلا بعد أن يُرى الملفُّ بحجمه** — انتهاءُ الكتابة
    # ليس كتابةً: قرصٌ امتلأ أو نظامُ ملفاتٍ للقراءة يُنهيان الحلقةَ صامتَين،
    # ثم يُكتب صفٌّ يعد بملفٍّ ليس هناك
    written = await anyio.to_thread.run_sync(
        lambda: final.stat().st_size if final.is_file() else -1
    )
    if written != len(data):
        await anyio.to_thread.run_sync(final.unlink, True)
        logger.error(
            "رسمة كُتبت ناقصةً: %s/%s — المتوقَّع %d والمكتوب %d",
            folder, name, len(data), written,
        )
        raise DocumentFileMissing()
    return f"{folder}/{name}"


async def ingest(reader: storage.AsyncReader, *, folder: str) -> StoredArtwork:
    """**البابُ الوحيد** لبايتاتِ رسمةٍ يرفعها إنسان — قراءةٌ، فعَرضٌ، فكتابة.

    والترتيبُ ليس تفصيلاً: **لا يُكتب شيءٌ قبل أن تُقبل الرسمةُ كاملةً**، فلا
    يبقى نصفُ زوجٍ على القرص حين يُرفض المقاسُ الثاني.
    """
    data = await read_capped(reader)
    art = render(data)

    if art.extension == ".svg":
        store_path = await _write_svg(art.store, folder=folder)
        map_path = await _write_svg(art.map, folder=folder)
    else:
        # **يمرّ بـ`storage.save`**: يُشمُّ المُخرَجُ ثانيةً، ويُنقل ذرّياً،
        # ويُتحقَّق من حجمه — بلا نسخةٍ ثانيةٍ من منطقه هنا
        store_path = (
            await storage.save(_BytesReader(art.store), folder=folder)
        ).relative_path
        map_path = (
            await storage.save(_BytesReader(art.map), folder=folder)
        ).relative_path

    return StoredArtwork(
        store_path=store_path,
        map_path=map_path,
        media_type=art.media_type,
        source_size=art.source_size,
        trimmed=art.trimmed,
    )


# ════════════════════════════════════════════════ ٦) العَرض المتصلّب


def hardened_headers(media_type: str) -> dict[str, str]:
    """ترويساتُ خدمةِ ملفٍّ رفعه إنسانٌ ويُخدَم للجميع.

    **و`<img>` لا تشغّل سكربتاً — ولا يُجعل ذلك الحارسَ الوحيد**: من ينتقل
    إلى العنوان مباشرةً يفتحه **مستنداً**، فيعمل ما فيه في أصلنا ويقرأ
    تخزينَه. فالترويساتُ تُغلق ذلك المسار:

    - `default-src 'none'` — لا سكربت، ولا نداءَ شبكة، ولا خطّ، ولا إطار.
    - `style-src 'unsafe-inline'` — سمةُ `style` داخل الرسمة تحتاجها، وهي
      **مصفّاةٌ سلفاً** من `url(` الخارجيّ ومن `@import`.
    - `sandbox` بلا قيمة — أصلٌ فريدٌ معتم: لا سكربت، ولا نماذج، ولا تخزين،
      ولا ملاحةٌ عليا. **وهي الطبقةُ التي تعمل ولو أخطأت القائمة.**
    - `nosniff` — فلا يخمّن متصفحٌ نوعاً أخطرَ ممّا استنتجناه.

    **والتخبئةُ عامّةٌ لأن الرسمةَ لا تحمل هويةَ أحد** — وهذا ما يفرّقها عن
    `drivers.document_response` التي تردّ `private, no-store`. واسمُ الملفِّ
    عشوائيٌّ يتبدّل مع كلِّ رفع، فلا تُقادِم التخبئةُ شيئاً.
    """
    return {
        "Content-Security-Policy": (
            "default-src 'none'; style-src 'unsafe-inline'; sandbox"
        ),
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "inline",
        "Cache-Control": f"public, max-age={CACHE_SECONDS}, immutable",
        "Referrer-Policy": "no-referrer",
    }


def bundled_path(asset_key: str, slot: Slot) -> Path:
    """مسارُ رسمةٍ مولَّدةٍ داخل الحزمة — **والمفتاحُ يُتحقَّق منه**.

    مفتاحٌ آتٍ من صفٍّ في القاعدة ليس مدخلاً خارجياً اليوم، **ويصير كذلك يومَ
    يكتبه أحدٌ بيده** — والفحصُ هنا لا في المستدعي، كما في `storage._SAFE_FOLDER`.
    """
    if not _ASSET_KEY.match(asset_key):
        raise DocumentFileMissing()
    base = ASSETS_DIR.resolve()
    path = (base / f"{asset_key}{_ASSET_SUFFIX[slot]}").resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise DocumentFileMissing()
    return path


def artwork_response(
    *,
    asset_key: str | None,
    stored_path: str | None,
    slot: Slot,
) -> FileResponse:
    """**بانٍ واحدٌ لبابَي العرض** — بابُ اللوحة وبابُ الكبتن.

    وبابان يخدمان الشيءَ نفسَه بترويستين هما **الشكلُ الثامن**: كلٌّ منهما
    صادقٌ وحدَه، ويفترقان أوّلَ تعديلٍ على أحدهما. فالسياسةُ هنا، والراوترُ
    ينادي — لا العكس.
    """
    if asset_key:
        path = bundled_path(asset_key, slot)
        media_type = "image/svg+xml"
    elif stored_path:
        path = storage.resolve(stored_path)
        media_type = "image/svg+xml" if path.suffix == ".svg" else "image/webp"
    else:
        raise DocumentFileMissing()
    return FileResponse(
        path, media_type=media_type, headers=hardened_headers(media_type)
    )


# ════════════════════════════════════════════════ ٧) الرسوماتُ المشحونة


def bundled_assets() -> list[dict[str, str]]:
    """كتالوجُ الرسومات المولَّدة — **ويُقرأ من القرص لا من قائمةٍ في الكود**.

    قائمةٌ مكتوبةٌ هنا تفترق عن المجلَّد أوّلَ رسمةٍ تُضاف أو تُحذف، **فيعرض
    المنتقي مركبةً بلا ملفّ** — وهو «بابٌ بلا زرّ» مقلوباً: زرٌّ بلا باب.
    والقراءةُ تتحقّق من **الملفين معاً**: نصفُ زوجٍ يُرسم في المتجر ولا يُرسم
    على الخريطة، وذلك لا يُكتشف إلا في يدِ كبتن.
    """
    manifest = ASSETS_DIR / "manifest.json"
    if not manifest.is_file():
        logger.error("منظومةُ رسومات المركبات ناقصة: لا manifest.json في %s", ASSETS_DIR)
        return []
    rows = json.loads(manifest.read_text(encoding="utf-8"))
    ready: list[dict[str, str]] = []
    for row in rows:
        key = str(row.get("key", ""))
        if not _ASSET_KEY.match(key):
            continue
        if all(
            (ASSETS_DIR / f"{key}{suffix}").is_file()
            for suffix in _ASSET_SUFFIX.values()
        ):
            ready.append(row)
        else:
            logger.error("رسمةٌ في المنظومة بلا ملفَّيها: %s", key)
    return ready
