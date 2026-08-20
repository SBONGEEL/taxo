"""**البند ١١**: `data` الإشعار يحمل قيماً خاماً لا جملةً مؤلَّفة.

**والقاعدةُ مكتوبةٌ في `CLAUDE.md` منذ المرحلة ٨** ولم يكن لها حارس: «`data`
يحمل `type` و`ride_id` و`amount` و`currency` — **لا جملةً مؤلَّفةً ولا أرقاماً
منسَّقة**». و`title`/`body` وحدَهما للدرج (OS tray) لأن النظامَ يرسمهما
والتطبيقُ مغلق.

**والعطبُ الذي تحرسه**: `f"{amount} {currency}"` في الخلفية يُرسم «4.100 JOD»
بخاناتٍ لاتينيةٍ ورمزٍ إنجليزيّ داخل تطبيقٍ يعرض «٤٫١٠٠ د.أ». **والعلاجُ ليس
تحويلَ الخانات في الخلفية**: ذلك يضع قرارَ لغةٍ في طبقةٍ لا تعرف من يقرأ،
ويمرّر المالَ بمُنسِّقٍ لغرضِ عرض (§14). فالخلفيةُ ترسل القيمةَ، والتطبيقُ
يؤلّف.

**ويفحص المصدرَ لا الاستجابة**: الجملةُ المؤلَّفة تولد في `notifications.py`،
ولا يمرّ بها اختبارٌ إلا إن أرسل ذلك الإشعارَ بعينه — فالمسحُ على الشجرة يغطّي
ما لا تلمسه المجموعة.
"""

from __future__ import annotations

import ast
import pathlib

SERVICE = pathlib.Path(__file__).resolve().parents[1] / "app" / "services"

#: مفاتيحُ يجوز أن تحمل نصّاً مؤلَّفاً — وهي **ما يرسمه النظامُ لا التطبيق**.
TRAY_KEYS = {"title", "body"}


def _composed(node: ast.AST) -> bool:
    """أهذا تعبيرٌ **يؤلّف** نصّاً؟ — قالبٌ، أو جمعُ نصوص، أو `format`/`join`."""
    if isinstance(node, ast.JoinedStr):  # f"…"
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return True
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in {"format", "join"}:
            return True
    return False


def test_notification_data_carries_raw_values_not_sentences() -> None:
    """**قيمٌ خام في `data`** — والجملةُ في `title`/`body` وحدَهما."""
    offenders: list[str] = []

    for path in sorted(SERVICE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.keyword) or node.arg != "data":
                continue
            if not isinstance(node.value, ast.Dict):
                continue  # `data=dict(...)` أو متغيّر — يُفحص عند تعريفه
            for key, value in zip(node.value.keys, node.value.values):
                name = key.value if isinstance(key, ast.Constant) else "?"
                if name in TRAY_KEYS:
                    continue
                if _composed(value):
                    offenders.append(f"{path.name}:{value.lineno}  data[{name!r}]")

    assert not offenders, (
        "جملةٌ مؤلَّفةٌ داخل `data` الإشعار — والتطبيقُ هو من يؤلّف:\n  "
        + "\n  ".join(offenders)
        + "\n\n  أرسل القيمةَ خاماً (`amount` و`currency` حقلين) ودع الشاشةَ "
        "تجمعهما.\n  و`title`/`body` وحدَهما للدرج، لأن النظامَ يرسمهما "
        "والتطبيقُ مغلق."
    )


def test_the_sweep_actually_read_something() -> None:
    """**صمتُ الحارس يحتاج إثباتاً** (قاعدةُ المِسبار ٥).

    مسحٌ لا يجد `data=` واحدةً يمرّ أخضرَ أبداً ولا يقيس شيئاً — وهو ما وقع
    مقيساً في `check:readers` يومَ بُني.
    """
    seen = 0
    for path in sorted(SERVICE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "data":
                seen += 1
    assert seen >= 10, f"لم يُقرأ إلا {seen} من `data=` — المسحُ لا يرى الشجرة"
