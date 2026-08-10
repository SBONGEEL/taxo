"""رمز كليك الديناميكي لدفع الرحلة — **الملف الوحيد الذي يعرف صيغة الرمز**.

القسم 6 من SPEC يصف القناة: «TAXO يولّد QR ديناميكياً بصيغة CliQ يحمل alias
الكبتن والمبلغ ومرجعاً داخلياً يولّده TAXO، ومعه deep link يفتح تطبيق البنك».
ولا acquirer في هذه القناة ولا يمكن أن يكون: المال ينتقل من الراكب إلى alias
**الكبتن** مباشرةً فلا يمر بحساب الشركة، فلا شاهد له سوى السجل والمرجع.

**الرمز يُبنى في الخلفية لا في الواجهة** (SPEC القسم 14): يحمل مبلغاً ومرجعاً
يُحاسَب عليهما، وواجهةٌ تبنيه هي واجهةٌ تختار ما يُدفع. الواجهة ترسم الحمولة
النصّية رمزاً مربّعاً وتعرض الرابط لا غير.

> **ثلاثة تفاصيل تحتاج مطابقةً بالتوثيق قبل أول تشغيل حقيقي**، كالتي في
> `card_gateway/telr.py` و`cliq/acquirer.py` — لم يُسلَّم توثيق JoPACC في جلسة
> التنفيذ. الهيكل نفسه **معياري** (EMVCo Merchant-Presented Mode: TLV
> ثنائيّة الخانة مع CRC-16/CCITT في الحقل 63)، وما دونه هو ما يخص كليكاً
> بعينه، مجموعاً في ثوابت مسمّاة تُطابَق في دقائق:
>
> 1. `CLIQ_GUID` — معرّف نظام كليك داخل قالب حساب التاجر (26).
> 2. `MERCHANT_CATEGORY_CODE` — رمز فئة التاجر (4121 = تاكسي).
> 3. `DEEP_LINK_TEMPLATE` — مخطط الرابط الذي يفتح تطبيق البنك.
>
> وخطؤها لا يحرّك مالاً خطأً: لا شيء في هذا الملف يكتب في الدفتر ولا يغيّر
> حالة دفعة. رمزٌ لا يقرؤه تطبيق البنك يعني راكباً يحوّل يدوياً على الـ alias
> المعروض بجانبه ثم يُدخل المرجع كما يفعل اليوم — القناة تعمل بلا الرمز،
> والرمز راحةٌ فوقها.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import quote

from app.models.enums import Currency

# ---------------------------------------------------------- ثوابت الصيغة

# معرّفات حقول EMVCo المستعملة (المعيار نفسه، لا اجتهاد فيه)
TAG_PAYLOAD_FORMAT = "00"
TAG_INITIATION_METHOD = "01"
TAG_MERCHANT_ACCOUNT = "26"
TAG_MERCHANT_CATEGORY = "52"
TAG_CURRENCY = "53"
TAG_AMOUNT = "54"
TAG_COUNTRY = "58"
TAG_MERCHANT_NAME = "59"
TAG_MERCHANT_CITY = "60"
TAG_ADDITIONAL_DATA = "62"
TAG_CRC = "63"

# داخل قالب حساب التاجر (26) وداخل قالب البيانات الإضافية (62)
SUBTAG_GUID = "00"
SUBTAG_ALIAS = "01"
SUBTAG_REFERENCE_LABEL = "05"

PAYLOAD_FORMAT_VERSION = "01"
# «ديناميكي»: رمزٌ لعمليةٍ واحدة بمبلغها ومرجعها، لا لافتةٌ ثابتة على الحائط
INITIATION_DYNAMIC = "12"

# (1) معرّف نظام كليك داخل قالب حساب التاجر — يحتاج مطابقة
CLIQ_GUID = "JO.COM.JOPACC.CLIQ"
# (2) رمز فئة التاجر: 4121 = سيارات الأجرة (ISO 18245) — يحتاج مطابقة
MERCHANT_CATEGORY_CODE = "4121"

# أرقام العملات بمعيار ISO 4217 — الحقل 53 رقميٌّ لا حرفي
CURRENCY_NUMERIC: dict[Currency, str] = {
    Currency.JOD: "400",
    Currency.LYD: "434",
}

# اسم المستفيد ومدينته كما يظهران في تطبيق البنك. الاسم اسم المنصة لا اسم
# الكبتن: هوية الكبتن لا تُنشر، والـ alias وحده هو ما يُحوَّل عليه
MERCHANT_NAME = "TAXO"
MERCHANT_CITY = "AMMAN"

# (3) رابطٌ يفتح تطبيق البنك على شاشة تحويلٍ مملوءة — يحتاج مطابقة
DEEP_LINK_TEMPLATE = (
    "cliq://transfer?alias={alias}&amount={amount}&currency={currency}&reference={reference}"
)

# المرجع الداخلي: قصيرٌ ليسع حقل «الملاحظة» في تطبيقات البنوك وحدَّ EMVCo
# (25 حرفاً للحقل 62/05)، وعشوائيٌّ لا متسلسل — مرجعٌ يُخمَّن مرجعٌ يُنتحل
REFERENCE_PREFIX = "TAXO"
REFERENCE_RANDOM_CHARS = 10
REFERENCE_ALPHABET = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # بلا I وO


@dataclass(frozen=True, slots=True)
class CliqRideCharge:
    """ما تعرضه شاشة دفع كليك: على مَن يُحوَّل، وكم، وبأيّ مرجع."""

    alias: str
    reference: str
    amount: Decimal
    currency: Currency
    qr_payload: str
    deep_link: str


def new_reference() -> str:
    """مرجعٌ داخلي يولّده TAXO — به يعرف الطرفان أيَّ حوالةٍ يتكلمان عنها."""
    body = "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(REFERENCE_RANDOM_CHARS))
    return f"{REFERENCE_PREFIX}{body}"


# ------------------------------------------------------------ بناء الحمولة


def _tlv(tag: str, value: str) -> str:
    """حقلٌ واحد: معرّفان، طولان، ثم القيمة — أساس صيغة EMVCo كلها."""
    return f"{tag}{len(value):02d}{value}"


def crc16(payload: str) -> str:
    """CRC-16/CCITT-FALSE كما يفرضه المعيار للحقل 63.

    يُحسب على النص كاملاً **بما فيه** `6304` نفسه — وهذا ليس تفصيلاً: قارئٌ
    يحسبه بدونه يرفض كل رمزٍ صحيح.
    """
    crc = 0xFFFF
    for byte in payload.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def build_payload(
    *, alias: str, amount: Decimal, currency: Currency, reference: str
) -> str:
    """حمولة الرمز نصّاً — ترسمها الواجهة مربعاً ولا تبنيها."""
    account = _tlv(SUBTAG_GUID, CLIQ_GUID) + _tlv(SUBTAG_ALIAS, alias)
    additional = _tlv(SUBTAG_REFERENCE_LABEL, reference)

    body = (
        _tlv(TAG_PAYLOAD_FORMAT, PAYLOAD_FORMAT_VERSION)
        + _tlv(TAG_INITIATION_METHOD, INITIATION_DYNAMIC)
        + _tlv(TAG_MERCHANT_ACCOUNT, account)
        + _tlv(TAG_MERCHANT_CATEGORY, MERCHANT_CATEGORY_CODE)
        + _tlv(TAG_CURRENCY, CURRENCY_NUMERIC[currency])
        + _tlv(TAG_AMOUNT, f"{amount:.3f}")
        + _tlv(TAG_COUNTRY, _country_of(currency))
        + _tlv(TAG_MERCHANT_NAME, MERCHANT_NAME)
        + _tlv(TAG_MERCHANT_CITY, MERCHANT_CITY)
        + _tlv(TAG_ADDITIONAL_DATA, additional)
    )
    # الحقل 63 يدخل حسابَ نفسه: المعرّف والطول ضمن المحسوب، والقيمة وحدها لا
    return body + TAG_CRC + "04" + crc16(f"{body}{TAG_CRC}04")


def _country_of(currency: Currency) -> str:
    """كليك أردنيٌّ بطبيعته؛ والحقل إلزامي في المعيار فيتبع عملة الرحلة."""
    return "JO" if currency == Currency.JOD else "LY"


def build_deep_link(
    *, alias: str, amount: Decimal, currency: Currency, reference: str
) -> str:
    return DEEP_LINK_TEMPLATE.format(
        alias=quote(alias, safe=""),
        amount=f"{amount:.3f}",
        currency=currency.value,
        reference=quote(reference, safe=""),
    )


def build_charge(
    *, alias: str, amount: Decimal, currency: Currency, reference: str
) -> CliqRideCharge:
    """كل ما تحتاجه شاشة الدفع في كائن واحد."""
    return CliqRideCharge(
        alias=alias,
        reference=reference,
        amount=amount,
        currency=currency,
        qr_payload=build_payload(
            alias=alias, amount=amount, currency=currency, reference=reference
        ),
        deep_link=build_deep_link(
            alias=alias, amount=amount, currency=currency, reference=reference
        ),
    )
