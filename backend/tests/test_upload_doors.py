"""**كلُّ بابٍ يأخذ `UploadFile` يمرّ ببابٍ معقِّم** — حارسُ صنفٍ لا حارسُ حالة.

**والعلّةُ أن القاعدةَ المكتوبةَ لا تكفي** — وهي قاعدةُ هذا المشروع الأولى:
`check:enums` أوقف اتحاداً مختلطاً في جلسةٍ وقع فيها فخٌّ **مكتوبٌ حرفياً** في
`CLAUDE.md`. **فالمكتوبُ لا يُطبَّق، والحارسُ يُطبَّق.**

**وما يحرسه**: بايتاتٌ يرفعها إنسانٌ لا تُكتب على القرص ولا تُخدَم لأحد إلا
بعد أن تمرّ بـ`storage.save` (توقيعٌ ثنائيٌّ وسقفٌ بالقراءة واسمٌ من عندنا) أو
`skin_artwork.ingest` (ذلك، ومعه قائمةُ سماحِ SVG والسقفُ الثاني للأبعاد).
**وبابٌ ثالثٌ يُضاف غداً بلا واحدٍ منهما يُسقط المجموعة** — وهي اللحظةُ التي
يوجد هذا الملفُّ لأجلها، لا اللحظةُ التي كُتب فيها.

---

**وحدُّه يُقال قبل أن يُصدَّق** (قاعدةُ الحارس): يقرأ **الشجرة**، فيمسك بابَ
`UploadFile` لا يصل منه نداءٌ إلى معقِّم. **ولا يقيس ما يفعله المعقِّم نفسُه**
— ذاك عملُ `test_skin_artwork.py`. **ولا يتتبّع الوسيطَ** عبر الاستدعاءات:
لو مرّر مسارٌ ملفَه إلى دالّةٍ ومرّر **غيرَه** إلى المعقِّم لَمرّ من هنا.
وذلك اختيارٌ مقصود: **حارسٌ يخترع عطباً أغلى من حارسٍ يفوته** (قرارُ المالك
2026-08-20)، وتتبّعُ الوسائط عبر الوحدات يُخرج بلاغاتٍ كاذبةً أكثرَ مما يمسك.

**وصمتُه يحتاج إثباتاً كما يحتاجه صياحُه**: يُعلن **كم ملفاً قرأ وكم باباً
وجد**، و**صفرٌ في أيِّهما عطبٌ فيه لا سلامةٌ في الشجرة** — وقد وقع ذلك مقيساً
في `check:readers` حين لم يطابق فاصلُ المسار على ويندوز فمرّ أخضرَ بلا ملف.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"

#: **الأبوابُ المعقِّمة** — تُطابَق على **نهاية** الاسم المنقَّط، فـ
#: `storage.save` تُطابق و`session.save` لا تُطابق.
SANITISERS = (
    "storage.save",
    "skin_artwork.ingest",
    "skin_artwork.read_capped",
)

#: عمقُ التتبّع: مسارٌ ← خدمةٌ ← مساعدٌ داخلها. وثلاثةٌ تكفي كلَّ ما في الشجرة
#: اليوم، **وزيادتُها تزيد البلاغاتِ الكاذبةَ لا الإمساك**.
MAX_DEPTH = 4


def _dotted(node: ast.AST) -> str:
    """`storage.save` من عقدة النداء — أو `""` لِما ليس اسماً."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = _dotted(node.value)
        return f"{head}.{node.attr}" if head else node.attr
    return ""


class _Scan(ast.NodeVisitor):
    """يجمع من كلِّ دالّة: نداءاتِها، وهل تعلن وسيطاً من نوع `UploadFile`."""

    def __init__(self, source: str) -> None:
        self.source = source
        #: اسمُ الدالّة (مجرَّداً) ← مجموعةُ الأسماء المنقَّطة التي تناديها
        self.calls: dict[str, set[str]] = {}
        #: أسماءُ الدوالِّ التي تستقبل ملفاً مرفوعاً
        self.doors: set[str] = set()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        called: set[str] = set()
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call):
                name = _dotted(inner.func)
                if name:
                    called.add(name)
        self.calls.setdefault(node.name, set()).update(called)

        args = node.args
        for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
            if arg.annotation is None:
                continue
            # **يُقرأ نصُّ التعليق لا شكلُه**: `UploadFile` تصل مجرَّدةً،
            # و`Annotated[UploadFile, File(...)]`، و`UploadFile | None` —
            # وثلاثةُ أشكالٍ في مطابقةٍ بنيويةٍ ثلاثةُ فروعٍ يُنسى رابعُها
            text = ast.get_source_segment(self.source, arg.annotation) or ""
            if "UploadFile" in text:
                self.doors.add(node.name)
        self.generic_visit(node)

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function


def _scan_tree() -> tuple[dict[str, set[str]], set[str], int]:
    calls: dict[str, set[str]] = {}
    doors: set[str] = set()
    files = 0
    for path in sorted(APP.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        scan = _Scan(source)
        scan.visit(ast.parse(source))
        for name, called in scan.calls.items():
            calls.setdefault(name, set()).update(called)
        doors |= scan.doors
        files += 1
    return calls, doors, files


def _reaches_a_sanitiser(name: str, calls: dict[str, set[str]]) -> bool:
    """أيصل من هذه الدالّة نداءٌ — مباشرٌ أو عبر خدمة — إلى معقِّم؟"""
    seen: set[str] = set()
    frontier = [(name, 0)]
    while frontier:
        current, depth = frontier.pop()
        if current in seen or depth > MAX_DEPTH:
            continue
        seen.add(current)
        for called in calls.get(current, set()):
            if any(
                called == door or called.endswith("." + door.split(".")[-1])
                and door.split(".")[0] in called
                for door in SANITISERS
            ):
                return True
            # المطابقةُ بالاسم المجرَّد: `documents_service.upload` ← `upload`
            frontier.append((called.rsplit(".", 1)[-1], depth + 1))
    return False


def test_every_upload_door_passes_through_a_sanitiser() -> None:
    calls, doors, files = _scan_tree()

    # **صفرٌ مقروءٌ عطبٌ لا سلامة** — والحارسُ يعلن ما قرأ قبل أن يحكم
    assert files > 50, f"لم تُقرأ الشجرة (ملفات={files}) — عطبٌ في الحارس"
    assert doors, "لم يُوجد بابُ رفعٍ واحد — عطبٌ في الحارس لا شجرةٌ بلا رفع"

    naked = sorted(
        name for name in doors if not _reaches_a_sanitiser(name, calls)
    )
    assert not naked, (
        "بابُ رفعٍ لا يصل منه نداءٌ إلى معقِّم: " + " · ".join(naked) + "\n"
        "  كلُّ `UploadFile` يمرّ بـ`core/storage.save` أو "
        "`services/skin_artwork.ingest`.\n"
        "  ولا يُضاف استثناء: بابٌ ثالثٌ للبايتات هو بابٌ ثالثٌ للقواعد."
    )


def test_the_guard_names_what_it_measured() -> None:
    """**والصمتُ يحتاج إثباتاً**: تُعرَض الأبوابُ التي وُجدت، فلا يُقرأ
    صمتٌ سببُه ألّا شيءَ قِيس صمتَ سلامة."""
    calls, doors, files = _scan_tree()
    print(f"\n  قُرئ {files} ملفَّ خلفية · وُجد {len(doors)} بابَ رفع: "
          + " · ".join(sorted(doors)))
    # الأبوابُ الثلاثةُ المعروفةُ اليوم — **وزيادتُها ليست عطباً**، وهذا
    # الاختبارُ لا يمنعها؛ يمنع فقط أن تنعدم فيمرّ الأولُ أخضرَ بلا قياس
    assert len(doors) >= 3
    assert calls, "لم تُقرأ نداءاتُ أيِّ دالّة — عطبٌ في الحارس"
