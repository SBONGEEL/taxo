"""تخزين ملفات المستندات على القرص (المرحلة 9-ب).

الوحيد في المشروع الذي يلمس نظام الملفات. ثلاث قواعد تحكمه، وكلُّها مكتوبةٌ
هنا لا في مستدعيه:

**١) اسم الملف من عندنا لا من العميل.** الاسم المرسَل لا يُقرأ ولا يُخزَّن:
اسمُ الملف على القرص `uuid4().hex` وامتدادُه مشتقٌّ من **محتواه**. فلا
`../../etc/passwd`، ولا `.php`، ولا اسمٌ يكشف شيئاً عن صاحبه.

**٢) النوع من البايتات لا من الترويسة.** `Content-Type` حقلٌ يكتبه العميل،
فقبولُه يعني قبول أي ملفٍ سمّى نفسه صورة. الحكم هنا على التوقيع الثنائي
(magic bytes) وحده، والامتداد يتبعه.

**٣) السقف يُفرض بالقراءة لا بـ `Content-Length`.** الترويسة يكتبها العميل
أيضاً؛ فالقراءة تجري على دفعات وتتوقف عند تجاوز السقف بدل أن تصدّق رقماً.

والمسارات المخزَّنة **نسبيةٌ** إلى جذر التخزين: جذرٌ يتبدّل لا يُبطل صفّاً،
ومسارٌ مطلق قادمٌ من طلبٍ لا يمكن أن يُكتب أصلاً. وكل قراءةٍ تمر بـ`resolve`
التي ترفض أي مسارٍ يخرج من الجذر — دفاعٌ ثانٍ خلف الأول، لأن الأول وحده
يكفي فقط ما دام لا أحد يكتب في `file_path` بيده.
"""

from __future__ import annotations

import logging
import re
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import anyio

from app.core.config import settings
from app.core.exceptions import (
    DocumentFileMissing,
    DocumentTooLarge,
    UnsupportedDocument,
)

logger = logging.getLogger(__name__)

CHUNK_BYTES = 64 * 1024

# اسم المجلد الفرعي: UUID الكبتن حصراً. الفحص هنا لا في المستدعي، لأن
# «المستدعي يمرر UUID دائماً» جملةٌ صحيحةٌ حتى تتوقف عن الصحة
_SAFE_FOLDER = re.compile(r"^[0-9a-fA-F-]{36}$")

# التوقيع الثنائي ← (نوع المحتوى، الامتداد). WebP توقيعان متباعدان:
# `RIFF` في الأول و`WEBP` بعد أربع بايتات من الطول
_SIGNATURES: tuple[tuple[bytes, str, str], ...] = (
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"%PDF-", "application/pdf", ".pdf"),
)

ALLOWED_CONTENT_TYPES: tuple[str, ...] = (
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
)


class AsyncReader(Protocol):
    """ما نحتاجه من `UploadFile` — لا أكثر، فيسهل اختباره بلا HTTP."""

    async def read(self, size: int = -1) -> bytes: ...


@dataclass(frozen=True, slots=True)
class StoredFile:
    """ما يُكتب في الصف بعد نجاح الحفظ."""

    relative_path: str
    content_type: str
    size_bytes: int


def _root() -> Path:
    """يُقرأ عند كل نداء لا مرةً عند الاستيراد — فتستطيع الاختبارات تبديله."""
    return Path(settings.document_storage_root)


def sniff(head: bytes) -> tuple[str, str]:
    """نوع المحتوى وامتداده من أول بايتاته — أو `UnsupportedDocument`."""
    for signature, content_type, extension in _SIGNATURES:
        if head.startswith(signature):
            return content_type, extension
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise UnsupportedDocument()


def resolve(relative_path: str) -> Path:
    """المسار المطلق لملفٍ مخزَّن — أو `DocumentFileMissing` إن خرج عن الجذر.

    الخروج عن الجذر لا يقع بمسارٍ كتبناه نحن؛ الفحص لما لو كُتب `file_path`
    يوماً من مدخلٍ خارجي: عندها يفشل هذا لا نظامُ الملفات.
    """
    root = _root().resolve()
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root):
        logger.error("مسار مستند خارج جذر التخزين: %s", relative_path)
        raise DocumentFileMissing()
    if not candidate.is_file():
        raise DocumentFileMissing()
    return candidate


async def save(reader: AsyncReader, *, folder: str) -> StoredFile:
    """يحفظ ملفاً مرفوعاً بعد التحقق من نوعه وحجمه.

    يُكتب باسمٍ مؤقت ثم يُنقل إلى اسمه النهائي: رفعٌ انقطع في منتصفه لا يترك
    ملفاً بنصف محتوى يحمل اسماً يشير إليه صفٌّ في القاعدة.
    """
    if not _SAFE_FOLDER.match(folder):  # pragma: no cover - حارس برمجي
        raise ValueError("مجلد التخزين يجب أن يكون UUID")

    root = _root()
    target_dir = root / folder
    await anyio.to_thread.run_sync(lambda: target_dir.mkdir(parents=True, exist_ok=True))

    max_bytes = settings.document_max_bytes
    first = await reader.read(CHUNK_BYTES)
    if not first:
        raise UnsupportedDocument("الملف فارغ")
    content_type, extension = sniff(first)

    handle = await anyio.to_thread.run_sync(
        lambda: tempfile.NamedTemporaryFile(
            dir=target_dir, prefix=".part-", delete=False
        )
    )
    temp_path = Path(handle.name)
    size = 0
    try:
        chunk = first
        while chunk:
            size += len(chunk)
            if size > max_bytes:
                raise DocumentTooLarge(
                    f"حجم الملف أكبر من المسموح ({max_bytes // (1024 * 1024)} ميغابايت)"
                )
            await anyio.to_thread.run_sync(handle.write, chunk)
            chunk = await reader.read(CHUNK_BYTES)
        await anyio.to_thread.run_sync(handle.flush)
    except BaseException:
        await anyio.to_thread.run_sync(handle.close)
        await anyio.to_thread.run_sync(temp_path.unlink, True)
        raise
    else:
        await anyio.to_thread.run_sync(handle.close)

    name = f"{uuid.uuid4().hex}{extension}"
    await anyio.to_thread.run_sync(temp_path.replace, target_dir / name)
    # 0o600: الملف يُقرأ عبر مسارٍ يتحقق من الملكية، لا بخادم ملفاتٍ ساكن
    await anyio.to_thread.run_sync((target_dir / name).chmod, 0o600)

    return StoredFile(
        relative_path=f"{folder}/{name}", content_type=content_type, size_bytes=size
    )


async def delete(relative_path: str) -> None:
    """يحذف ملفاً مخزَّناً. **يُستدعى بعد نجاح الـ commit لا قبله.**

    ملفٌّ يتيمٌ بلا صفّ نفايةٌ تُنظَّف؛ وصفٌّ يشير إلى ملفٍ محذوف عطلٌ يراه
    المستخدم. فترتيبُ الاثنين ليس تفصيلاً، والفشلُ هنا يُبتلع ويُسجَّل.
    """
    try:
        root = _root().resolve()
        candidate = (root / relative_path).resolve()
        if not candidate.is_relative_to(root):  # pragma: no cover - حارس
            logger.error("رفض حذف مسار خارج جذر التخزين: %s", relative_path)
            return
        await anyio.to_thread.run_sync(candidate.unlink, True)
    except OSError:  # pragma: no cover - يعتمد على عطل قرص
        logger.exception("تعذّر حذف ملف المستند %s", relative_path)
