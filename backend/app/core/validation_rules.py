"""قواعدُ التحقق منشورةً للتطبيقات — SPEC القسم ١٧.٣ (قرارُ المالك 2026-08-18).

**تُشتقّ من مخططات Pydantic برمجياً، ولا تُكتب بيدٍ بجانبها.** والفرقُ ليس
أناقة: حدٌّ مكتوبٌ مرتين — مرةً في المخطط ومرةً في قائمةٍ للنشر — يفترق عند أوّل
تعديل، فيمنع التطبيقُ ما تقبله الخلفيةُ أو يقبل ما ترفضه. وهذا المشروع كسر هذه
القاعدةَ مرةً بالفعل: حدُّ الرسائل رُفع من ٣ إلى ٢٠ في الخدمة وبقي ٣ في اختبارٍ
ينسخه، فظلَّت المجموعةُ حمراءَ بلا أن ينتبه أحد.

**والنصُّ يُنشر مع القاعدة ومصدرُه السجل المركزي وحدَه** (`validation_errors`):
لو صاغ التطبيقُ نصَّه لاختلف عن نصِّ الخلفية للشرط نفسِه، فيقرأ المستخدمُ
رسالتين لخطأٍ واحد ويظنّهما خطأين. فما يُنشر هنا هو **نصُّ الخلفية بعينه**،
مولَّداً بنفس الدالة التي تجيب بها على ٤٢٢.

**والتطبيقُ يتحقق فوراً، والخلفيةُ تبقى المرجعَ النهائي.** المنشورُ يُغني عن
رحلةِ شبكةٍ قبل أن يرى المستخدمُ خطأه، ويعمل والشبكةُ مقطوعة — ولا يُغني عن
الحارس: طلبٌ لم يمرّ بشاشتنا يُفحص هنا كما كان.
"""

from __future__ import annotations

import enum
import types
import typing
from typing import Any

from annotated_types import Ge, Le, MaxLen, MinLen
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from app.core import validation_errors
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.driver import VehicleCreate

# **النماذجُ المنشورة** — وهي التي للتطبيقات شاشاتٌ تحقّقٍ عليها. وإضافةُ نموذجٍ
# هنا تكفي لنشره؛ لا قائمةَ حقولٍ تُكتب بعده.
FORMS: dict[str, type[BaseModel]] = {
    "vehicle_create": VehicleCreate,
    "register": RegisterRequest,
    "login": LoginRequest,
}


def _unwrap_optional(annotation: Any) -> Any:
    """`X | None` ← `X`. والاختياريةُ يقولها `is_required` لا النوع."""
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        args = [arg for arg in typing.get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _choices(annotation: Any) -> list[str] | None:
    """قيمُ التعداد أو `Literal` — أو `None` لما ليس اختياراً من قائمة."""
    annotation = _unwrap_optional(annotation)
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return [str(member.value) for member in annotation]
    if typing.get_origin(annotation) is typing.Literal:
        return [
            str(arg.value if isinstance(arg, enum.Enum) else arg)
            for arg in typing.get_args(annotation)
        ]
    return None


def _kind(annotation: Any) -> str:
    annotation = _unwrap_optional(annotation)
    if _choices(annotation) is not None:
        return "choice"
    if annotation is bool:
        return "boolean"
    if annotation is int or annotation is float:
        return "number"
    return "text"


def _message(field: str, error_type: str, ctx: dict | None = None) -> str:
    """النصُّ من السجل المركزي — **بنفس الدالة التي تجيب بها ٤٢٢**.

    و`loc` تُبنى بشكل الخطأ الحقيقي (`("body", field)`) لأن `field_of` تُسقط
    أوّلَ جزء؛ فبغير الجزء الأول يُقرأ اسمُ الحقل موضعاً ويضيع اسمُه العربي.
    """
    return validation_errors.message_for(
        {"loc": ("body", field), "type": error_type, "ctx": ctx or {}}
    )


def _rule(name: str, field: FieldInfo) -> dict[str, Any]:
    kind = _kind(field.annotation)
    rule: dict[str, Any] = {"type": kind, "required": field.is_required()}
    messages: dict[str, str] = {}

    if field.is_required():
        messages["required"] = _message(name, "missing")
    if kind == "number":
        messages["type"] = _message(name, "int_type")

    for constraint in field.metadata:
        if isinstance(constraint, MinLen):
            rule["min_length"] = constraint.min_length
            messages["min_length"] = _message(
                name, "string_too_short", {"min_length": constraint.min_length}
            )
        elif isinstance(constraint, MaxLen):
            rule["max_length"] = constraint.max_length
            messages["max_length"] = _message(
                name, "string_too_long", {"max_length": constraint.max_length}
            )
        elif isinstance(constraint, Ge):
            rule["min"] = constraint.ge
            messages["min"] = _message(name, "greater_than_equal", {"ge": constraint.ge})
        elif isinstance(constraint, Le):
            rule["max"] = constraint.le
            messages["max"] = _message(name, "less_than_equal", {"le": constraint.le})

    choices = _choices(field.annotation)
    if choices is not None:
        rule["choices"] = choices
        messages["choices"] = _message(name, "enum")

    label = validation_errors.label_of(name)
    if label:
        rule["label"] = label
    rule["messages"] = messages

    # **الشروطُ قائمةً تُعلَّم لحظةَ الكتابة** (القسم ١٧.٧) — ونصُّها يُنشر هنا
    # لا يُصاغ في التطبيق: بندٌ يصوغه التطبيقُ يحتاج تصريفَ العدد العربيِّ
    # مرةً ثانية، وصياغتان لشرطٍ واحدٍ تفترقان.
    conditions = [
        {"key": key, "label": validation_errors.condition_label(key, rule[key])}
        for key in ("min_length", "max_length", "min", "max")
        if key in rule
    ]
    if conditions:
        rule["conditions"] = conditions
    return rule


def rules_for(model: type[BaseModel]) -> dict[str, dict[str, Any]]:
    return {name: _rule(name, field) for name, field in model.model_fields.items()}


def published_rules() -> dict[str, dict[str, dict[str, Any]]]:
    """ما يخرج في `GET /config` — يُبنى عند كل نداء، فلا نسخةَ تبرد."""
    return {form: rules_for(model) for form, model in FORMS.items()}
