"""تحويلُ أخطاء التحقق إلى عقد الأخطاء (SPEC القسم ١٧).

**هذا الملفُّ هو السجلُّ المركزيُّ لنصوص أخطاء المدخلات**، ولا يُكتب نصٌّ عربيٌّ
لخطأ تحقّقٍ في شاشةٍ ولا في endpoint. والسببُ ليس الترتيب: النصُّ في الشاشة
يختلف عن أخيه في شاشةٍ ثانيةٍ للشرط نفسِه، فيقرأ المستخدمُ رسالتين لخطأٍ واحد
ويظنّهما خطأين.

**ولا يصل المستخدمَ نصُّ Pydantic الخام أبداً** (القسم ١٧.٤): «Input should be a
valid integer» جملةٌ إنجليزيةٌ عن نوعٍ برمجيّ، تُقرأ في تطبيقٍ عربيٍّ عطباً في
التطبيق لا خطأً في الإدخال. والنصُّ الخامُ يذهب إلى السجل كاملاً، حيث يُشخَّص.
"""

from __future__ import annotations

from typing import Any

# **أسماءُ الحقول بالعربية** — وهي ما يقرؤه المستخدم، لا اسمُ العمود.
# وغيابُ اسمٍ هنا ليس عطباً: تُستعمل صيغةٌ بلا اسمٍ («هذه القيمة») بدل أن يُعرض
# `plate_number` — وهو اسمٌ داخليٌّ يمنع القسمُ ١٧.٤ عرضَه.
FIELD_LABELS: dict[str, str] = {
    "make": "الشركة الصانعة",
    "model": "الطراز",
    "year": "سنة الصنع",
    "color": "اللون",
    "plate_number": "رقم اللوحة",
    "stops": "المحطات",
    "category": "فئة المركبة",
    "phone": "رقم الهاتف",
    "password": "كلمة المرور",
    "new_password": "كلمة المرور الجديدة",
    "name": "الاسم",
    "full_name": "الاسم",
    "country_code": "الدولة",
    "verification_token": "رمز التحقق",
    "code": "الرمز",
    "role": "نوع الحساب",
    "gender": "الجنس",
    "cliq_alias": "اسم كليك",
    "referral_code": "رمز الإحالة",
    "amount": "المبلغ",
    "currency": "العملة",
    "reference": "المرجع",
    "reason": "السبب",
    "label": "التسمية",
    "address": "العنوان",
}

# **الحقولُ التي تُؤنَّث أفعالُها.** والعربيةُ لا تحتمل «كلمة المرور مطلوب»:
# جملةٌ مكسورةٌ نحوياً في شاشةِ خطأٍ تُقرأ عطباً في التطبيق لا خطأً في الإدخال،
# فتُضعف ثقةَ قارئها بما بعدها. والجنسُ **يُكتب هنا صراحةً** لأنه خاصّةُ
# الكلمة، ولا يُستنتج من صيغتها: «سنة» مؤنثةٌ و«اسم» مذكَّر، والتاءُ ليست قاعدة.
FEMININE_LABELS = frozenset(
    {
        # **جمعُ مؤنّثٍ سالم** — «المحطات اثنتان على الأكثر» لا «اثنان».
        # وأمسكه `test_label_gender` يومَ أُضيف الوسمُ بلا تصنيف: **الوسمُ
        # والجنسُ يُكتبان معاً، والمذكَّرُ ليس افتراضاً صامتاً**.
        "المحطات",
        "الشركة الصانعة",
        "سنة الصنع",
        "فئة المركبة",
        "كلمة المرور",
        "كلمة المرور الجديدة",
        "الدولة",
        "العملة",
        "التسمية",
        "هذه القيمة",
    }
)


# **والمذكَّرُ يُكتب أيضاً — لا يُترك افتراضاً.** والعلّةُ أن الافتراضَ صامت:
# حقلٌ جديدٌ مؤنَّثٌ يُنسى فيخرج «سنة الصنع مطلوب» ولا شيءَ يفشل. فبكتابة
# القائمتين تصير كلُّ تسميةٍ **مصنَّفةً أو ساقطةً في اختبار**، ولا ثالثَ.
# ويحرسهما `tests/test_label_gender.py`.
MASCULINE_LABELS = frozenset(
    {
        "الطراز",
        "اللون",
        "رقم اللوحة",
        "رقم الهاتف",
        "الاسم",
        "رمز التحقق",
        "الرمز",
        "نوع الحساب",
        "الجنس",
        "اسم كليك",
        "رمز الإحالة",
        "المبلغ",
        "المرجع",
        "السبب",
        "العنوان",
    }
)


def _fem(subject: str) -> bool:
    return subject in FEMININE_LABELS


# **ما لا يُكتب في السجل أبداً** — والتسجيلُ يقع على جسم الطلب كاملاً، فبغير
# هذه القائمة تُكتب كلمةُ المرور في `docker compose logs` بنصٍّ صريح.
# والمقارنةُ **بالاحتواء لا بالتساوي**: `new_password` و`refresh_token`
# و`verification_token` من الجنس نفسِه، وقائمةٌ بالتساوي تفوتها.
SENSITIVE_HINTS = (
    "password",
    "token",
    "secret",
    "code",
    "otp",
    "credential",
    "recovery",
    "pin",
    "cvv",
)

REDACTED = "«محجوب»"


def redact(payload: Any) -> Any:
    """نسخةٌ من الجسم صالحةٌ للسجل — بلا أسرار.

    **وتُبقي المفتاحَ وتحجب القيمة**: من يقرأ السجل يحتاج أن يعرف أن الحقل
    أُرسل أصلاً — وحذفُ المفتاح يجعل «أرسله فارغاً» و«لم يرسله» واحداً، وهما
    خطآن مختلفان تماماً في شاشةِ تسجيل.
    """
    if isinstance(payload, dict):
        return {
            key: (
                REDACTED
                if any(hint in str(key).lower() for hint in SENSITIVE_HINTS)
                else redact(value)
            )
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [redact(item) for item in payload]
    if isinstance(payload, str) and len(payload) > 200:
        return payload[:200] + "…"
    return payload


def field_of(error: dict) -> str | None:
    """اسمُ الحقل من `loc` — أو `None` حين لا يخصّ الخطأُ حقلاً.

    `loc` تبدأ بموضع الخطأ (`body` / `query` / `path`) ثم مسارِ الحقل. ويؤخذ
    **آخرُ جزءٍ نصّي**: في `("body", "stops", 0, "lat")` الحقلُ هو `lat`، ورقمُ
    الفهرس ليس اسمَ حقلٍ يُعلَّم في شاشة.
    """
    parts = [part for part in error.get("loc", ()) if isinstance(part, str)]
    if len(parts) <= 1:
        return None
    return parts[-1]


def label_of(field: str | None) -> str | None:
    return FIELD_LABELS.get(field) if field else None


def chars(count: int) -> str:
    """«محرف» بصيغة العدد العربية — والعربيةُ لا تحتمل «1 محارف».

    التمييزُ في العربية أربعُ صيغ لا صيغتان: المفردُ للواحد، والمثنى للاثنين،
    والجمعُ من ٣ إلى ١٠، والمفردُ منصوباً من ١١ فصاعداً. وجملةٌ مكسورةٌ في
    شاشةِ خطأٍ تُقرأ عطباً في التطبيق لا خطأً في الإدخال، فتُضعف الثقةَ بكل ما
    بعدها — وهذه النصوصُ تُنشر إلى التطبيقات وتُعرض كما هي.
    """
    if count == 1:
        return "محرفٌ واحد"
    if count == 2:
        return "محرفان"
    if 3 <= count <= 10:
        return f"{count} محارف"
    return f"{count} محرفاً"


def items(count: int, one: str, two: str, few: str, many: str) -> str:
    """عددٌ بصيغة العربية الأربع — أختُ `chars` لأيِّ معدودٍ آخر.

    و«٢ محطات» مكسورةٌ كما «1 محارف» مكسورة، **والكسرُ في شاشة خطأٍ يُقرأ
    عطباً في التطبيق لا خطأً في الإدخال**.
    """
    if count == 1:
        return one
    if count == 2:
        return two
    if 3 <= count <= 10:
        return f"{count} {few}"
    return f"{count} {many}"


def condition_label(kind: str, value: int) -> str:
    """وصفُ شرطٍ **مُحقَّقٍ أو غيرِ محقَّق** — لا رسالةَ رفض.

    القائمةُ تحت الحقل تُعلَّم لحظةَ الكتابة (القسم ١٧.٧)، وبندُها يُقرأ قبل
    الخطأ وبعده: «٨ محارف على الأقل ✓». ورسالةُ الرفض («قصيرةٌ جداً — …») تصف
    ما وقع، وهي جملةٌ خاطئةٌ حين يكون الشرطُ محقَّقاً.

    **ويُنشر مع القاعدة** لأن التطبيقَ لا يكتب عربيةً: لو صاغ البندَ بنفسه
    لاحتاج تصريفَ العدد العربيَّ مرةً ثانية — وهو ما تفعله `chars` هنا.
    """
    if kind == "min_length":
        return f"{chars(value)} على الأقل"
    if kind == "max_length":
        return f"{chars(value)} على الأكثر"
    if kind == "min":
        return f"{value} أو أكثر"
    if kind == "max":
        return f"{value} أو أقلّ"
    return ""


def message_for(error: dict) -> str:
    """نصٌّ عربيٌّ لخطأ تحقّقٍ واحد — **ويذكر الحدَّ الذي كُسر**.

    «القيمة غير صالحة» تترك صاحبَها يخمّن، و«بين ١٩٩٠ و٢١٠٠» تُنهي الأمر.
    والحدودُ تُقرأ من `ctx` التي يرسلها Pydantic نفسُه، فلا يُكتب الحدُّ مرتين
    — مرةً في المخطط ومرةً في نصٍّ يخالفه بعد أوّل تعديل.
    """
    kind = error.get("type", "")
    ctx: dict = error.get("ctx") or {}
    name = label_of(field_of(error))
    subject = name or "هذه القيمة"

    if kind == "missing":
        if not name:
            return "حقلٌ مطلوبٌ ناقص"
        return f"{subject} {'مطلوبة' if _fem(subject) else 'مطلوب'}"
    if kind in {
        "int_type",
        "int_parsing",
        "float_type",
        "float_parsing",
        "decimal_parsing",
    }:
        return f"{subject} يجب أن {'تكون' if _fem(subject) else 'يكون'} رقماً"
    if kind == "greater_than_equal":
        return f"{subject} يجب ألّا {'تقلّ' if _fem(subject) else 'يقلّ'} عن {ctx.get('ge')}"
    if kind == "less_than_equal":
        return f"{subject} يجب ألّا {'تزيد' if _fem(subject) else 'يزيد'} عن {ctx.get('le')}"
    if kind == "greater_than":
        return f"{subject} يجب أن {'تكون' if _fem(subject) else 'يكون'} أكبر من {ctx.get('gt')}"
    if kind == "less_than":
        return f"{subject} يجب أن {'تكون' if _fem(subject) else 'يكون'} أصغر من {ctx.get('lt')}"
    if kind == "string_too_short":
        short = "قصيرةٌ جداً" if _fem(subject) else "قصيرٌ جداً"
        return f"{subject} {short} — {chars(int(ctx.get('min_length') or 0))} على الأقل"
    if kind == "string_too_long":
        long = "طويلةٌ جداً" if _fem(subject) else "طويلٌ جداً"
        return f"{subject} {long} — {chars(int(ctx.get('max_length') or 0))} على الأكثر"
    # **قائمةٌ تتجاوز سقفَها** (عقدُ الأخطاء §17): كان `too_long` بلا معالجٍ
    # فيسقط إلى «هذه القيمة غير صالحة» — **رسالةٌ لا تقول الحدَّ ولا تقول ما
    # يُفعل**. قِيس على `stops` بثلاث محطات (2026-08-23).
    if kind == "too_long":
        cap = int(ctx.get("max_length") or 0)
        return f"{subject} {items(cap, 'واحدةٌ على الأكثر', 'اثنتان على الأكثر', 'على الأكثر', 'على الأكثر')}"
    if kind == "too_short":
        floor = int(ctx.get("min_length") or 0)
        return f"{subject} {items(floor, 'واحدةٌ على الأقل', 'اثنتان على الأقل', 'على الأقل', 'على الأقل')}"
    if kind == "string_pattern_mismatch":
        return f"{subject} بصيغةٍ غير صحيحة"
    if kind == "enum":
        return f"{subject} {'ليست' if _fem(subject) else 'ليس'} من القيم المسموحة"
    if kind in {"string_type", "bool_type", "list_type", "dict_type"}:
        return f"{subject} بنوعٍ غير صحيح"
    if kind == "json_invalid":
        return "تعذّرت قراءة الطلب"
    if kind == "value_error":
        # **`ValueError` من مُحقِّقٍ كتبناه نحن** — نصُّه عربيٌّ أصلاً ومقصود،
        # فيُمرَّر كما هو. وغيرُ العربيِّ لا يُعرض: قد يكون نصَّ مكتبة.
        raw = str(ctx.get("error") or "").strip()
        if raw and any("؀" <= ch <= "ۿ" for ch in raw):
            return raw
        return f"{subject} {'غير صالحة' if _fem(subject) else 'غير صالح'}"
    return f"{subject} {'غير صالحة' if _fem(subject) else 'غير صالح'}"
