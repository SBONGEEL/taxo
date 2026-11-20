"""**الصورةُ الشخصيّةُ تُخزَّن بلا بياناتٍ وصفيّة** (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-هـ/٤).

صورةُ الهاتف تحمل في EXIF **إحداثيّاتِ المكان الذي التُقطت فيه** — بيتُ صاحبها غالباً. والتطبيقان يقصّانها ويعيدان ترميزَها قبل
الرفع (الترميزُ في `canvas` لا ينقل EXIF)، **لكنّ الخادمَ لا يثق بالعميل**: كلُّ صورةٍ شخصيّةٍ تُفكّ هنا يُعاد ترميزُها JPEG بلا
EXIF، مقلوبةً إلى اتّجاهها الصحيح أوّلاً (فلا تنقلب صورةٌ كان اتّجاهُها في EXIF وحدَه)، ومصغَّرةً إلى ٥١٢ بكسل.

**وما لا يُفكّ يمرّ كما هو إلى `core/storage`** الذي يفحص نوعَه من بايتاته ويرفض ما ليس صورة — فالتنظيفُ لا يصير حارسَ نوعٍ
ثانياً بقواعدَ أخرى. **وحدُّه مكتوب**: ملفٌّ يمرّ فحصَ النوع ولا تفكّه Pillow يُخزَّن بأصله — وهو لا يُعرض لأحدٍ صورةً أصلاً
(`avatar.render` يرسم الحرفَ مكانَ ما لا يُفكّ).
"""

from __future__ import annotations

import io

from PIL import Image, ImageOps

from app.core.config import settings

#: أكبرُ ضلع — ما يرسمه أيُّ بابٍ أصغرُ بكثير (`avatar.SIZE = 256`)، و٥١٢ تكفي شاشةً بكثافة ٣×
MAX_EDGE = 512
QUALITY = 85
_CHUNK = 64 * 1024


class _BytesReader:
    """قارئٌ بواجهة `UploadFile.read` — ما يأخذه `storage.save`."""

    def __init__(self, data: bytes) -> None:
        self._buffer = io.BytesIO(data)

    async def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)


def strip(data: bytes) -> bytes | None:
    """JPEG نظيفٌ بلا EXIF، أو `None` إن لم تُفكّ الصورة."""
    try:
        with Image.open(io.BytesIO(data)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
    except Exception:
        return None
    image.thumbnail((MAX_EDGE, MAX_EDGE))
    out = io.BytesIO()
    # **بلا `exif=`**: Pillow لا يكتب EXIF ما لم يُمرَّر، والصورةُ الجديدةُ لا تحمل من الأصل إلا بكسلاته
    image.save(out, format="JPEG", quality=QUALITY, optimize=True)
    return out.getvalue()


async def cleaned(reader) -> _BytesReader:
    """يقرأ الرفعَ كلَّه (بسقف حجم المستندات نفسِه) ويعيد قارئاً بالصورة النظيفة — أو بالأصل إن لم يُفكّ."""
    limit = settings.document_max_bytes
    raw = bytearray()
    while True:
        chunk = await reader.read(_CHUNK)
        if not chunk:
            break
        raw += chunk
        if len(raw) > limit:
            # **يُترك لـ`storage` أن يرفضه برسالته** — نمرّر ما يكفي ليتجاوز السقفَ عنده كما يتجاوزه هنا
            break
    data = bytes(raw)
    return _BytesReader(strip(data) or data)
