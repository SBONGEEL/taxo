"""**ما قد يصل مستخدماً من نصوص الخلفية** (SPEC §٧٣-هـ المرحلة ٥) — يُستخرج ليُترجم، ويقيسه `tests/test_i18n.py`.

    python scripts/i18n_extract.py            # يطبع العددَ بأصنافه
    python scripts/i18n_extract.py --json     # المفاتيحُ مرتّبةً (JSON)

**الصنفُ يُقرأ من الشيفرة لا من ذاكرة**:
1. **ما يُرفع خطأً** — أوّلُ وسيطٍ (أو `message=`) لكلِّ صنفٍ يرث `AppError` (تُحسب الشجرةُ من الشيفرة نفسِها).
2. **ما يُكتب في الإشعارات** — كلُّ نصٍّ في `services/notifications.py` و`services/push/`، و`title=`/`body=` في أيِّ نداء.
3. **رسائلُ التحقّق ونصوصُ الحالات** — `core/validation_errors.py` و`core/exceptions.py`.
4. **قالبُ رسالة الرمز** — `services/otp_templates.py`.
5. **أسماءُ الدول وعملاتُها** — `core/currency.py` (§٧٤-أ/٤: الاسمُ يُنشر في `/config` بلغة الطلب).

**والقالبُ النصّيُّ (`f"…"`) مفتاحٌ بمواضع** `{0}` `{1}` — فيُطابَق ما يُرسم وقتَ الخطأ وتُنقل قيمُه إلى الفرنسيّة. **وما لا يُستخرج**: نصُّ
السجلّ (`logger.*`)، والتوثيقُ، وما يُبنى بالجمع أو بـ`format` — **يبقى عربيّاً في الفرنسيّة** ويُقال كذلك.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

AR = re.compile(r"[؀-ۿ]")
APP = Path(__file__).resolve().parents[1] / "app"
WHOLE_FILES = (
    "services/notifications.py",
    "core/validation_errors.py",
    "core/exceptions.py",
    "services/otp_templates.py",
    # **أسماءُ الدول** (SPEC §٧٤-أ/٤) — تُنشر في `/config` بلغة الطلب فيسمّي بها مُختارُ الدولة كلَّ سوق
    "core/currency.py",
    # **أسماءُ طرق الدفع والخطط وأسبابُ حسم الدفعة** (SPEC §٧٦-ع/٢) — تُرسم بلغة الطلب
    "core/data_names.py",
    "services/payment_reasons.py",
)
WHOLE_DIRS = ("services/push",)
LOGGER = {"debug", "info", "warning", "error", "exception", "critical", "log"}


def template_of(node: ast.JoinedStr) -> str | None:
    parts, index = [], 0
    for value in node.values:
        if isinstance(value, ast.Constant):
            if "{" in str(value.value) or "}" in str(value.value):
                return None
            parts.append(str(value.value))
        else:
            parts.append(f"{{{index}}}")
            index += 1
    text = "".join(parts)
    return text if AR.search(text) else None


def text_of(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and AR.search(node.value):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return template_of(node)
    return None


def error_classes(trees: dict[Path, ast.Module]) -> set[str]:
    bases: dict[str, set[str]] = {}
    for tree in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases[node.name] = {getattr(b, "id", None) or getattr(b, "attr", "") for b in node.bases}
    known = {"AppError"}
    changed = True
    while changed:
        changed = False
        for name, parents in bases.items():
            if name not in known and parents & known:
                known.add(name)
                changed = True
    return known


def docstrings(tree: ast.Module) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                ids.add(id(first.value))
    return ids


def extract() -> dict[str, set[str]]:
    trees = {path: ast.parse(path.read_text(encoding="utf-8")) for path in APP.rglob("*.py")}
    errors = error_classes(trees)
    found: dict[str, set[str]] = {"errors": set(), "notifications": set(), "messages": set()}
    for path, tree in trees.items():
        rel = path.relative_to(APP).as_posix()
        whole = rel in WHOLE_FILES or rel.startswith(WHOLE_DIRS)
        skip = docstrings(tree)
        logged: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                if isinstance(func, ast.Attribute) and func.attr in LOGGER:
                    for arg in node.args:
                        for inner in ast.walk(arg):
                            logged.add(id(inner))
                    continue
                if name in errors:
                    candidates = node.args[:1] + [kw.value for kw in node.keywords if kw.arg == "message"]
                    for arg in candidates:
                        text = text_of(arg)
                        if text:
                            found["errors"].add(text)
                for kw in node.keywords:
                    if kw.arg in ("title", "body"):
                        text = text_of(kw.value)
                        if text:
                            found["notifications"].add(text)
        if whole:
            bucket = "notifications" if "notifications" in rel or "push" in rel else "messages"
            for node in ast.walk(tree):
                if id(node) in skip or id(node) in logged:
                    continue
                if isinstance(node, ast.JoinedStr):
                    text = template_of(node)
                    if text:
                        found[bucket].add(text)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str) and AR.search(node.value):
                    if not any(id(node) in {id(v) for v in j.values} for j in ast.walk(tree) if isinstance(j, ast.JoinedStr)):
                        found[bucket].add(node.value)
    return found


def keys() -> list[str]:
    found = extract()
    return sorted(set().union(*found.values()))


if __name__ == "__main__":
    found = extract()
    if "--json" in sys.argv:
        print(json.dumps(keys(), ensure_ascii=False, indent=1))
    else:
        for bucket, items in found.items():
            print(bucket, len(items))
        print("total unique", len(keys()))
