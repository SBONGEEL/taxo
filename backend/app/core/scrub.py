"""تنظيفُ ما يصل من الأجهزة — **البابُ الذي لا يُفتح إلا لما سُمّي** (§D10).

**هذا الملفُّ هو الحارس، لا التوثيقُ الذي يصفه.** ما يمرّ منه يُخزَّن، وما لا
يمرّ لا يُخزَّن — ولا موضعَ ثانٍ يقرّر.

## القاعدةُ: بياضٌ للبنية، سوادٌ للنصّ الحرّ

**والقسمةُ ليست ذوقاً**. البنيةُ نعرف حقولَها بالاسم، فتُبنى الحمولةُ الخارجةُ
من **قائمةٍ بيضاءَ مسمّاة** (`schemas/error_report.py`) لا بحذفٍ ممّا وصل:
قائمةٌ سوداءُ على بنيةٍ **تكون خاطئةً أوّلَ حقلٍ يُضاف بعد شهر**، ومن يضيفه لا
يعرف أن هنا قائمةً تحتاج تحديثاً. وهي علّةُ `check:readers` نفسُها: **البلاغُ
عن المنسيِّ لا عن المُمرَّر جملةً**.

**والنصُّ الحرُّ لا يُبيَّض**: رسالةُ استثناءٍ قد تحمل أيَّ شيء، فلا سبيلَ إلى
تعداد ما يُسمح به فيها. فيبقى السوادُ — أنماطٌ تُعرف بشكلها لا بموضعها.

## وما لا يَعِد به هذا الملفّ

**لا يَعِد بأنّ كلَّ سرٍّ يُمسَك.** نمطٌ لم يُكتب هنا يمرّ — ورقمٌ بصيغةٍ لم
تخطر لكاتبه يمرّ. **وهذا يُقال ولا يُسكت عنه**: الضمانةُ الحقيقيةُ هي
**قِصَرُ ما يُرسَل أصلاً** (لا أجسامَ طلبات، ولا إحداثيّات، ولا رؤوس) —
والسوادُ هنا شبكةٌ ثانيةٌ تحت الأولى، لا الأولى نفسُها.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any

from app.core.config import settings
from app.core.validation_errors import SENSITIVE_HINTS

#: **مفرداتُ الحجب في بيتٍ واحد** — `SENSITIVE_HINTS` جاءت من معالج الـ٤٢٢
#: (كلمةُ مرورٍ ورمزٌ وسرّ)، **وهذه تضمّ إليها ما يخصّ الأشخاص والمال**.
#: ونسختان تفترقان أوّلَ تعديل، فتُقبل هنا قيمةٌ يرفضها هناك — وهو ما صار
#: `otp-template-rules.json` ملفّاً واحداً يقرؤه اثنان.
PII_HINTS: tuple[str, ...] = SENSITIVE_HINTS + (
    "phone",
    "mobile",
    "msisdn",
    "email",
    "lat",
    "lng",
    "lon",
    "coord",
    "position",
    "location",
    "national",
    "plate",
    "iban",
    "alias",
    "amount",
    "balance",
    "fare",
    "price",
    "total",
    "commission",
    "payout",
    "name",
)

#: **ولمَ كلٌّ منها رمزُه**: «محجوب» واحدةٌ لكلِّ شيءٍ تجعل من يقرأ الأثرَ
#: لا يعرف **ما الذي كان هناك** — ومعرفةُ «كان رقمَ هاتف» تُشخِّص، بلا أن
#: يُطبع الرقم. وهي «أبقِ المفتاحَ واحجب القيمة» في النصّ الحرّ.
_PHONE = "«رقم»"
_MONEY = "«مبلغ»"
_UUID = "«مُعرِّف»"
_EMAIL = "«بريد»"
_COORD = "«إحداثية»"

# **الترتيبُ جزءٌ من الصحّة**: المُعرِّفُ يحمل شُرَطاً وأرقاماً، فلو سبقه نمطُ
# الأرقام لَقطّعه إلى أشلاءَ تُقرأ ركاماً. فالأطولُ شكلاً يُمسَك أوّلاً.
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
            r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
        ),
        _UUID,
    ),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), _EMAIL),
    # إحداثيّةٌ عشريّةٌ بزوجٍ — `31.9539, 35.9106`
    (
        re.compile(r"(?<![\d.])-?\d{1,3}\.\d{4,}\s*,\s*-?\d{1,3}\.\d{4,}(?![\d.])"),
        _COORD,
    ),
    # **مبلغٌ بثلاث خانات** — صيغةُ المال في هذا المشروع كلِّه (`NUMERIC(12,3)`)
    (re.compile(r"(?<![\d.])\d+\.\d{3}(?![\d.])"), _MONEY),
    # **رقمٌ طويلٌ متّصل** — هاتفٌ بصيغته الدولية أو المحلية، أو ما يشبهه.
    # والحدُّ تسعةٌ: أرقامُ الأسطر في أثر المكدَّس أقصرُ من ذلك بكثير، فلا
    # يُمسَح `main.tsx:142:18` وهو ما يُشخَّص به.
    (re.compile(r"(?<!\d)(?:\+|00)?\d{9,15}(?!\d)"), _PHONE),
)

#: مقاسٌ لكلِّ حقلٍ حرّ — **والقصُّ قبل الحجب لا بعده**، فنصٌّ ضخمٌ لا يُمسح كلُّه
_MESSAGE_LIMIT = 2_000
_STACK_LIMIT = 8_000
_NOTE_LIMIT = 500
_CRUMB_TEXT_LIMIT = 200
_MAX_CRUMBS = 20


def scrub_text(value: str | None, *, limit: int = _MESSAGE_LIMIT) -> str:
    """نصٌّ حرٌّ صالحٌ للتخزين — مقصوصٌ ثمّ محجوبٌ بالأنماط."""
    if not value:
        return ""
    text = str(value)[:limit]
    for pattern, token in _PATTERNS:
        text = pattern.sub(token, text)
    return text


def scrub_stack(value: str | None) -> str | None:
    """أثرُ المكدَّس — **مقاسُه أوسعُ لأنه هو المُشخِّص**."""
    if not value:
        return None
    return scrub_text(value, limit=_STACK_LIMIT) or None


def scrub_note(value: str | None) -> str | None:
    """جملةُ صاحبِ الجهاز — **تُحجب ولا تُرفض**.

    **والفرقُ مقصود**: رفضُ الرسالة كلِّها لأن فيها رقماً يُضيّع التقريرَ
    الذي تطوّع به صاحبُه، **وهو أندرُ ما يصلنا وأغلاه**. فيُحجب الرقمُ وتبقى
    الجملة: «كتبتُ «رقم» ولم يصلني شيء» تُقرأ وتُفهم.

    **ولا تُنظَّف في الجهاز**: الكتابةُ تُرى وهي تُكتب، وتبديلُ ما يكتبه إنسانٌ
    تحت إصبعه أسوأُ من الحجب عنده. فالخادمُ هو المُنظِّف، **وهو الذي يُختبَر**.
    """
    if not value:
        return None
    return scrub_text(value.strip(), limit=_NOTE_LIMIT) or None


def hash_device(client_hash: str) -> str:
    """مُعرِّفُ جهازٍ لا يُوصَل بصاحبه — **مِلحٌ لا يغادر الخادم**.

    الجهازُ يرسل `sha256` لمُعرِّفه، **والخادمُ يملّحه ثانيةً**: فلا الخامُ يمرّ
    على السلك، ولا المخزَّنُ يُطابَق بما في `device_tokens` — **والخلفيةُ تملك
    كلَّ المُعرِّفات، فبغير المِلح تستطيع الوصل**.

    **وقوّتُه قوّةُ `jwt_secret`، وهي تُقال لا تُدَّعى**: افتراضُه `change-me`
    بقرارٍ معلَن في `core/config.py`. فحيث لم يُضبط، **المِلحُ معلوم** ويصير
    هذا تعميةً أمام من يقرأ الجدول، لا أمام من يملك الشيفرة. وضبطُه معروضٌ
    على المالك في `HANDOFF.md` — وهذا أحدُ ما يزيده ثمناً.
    """
    salt = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        b"taxo.error-reports.device-salt.v1",
        hashlib.sha256,
    ).digest()
    return hashlib.sha256(salt + client_hash.encode("utf-8")).hexdigest()[:12]


_PATH_SEGMENT = re.compile(r"^[0-9a-fA-F-]{8,}$|^\d+$")


def safe_route(route: str | None) -> str | None:
    """قالبُ المسار — **والعميلُ يُرسله قالباً، وهذا يحرسه إن لم يفعل**.

    الشاشةُ ترسل `/rides/:rideId/pay`، **لكنّ حارساً يثق بما يصله ليس حارساً**.
    فكلُّ مقطعٍ يشبه مُعرِّفاً يصير `:id` هنا أيضاً.

    **والفائدةُ مزدوجة**: لا مُعرِّفَ يُخزَّن، **والتجميعُ يصحّ** — بغيره تصير
    كلُّ رحلةٍ مساراً مستقلّاً فينقسم العطبُ الواحدُ مئةَ مجموعة.
    """
    if not route:
        return None
    parts = [
        ":id" if _PATH_SEGMENT.match(part) else part
        for part in route.split("?")[0].split("/")
    ]
    return "/".join(parts)[:200]


#: **مفاتيحُ الفُتات المسموحة** — قائمةٌ بيضاءُ لأنها بنية
_CRUMB_KEYS = ("at", "kind", "route", "method", "path", "status", "level", "text")


def scrub_breadcrumbs(items: Any) -> list[dict[str, Any]] | None:
    """الفُتاتُ — **يُبنى من جديدٍ ولا يُنقَّح ما وصل**.

    كائنٌ يُنسخ ثمّ تُحذف منه حقولٌ يحمل ما لم يُفكَّر فيه؛ وكائنٌ **يُبنى**
    من مفاتيحَ مسمّاةٍ لا يحمل إلا ما سُمّي. وهي القاعدةُ نفسُها في رأس الملفّ.
    """
    if not isinstance(items, list):
        return None

    built: list[dict[str, Any]] = []
    for item in items[:_MAX_CRUMBS]:
        if not isinstance(item, dict):
            continue
        crumb: dict[str, Any] = {}
        for key in _CRUMB_KEYS:
            if key not in item:
                continue
            value = item[key]
            if key == "path":
                crumb[key] = safe_route(str(value))
            elif key == "status":
                crumb[key] = int(value) if isinstance(value, (int, float)) else None
            elif isinstance(value, str):
                crumb[key] = scrub_text(value, limit=_CRUMB_TEXT_LIMIT)
            elif isinstance(value, (int, float, bool)):
                crumb[key] = value
        if crumb:
            built.append(crumb)
    return built or None


def has_pii_key(key: str) -> bool:
    """أيحمل اسمُ الحقل مفردةً محجوبة؟ — بالاحتواء لا بالتساوي."""
    lowered = key.lower()
    return any(hint in lowered for hint in PII_HINTS)
