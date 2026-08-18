"""قائمةُ المنع لكلمات المرور — إذنُ المالك 2026-08-18.

**وهي البديلُ الذي يوصي به الدليلُ عن قواعد التركيب.** `NIST SP 800-63B` يمنع
فرضَ «رقمٍ وحرفٍ كبير» لأنها تُنتج أنماطاً متوقّعة (`Taxi2024`) فترفع الإزعاجَ
لا العشوائية، ويوصي بدلَها بـ**طولٍ أدنى وقائمةِ منع**. فهذا ما بُني: الطولُ
كما هو (٨–١٢٨) بلا شرطِ تركيبٍ واحد، ومعه ثلاثةُ أصنافِ منعٍ لا رابع.

**ولا تُنشر القائمةُ ولا يُكشف عددُها** (شرطُ المالك): `GET /config` ينشر الحدود
لا هذه. وقائمةٌ منشورةٌ تُقرأ **دليلَ تخمينٍ مرتَّباً** — وهي نفسُها ما يجرّبه
المهاجمُ أولاً.

**والرفضُ يقول سببَه ولا يقول القائمة**: «هذه من الأكثر شيوعاً» تكفي صاحبَها
ليختار غيرَها، ولا تخبر أحداً بما فيها. ورفضٌ بلا سببٍ يجعل صاحبَه يجرّب
كلماتٍ من الجنس نفسِه.
"""

from __future__ import annotations

import re

from app.core.exceptions import (
    PasswordIsPhone,
    PasswordTooCommon,
    PasswordTooRepetitive,
)

# **أشيعُ ما يُجرَّب أولاً** — وكلُّها ثماني خاناتٍ فأكثر عمداً: ما دونها يرفضه
# حدُّ الطول أصلاً، فوضعُه هنا سطرٌ لا يعمل. وفيها ما يخصّ سوقَنا (`taxo…`)
# لأن اسمَ المنصّة أوّلُ ما يخطر لمن يسجّل فيها.
COMMON_PASSWORDS = frozenset(
    {
        "12345678",
        "123456789",
        "1234567890",
        "87654321",
        "987654321",
        "01234567",
        "11111111",
        "00000000",
        "12341234",
        "password",
        "password1",
        "password123",
        "passw0rd",
        "qwerty123",
        "qwertyui",
        "qwertyuiop",
        "1q2w3e4r",
        "1qaz2wsx",
        "q1w2e3r4",
        "qazwsxedc",
        "asdfghjk",
        "asdfghjkl",
        "zxcvbnm1",
        "abc12345",
        "abcd1234",
        "a1b2c3d4",
        "iloveyou",
        "princess",
        "sunshine",
        "football",
        "baseball",
        "superman",
        "starwars",
        "computer",
        "whatever",
        "trustno1",
        "letmein1",
        "welcome1",
        "welcome123",
        "monkey12",
        "dragon12",
        "master12",
        "shadow12",
        "freedom1",
        "michael1",
        "jordan23",
        "admin123",
        "administrator",
        "root1234",
        "taxo1234",
        "taxo12345",
        "taxi1234",
        "captain1",
    }
)

# **تكرارٌ بحت**: نمطٌ طولُه ثلاثةٌ فأقلَّ يملأ الكلمةَ كلَّها — `aaaaaaaa`
# و`abababab` و`123123123`. والحدُّ ثلاثةٌ لا أكثر: نمطٌ من أربعةٍ فصاعداً
# (`1q2w1q2w`) كلمةٌ ضعيفةٌ لكنها ليست «تكراراً بحتاً»، ومنعُها يوسّع القاعدةَ
# إلى ما لم يُؤذن به.
_MAX_REPEATED_UNIT = 3

# أقصرُ ذيلٍ يُعدّ «رقمَ هاتفٍ»: سبعُ خاناتٍ — أقلُّ منها رقمٌ لا يعرّف أحداً،
# ويرفضه حدُّ الطول أصلاً حين يقلّ عن ثمان.
_MIN_PHONE_TAIL = 7


def _is_pure_repetition(value: str) -> bool:
    for size in range(1, _MAX_REPEATED_UNIT + 1):
        if len(value) % size:
            continue
        unit = value[:size]
        if unit * (len(value) // size) == value:
            return True
    return False


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def check(password: str, *, phone: str | None = None) -> None:
    """يرفع خطأً مسمّى السبب — أو لا يفعل شيئاً.

    **والترتيبُ مقصود**: الشيوعُ أولاً لأنه أخطرُها (يُجرَّب أولاً في أي هجوم)،
    ثم الهاتفُ (يعرفه من يعرف صاحبَه)، ثم التكرار.
    """
    if password.strip().lower() in COMMON_PASSWORDS:
        raise PasswordTooCommon()

    if phone:
        # **«رقمُ هاتفه» يعني الرقمَ وحدَه، لا كلمةً تصادف أن فيها خاناتِه.**
        # وأوّلُ نسخةٍ قارنت بالاحتواء المجرّد فرفضت `SuperSecret123`: خاناتُها
        # `123`، وهي جزءٌ من `962791234567`. سقط بها **٢٧ اختباراً** — وهو
        # الفرقُ بين حارسٍ يمنع ما قُصد ومنعٍ يصيب من لم يُقصد.
        #
        # فالشرطان معاً: أن يكون النصُّ **خاناتٍ وحدَها** (بعد إسقاط الفواصل)،
        # وأن يطابق الرقمَ أو يكون ذيلاً له بسبع خاناتٍ فأكثر — فتُلتقط الصيغُ
        # الثلاث (`0791234567` · `+962791234567` · `791234567`) ولا يُلتقط غيرها.
        compact = re.sub(r"[\s+\-()]", "", password)
        if compact.isdigit():
            digits = compact.lstrip("0")
            phone_digits = _digits(phone).lstrip("0")
            if (
                digits
                and phone_digits
                and len(digits) >= _MIN_PHONE_TAIL
                and (
                    digits == phone_digits
                    or phone_digits.endswith(digits)
                    or digits.endswith(phone_digits)
                )
            ):
                raise PasswordIsPhone()

    if _is_pure_repetition(password):
        raise PasswordTooRepetitive()
