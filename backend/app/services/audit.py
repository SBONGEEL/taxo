"""سجلُّ التدقيق — **قيدٌ في معاملة التغيير نفسِها** (SPEC §14).

## والقيمةُ قبل وبعد (قرارُ المالك 2026-09-02، البند ٤، §39٫٤)

**وهذا نقضٌ صريحٌ لقاعدةٍ كانت مكتوبة**: «`details` يحمل **أسماءَ الحقول
المتغيّرة فقط، لا قيمَها**». **وعلّةُ النقض بنصِّ المالك**: «كلُّ تعديلٍ أو
حذفٍ مختومٌ في التدقيق: **من ومتى والقيمةُ قبل وبعد**» — و«تغيّر السعر» بلا
رقمين **لا يُجيب من يسأل بعد شهرٍ كم كان**.

**ولمَ كانت القاعدةُ القديمة**: خشيةَ أن يُكتب **سرٌّ** في سجلٍّ يقرؤه
`support` — ومفاتيحُ المزوّدين تمرّ بأبواب تعديل. **والعلّةُ تبقى صحيحة،
فالحلُّ ليس العودةَ عنها بل تضييقُها**: `redact` يمنع القيمةَ حيث كان المنعُ
حقّاً، **ويسمح بها حيث لا سرّ**.

**وحدُّه مكتوب**: القائمةُ **بالاسم لا بالحدس** — وحقلٌ سرِّيٌّ باسمٍ جديدٍ
يمرّ حتى يُضاف. ولذلك تُقرأ الأسماءُ **من سجلِّ المزوّدين نفسِه** حيث توجد،
ولا تُخمَّن من شكل الاسم وحدَه.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from datetime import date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AdminAuditLog
from app.models.enums import AuditAction
from app.models.user import User

#: **ما لا تُكتب قيمتُه أبداً** — والقائمةُ بالاسم لا بالحدس.
#:
#: **ومصدرُها سجلُّ المزوّدين**: `providers/registry.py` يُعلن أيَّ حقلٍ
#: `secret` — وهو الذي يُقنَّع بـ`****` ولا يغادر الخلفية. **وتُقرأ منه لا
#: تُنسخ**، فحقلٌ سرِّيٌّ يُضاف هناك يصير محميّاً هنا بلا سطر.
_ALWAYS_REDACTED = frozenset(
    {"password", "password_hash", "secret", "api_key", "token", "credentials"}
)

#: ما يُكتب مكان القيمة المحجوبة — **«تغيّر» بلا «إلى ماذا»**.
REDACTED = "****"


def _secret_field_names() -> frozenset[str]:
    """أسماءُ الحقول السرّية **مقروءةً من سجلِّ المزوّدين** لا منسوخةً.

    **والاستيرادُ داخل الدالّة**: `registry` يستورد نماذج، واستيرادٌ في الرأس
    يصنع حلقةً — وهو الشكلُ نفسُه في `advances.py`.
    """
    try:
        from app.services.providers.registry import PROVIDERS
    except Exception:  # pragma: no cover - سجلٌّ غيرُ متاحٍ لا يفتح باباً
        return frozenset()
    names: set[str] = set()
    for provider in PROVIDERS.values():
        names |= provider.secret_field_keys
    return frozenset(names)


def redact(field: str, value: Any) -> Any:
    """قيمةٌ صالحةٌ للسجلّ — **أو `****` إن كان الحقلُ سرّاً**.

    **ولا يُخمَّن من شكل الاسم**: `_ALWAYS_REDACTED` أسماءٌ مصرَّحة، ومعها ما
    يُعلنه سجلُّ المزوّدين `secret`. **وحقلٌ سرِّيٌّ باسمٍ جديدٍ يمرّ حتى
    يُضاف** — وهذا مكتوبٌ لا مسكوتٌ عنه.
    """
    lowered = field.lower()
    if lowered in _ALWAYS_REDACTED or lowered in _secret_field_names():
        return REDACTED
    return _plain(value)


def _plain(value: Any) -> Any:
    """قيمةٌ تصلح لـ`JSONB` — **ولا تُفقد دقّةُ المال**.

    `Decimal` تُكتب **نصّاً** لا `float`: `NUMERIC(12,3)` لا يُمثَّل في العائم
    بلا خسارة، **وسجلُّ تدقيقٍ يقول `4.0999999` عن `4.100` سجلٌّ يكذب**.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "value"):  # تعدادٌ نصّيّ
        return value.value
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def apply_changes(instance: object, changes: dict[str, Any]) -> dict[str, dict]:
    """يطبّق ما أُرسل **ويعيد قبلَ وبعدَ لكلِّ ما تغيّر فعلاً**.

    **وبيتٌ واحدٌ لكلِّ تعديل** (البند ٤): كان `_apply_updates` في موجّه
    الإعدادات يعيد **أسماءً بلا قيم**، **ونسخةٌ ثانيةٌ في كلِّ موجّهٍ كانت
    ستفترق** — فانتقل إلى هنا ليصل كلَّ من يعدّل.

    **وما لم يتغيّر لا يُذكر**: حقلٌ أُرسل بقيمته نفسِها ليس تعديلاً، **وذكرُه
    يجعل سجلَّ التدقيق يقول إن شيئاً وقع ولم يقع**.
    """
    recorded: dict[str, dict] = {}
    for field, value in changes.items():
        before = getattr(instance, field)
        if before != value:
            setattr(instance, field, value)
            recorded[field] = {
                "before": redact(field, before),
                "after": redact(field, value),
            }
    return recorded


def snapshot(instance: object, fields: tuple[str, ...]) -> dict[str, Any]:
    """لقطةُ صفٍّ **قبل حذفه** — فالمحذوفُ لا يُقرأ بعد حذفه.

    **وحذفٌ يسجّل معرّفاً وحدَه لا يجيب «ماذا حُذف»**: من يقرأ السجلَّ بعد
    شهرٍ يجد رقماً لا صفَّ له.
    """
    return {field: redact(field, getattr(instance, field, None)) for field in fields}


async def record(
    session: AsyncSession,
    *,
    actor: User | None,
    action: AuditAction,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
    changes: dict[str, dict] | None = None,
) -> AdminAuditLog:
    """يضيف قيد تدقيق للجلسة — الـ commit مسؤولية الراوتر.

    يبقى القيد في نفس معاملة التغيير: إن فشل التغيير لا يبقى أثر كاذب،
    وإن نجح فلا يمكن أن ينجح بلا قيد.
    """
    if changes:
        # **`changes` تُدمج ولا تستبدل**: موجّهاتٌ تكتب سياقاً معها
        # (`country_code` مثلاً)، **ومفتاحٌ يبتلع الآخر يُفقد أحدَهما**
        details = {**(details or {}), "changes": changes}

    entry = AdminAuditLog(
        actor_id=actor.id if actor is not None else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    session.add(entry)
    return entry
