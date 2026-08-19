"""حارسٌ كانس: **لا خانةَ عربية-هندية في نصٍّ تنشره الخلفية** (2026-08-19).

**بمنطق حارس المال نفسِه** (`tests/money_format.py`): يمرّ على كل جوابٍ تنتجه
المجموعة، ويقرأ كل سلسلةٍ فيه، ويفشل إن وجد `٠-٩` أو `۰-۹`.

**ولماذا في الخلفية وقد قُلبت الواجهات؟** لأن الواجهةَ تعرض ما يصلها. رسالةُ
خطأٍ أو نصُّ إشعارٍ أو حدٌّ منشورٌ يحمل خانةً عربيةً يظهر على الشاشة كما هو —
ولا يمرّ بمصفى `digits` لأنه **نصٌّ لا رقم**. وحارسُ الواجهة يقرأ الشيفرة، وهذا
يقرأ ما خرج منها فعلاً؛ ولا يغني أحدُهما عن الآخر.

**وحدُّه مُعلَنٌ لا مخفيّ**: ما لا تلمسه المجموعةُ لا يُفحص — يحرس ما يُمارَس
ولا يدّعي أكثر.
"""

from __future__ import annotations

import re
from typing import Any

# الخاناتُ العربية-الهندية والفارسية — لا يجوز أن تصل نصّاً منشوراً
ARABIC_INDIC = re.compile(r"[٠-٩۰-۹]")

# **مفاتيحُ يُسمح لقيمها بها**، وكلٌّ بسببه:
# - `reason` و`details`: نصٌّ يكتبه مشرفٌ بلوحة مفاتيحه، لا نصٌّ ننشئه نحن.
#   ومنعُه يعني رفضَ ما كتبه إنسانٌ عن قرارٍ اتخذه.
# - `body` و`preview`: قالبُ رسالة الرمز — نصٌّ يحرّره المشرف (SPEC §19).
_AUTHORED_BY_A_HUMAN = frozenset(
    {"reason", "details", "note", "notes", "body", "preview", "message_template"}
)


def _walk(node: Any, path: str, out: list[str], *, inherited_free: bool = False) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            free = inherited_free or key in _AUTHORED_BY_A_HUMAN
            _walk(value, f"{path}.{key}", out, inherited_free=free)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _walk(value, f"{path}[{index}]", out, inherited_free=inherited_free)
    elif isinstance(node, str) and not inherited_free:
        found = ARABIC_INDIC.findall(node)
        if found:
            out.append(f"{path} = {node[:70]!r}")


def offences(payload: Any) -> list[str]:
    out: list[str] = []
    _walk(payload, "$", out)
    return out
