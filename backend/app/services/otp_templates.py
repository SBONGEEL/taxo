"""قوالبُ رسالة الرمز: القراءةُ والتحقّقُ والاستبدال.

**الحارسُ انتقل ولم يُحذف** (قرارُ المالك 2026-08-19). كان وعدُ البوابة «لا بابَ
يقبل نصّاً»، وصياغتُها للنصّ هي التي تحرسه. والوعدُ الحقيقيُّ لم يكن «البوابةُ
تصوغ» بل **«لا يخرج على السلك ما يخالف الشروط»** — وهذا يبقى محروساً بمن يملك
السلك، بالفحص بدل الصياغة. من قرأ هذا لاحقاً فلا يقرأه تنازلاً.

**والفحصُ في موضعين من مصدرٍ واحد**: هنا ليعرف المشرفُ رفضَه في اللوحة، وفي
البوابة لئلا يخرج المرفوضُ على السلك. ولو كان الفحصُ عند البوابة وحدَها لاكتشف
المشرفُ خطأه من رسالةٍ لم تصل.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.otp_template import OtpMessageTemplate, OtpTemplatePurpose

# ------------------------------------------------------------ الشروط

# **ملفٌ واحدٌ تقرؤه الخلفيةُ والبوابة** — مربوطٌ للقراءة في docker-compose.yml.
# وغيابُه لا يُسقط التسجيل: الشروطُ المدمجةُ أدناه نسخةُ طوارئ، وتُسجَّل صراحةً
_RULES_PATH = Path("/app/otp_template_rules.json")
_FALLBACK_RULES = {
    "max_body_bytes": 3989,
    "required_variables": ["code"],
    "optional_variables": ["app_name", "minutes"],
    "forbidden_patterns": [
        {"name": "scheme", "pattern": r"https?://", "flags": "i", "why": "رابطٌ صريح"},
    ],
}

_PLACEHOLDER = re.compile(r"\{([^{}]*)\}")


@lru_cache(maxsize=1)
def rules() -> dict:
    try:
        return json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # pragma: no cover - مسارُ طوارئ
        import logging

        logging.getLogger(__name__).warning(
            "otp_template_rules_unreadable path=%s — تُستعمل الشروطُ المدمجة",
            _RULES_PATH,
        )
        return _FALLBACK_RULES


def max_bytes() -> int:
    return int(rules()["max_body_bytes"])


def known_variables() -> tuple[str, ...]:
    r = rules()
    return tuple(r["required_variables"]) + tuple(r["optional_variables"])


# ------------------------------------------------------------ النصُّ الافتراضي

# **منقولٌ بقيمته الحالية حرفياً** من `whatsapp-gateway/src/session.js::MESSAGE`
# (قرارُ المالك: لا تحسّن الصياغة). وكان **نصّاً واحداً يخدم المسارين**، فنُسخ
# كما هو في القالبين — والفرقُ بينهما من اليوم قرارُ مشرفٍ لا قرارُ شيفرة.
_DEFAULT_BODY = "رمز تأكيد رقمك في تاكسو: {code}\nصالح {minutes} دقيقة. لا تشاركه مع أحد."

DEFAULTS: dict[str, str] = {
    OtpTemplatePurpose.REGISTRATION: _DEFAULT_BODY,
    OtpTemplatePurpose.PASSWORD_RESET: _DEFAULT_BODY,
}


# ------------------------------------------------------------ التحقّق


@dataclass(frozen=True, slots=True)
class Violation:
    """مخالفةٌ واحدة — `code` للسجل و`message` عربيةٌ جاهزةٌ للعرض (§17)."""

    code: str
    message: str


def validate(body: str, *, purpose: str) -> list[Violation]:
    """يعيد كلَّ ما يخالف، لا أوّلَ ما يخالف.

    ومن يصحّح خطأً ثم يُبلَّغ بغيره يظنّ التحققَ عابثاً — فتُقال المخالفاتُ معاً.
    """
    label = PURPOSE_LABEL.get(purpose, purpose)
    out: list[Violation] = []
    r = rules()

    if not body.strip():
        out.append(Violation("template_empty", f"نصُّ «{label}» فارغ"))
        return out

    found = {m.group(1).strip() for m in _PLACEHOLDER.finditer(body)}
    known = set(known_variables())

    for required in r["required_variables"]:
        if required not in found:
            out.append(
                Violation(
                    "template_missing_variable",
                    f"ينقص «{label}» المتغيّرُ {{{required}}} — ولا رسالةَ رمزٍ بلا رمز",
                )
            )

    for unknown in sorted(found - known):
        shown = unknown or "فراغ"
        out.append(
            Violation(
                "template_unknown_variable",
                f"متغيّرٌ مجهولٌ في «{label}»: {{{shown}}} — "
                f"والمعروفُ منها: {'، '.join('{' + v + '}' for v in known_variables())}",
            )
        )

    size = len(body.encode("utf-8"))
    if size > r["max_body_bytes"]:
        out.append(
            Violation(
                "template_too_long",
                f"نصُّ «{label}» أطولُ مما تقبله القناة: {size} بايت "
                f"والحدُّ {r['max_body_bytes']}",
            )
        )

    for pattern in r["forbidden_patterns"]:
        flags = re.IGNORECASE if "i" in pattern.get("flags", "") else 0
        if re.search(pattern["pattern"], body, flags):
            # **الرسالةُ تسمّي نوعَ المخالفة لا تجمعها**: «يحمل رابطاً» عن
            # خانةٍ عربيةٍ تُربك من يقرؤها ويبحث عن رابطٍ لا وجودَ له.
            if pattern.get("kind") == "digits":
                out.append(
                    Violation(
                        "template_has_arabic_digits",
                        f"«{label}» يحمل خاناتٍ عربية-هندية — وصيغةُ العرض في "
                        "المنصّة كلِّها لاتينية، والرمزُ يخرج لاتينياً",
                    )
                )
            else:
                out.append(
                    Violation(
                        "template_has_link",
                        f"«{label}» يحمل رابطاً ({pattern['why']}) — "
                        "ورسائلُ هذا الرقم بلا روابط، وهو شرطُ بقائه",
                    )
                )

    return out


PURPOSE_LABEL = {
    OtpTemplatePurpose.REGISTRATION: "قالب التسجيل",
    OtpTemplatePurpose.PASSWORD_RESET: "قالب استعادة كلمة المرور",
}


# ------------------------------------------------------------ الاستبدال


def render(body: str, *, code: str, minutes: int, app_name: str = "تاكسو") -> str:
    """يستبدل المعروفَ ولا يترك مجهولاً.

    و`str.format` لا تصلح: قوسٌ مفردٌ في نصٍّ عربيٍّ يرفع `KeyError` وقتَ
    الإرسال — أي عطبٌ في مسارِ رمزٍ ينتظره إنسان. فالاستبدالُ صريحٌ بالمعروف.
    """
    values = {"code": code, "minutes": str(minutes), "app_name": app_name}
    return _PLACEHOLDER.sub(
        lambda m: values.get(m.group(1).strip(), m.group(0)), body
    )


# ------------------------------------------------------------ القراءة


async def body_for(session: AsyncSession, purpose: str) -> str:
    """نصُّ هذا الغرض — أو الافتراضيُّ إن كان فارغاً أو مخالفاً.

    **ولا تسقط قناةُ التسجيل بنصٍّ محرَّرٍ خطأً**: صفٌّ محفوظٌ ثم عُدِّلت شروطُه
    (سقفٌ ضُيّق مثلاً) يصير مخالفاً وهو مكتوب، والقناةُ أهمُّ من احترامِ صفّ.
    """
    row = await session.scalar(
        select(OtpMessageTemplate).where(OtpMessageTemplate.purpose == purpose)
    )
    default = DEFAULTS.get(purpose, _DEFAULT_BODY)
    if row is None:
        return default
    if validate(row.body, purpose=purpose):
        import logging

        logging.getLogger(__name__).warning(
            "otp_template_rejected_at_read purpose=%s — يُستعمل النصُّ الافتراضي",
            purpose,
        )
        return default
    return row.body


async def all_templates(session: AsyncSession) -> dict[str, OtpMessageTemplate | None]:
    rows = await session.scalars(select(OtpMessageTemplate))
    by_purpose = {row.purpose: row for row in rows}
    return {p: by_purpose.get(p) for p in OtpTemplatePurpose.ALL}
