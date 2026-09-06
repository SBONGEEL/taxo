"""إعداداتُ الصفحة التعريفية — **بيتٌ واحدٌ للقراءة والكتابة**.

**والصفحةُ لا تقرّر شيئاً** (قاعدةُ `customer-app` نفسُها في `ARCHITECTURE.md`):
كلُّ نصٍّ ورابطٍ ومفتاحٍ تعرضه يأتي من هنا، **ولا قيمةَ قابلةٌ للتغيير مخبوزةٌ
في HTML**. وما يُبدَّل من اللوحة يصل الزائرَ بلا نشرٍ ولا بناء.

## والباب العام قائمةُ سماحٍ صريحة — لا استبعادٌ ضمنيّ

**`public_payload` يبني القاموسَ حقلاً حقلاً** ولا يُسلسل النموذج. **والفرقُ
ليس أسلوباً**: `model_dump()` ناقصاً حقولاً مستبعدةً **ينشر أيَّ عمودٍ يُضاف
غداً**، ومن يضيف عموداً لا يمرّ على قائمة الاستبعاد. **فالسماحُ يُكتب مرّةً،
والاستبعادُ يُنسى في كلِّ إضافة.**

## والعمولةُ والمفاتيحُ تُقرآن من مصدرهما ولا تُنسخان

**نسبةُ العمولة** من `commission_settings` عبر `settings_service` — **وهو
المصدرُ نفسُه الذي تقرؤه شاشةُ الإعدادات ويُجمَّد منه `commission_percent_at_ride`**.
**ومفاتيحُ الميزات** من `settings_service.get_flags` — **وهي التي يقرؤها
`GET /config`**. فلا مفتاحَ ثانٍ لمفهومٍ قائم، ولا رقمَ يُنسخ فيفترق.

## ولا رقمَ مالٍ يخرج من هنا غيرَ نسبة العمولة

**قرارُ المالك ٢٠٢٦-٠٩-٠٥**: «لا أرقام أسعار اشتراك ولا مبالغ عروض ولا مكافآت
في أي موضع؛ الرقم الوحيد المسموح نسبة العمولة من الباب العام». **فالعرضُ يخرج
اسماً بلا سعر** — `offer_name` و`offer_free` ولا `price` ولا `price_after`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CountryCode
from app.models.site import SiteSettings
from app.services import settings_service

#: **سوقُ الصفحة** — الأردنُ وحدَه بقرار المالك، ومنه تُقرأ العمولةُ والمفاتيح.
#:
#: **وثابتٌ مصرَّحٌ لا وسيطٌ من العميل**: الصفحةُ عامّةٌ بلا جلسة، ووسيطُ سوقٍ
#: من زائرٍ يجعل «كم العمولة؟» سؤالاً يجيبه السائلُ لنفسه.
SITE_COUNTRY = CountryCode.JO

#: **الوضعان، ولا ثالث** — والقائمةُ هنا هي التي يحرسها المخطَّط.
DISTRIBUTION_MODES = ("apk", "play")

#: **ما يُنشر على الباب العام** — قائمةُ سماحٍ صريحة، ولا حقلَ خارجها.
PUBLIC_FIELDS: tuple[str, ...] = (
    "hero_title",
    "hero_subtitle",
    "hero_note",
    "announce_enabled",
    "announce_text",
    "announce_url",
    "support_email",
    "privacy_email",
    "social_facebook",
    "social_instagram",
    "social_tiktok",
    "social_x",
    "social_whatsapp",
    "hidden_sections",
    "hidden_cards",
    "faq",
    "distribution_mode",
    "play_url_rider",
    "play_url_driver",
    "ios_url",
    "apk_page_enabled",
    "policies_public",
    "seo_description",
)

#: **معرِّفا الحزمتين** — من `channels.json`، وهما ما يبني منه المتجرُ عنوانَه.
#:
#: **ولا يُكتبان هنا بيدٍ ثانيةً**: مكتوبان في `channels.json` و`check-apk.mjs`،
#: **وثالثةٌ تفترق أوّلَ تغيير**. لكنّ الخلفيةَ لا تقرأ ملفَّ القنوات (فهو أداةُ
#: بناءٍ لا مصدرُ تشغيل)، **فيُصرَّحان هنا ومعهما من أين جاءا** — وهذا حدٌّ
#: مكتوبٌ لا مسكوتٌ عنه.
RIDER_PACKAGE = "ly.tajora.rider"
DRIVER_PACKAGE = "ly.tajora.driver"

#: **عنوانُ المتجر يُشتقّ ولا يُكتب** — والشكلُ هو شكلُ Google القياسيّ.
#:
#: **ولمَ افتراضٌ لا فراغ** (قرارُ المالك ٢٠٢٦-٠٩-٠٥): يومَ يُبدَّل الوضعُ إلى
#: `play` **يجد المشرفُ الرابطَ جاهزاً** بدل شارةٍ معطَّلةٍ يظنّها عطباً.
#: **ويقبل رابطَ اختبارٍ مغلقاً** لأنه على النطاق نفسِه — والمخطَّطُ يفحص
#: المضيفَ لا شكلَ المسار.
#:
#: **والحالُ تبقى `apk` حتى يبدّلها المالكُ بنفسه** — الرابطُ جاهزٌ والزرُّ لا
#: يظهر: **إعدادٌ محضَّرٌ ليس إعلاناً**.
def play_url(package: str) -> str:
    return f"https://play.google.com/store/apps/details?id={package}"


#: القيمُ الأولى — **تُكتب مرّةً عند أوّل قراءة، ولا تُعاد كتابتُها بعدها**.
DEFAULTS: dict[str, Any] = {
    "hero_title": "TAXO — تاكسي بالتطبيق للراكب والكبتن",
    "hero_subtitle": (
        "اطلب رحلتك أو اقبل الطلبات من التطبيق نفسه — وعمولةٌ منخفضةٌ تُجمَّد لحظةَ اشتراكك."
    ),
    "hero_note": "في الأردن الآن",
    "support_email": "support@tajora.ly",
    "privacy_email": "privacy@tajora.ly",
    "play_url_rider": play_url(RIDER_PACKAGE),
    "play_url_driver": play_url(DRIVER_PACKAGE),
    "seo_description": (
        "TAXO — تاكسي بالتطبيق للراكب والكبتن في الأردن. صفر عمولة على الكبتن "
        "المشترِك، خدمة نسائية، ومحفظة ودفع بأكثر من طريقة."
    ),
}


async def get_or_create(session: AsyncSession) -> SiteSettings:
    """صفُّ الإعدادات — يُنشأ بالقيم الأولى إن لم يوجد.

    **ولا يُنشأ صفٌّ ثانٍ ولو تسابق نداءان**: `singleton` فريدٌ في القاعدة،
    فالثاني يسقط بـ`IntegrityError` ولا يصير للجدول رأسان.
    """
    row = await session.scalar(select(SiteSettings).limit(1))
    if row is None:
        row = SiteSettings(**DEFAULTS)
        session.add(row)
        await session.flush()
    return row


async def read(session: AsyncSession) -> SiteSettings | None:
    """قراءةٌ محضة — **ولا تُنشئ صفّاً**.

    **يقرؤها البابُ العامُّ وحدَه**: مسارٌ يفتحه زائرٌ لا يجوز أن يكتب في
    القاعدة — وهي قاعدةُ `commission_percent_for` نفسُها بحرفها.
    """
    return await session.scalar(select(SiteSettings).limit(1))


def _default_payload() -> dict[str, Any]:
    """ما يُنشر حين لا صفَّ بعد — **قيمٌ أولى لا فراغ**.

    **وصفحةٌ بلا نصٍّ أسوأُ من صفحةٍ بنصٍّ أوّليّ**: تركيبٌ جديدٌ لم يُبذر بعد
    يعطي زائرَه صفحةً بيضاء، **والخطأُ يُقرأ عطباً في الموقع لا نقصاً في بذر**.
    """
    blank_text = {
        field: ""
        for field in PUBLIC_FIELDS
        if field
        not in {
            "announce_enabled",
            "hidden_sections",
            "hidden_cards",
            "faq",
            "distribution_mode",
            "apk_page_enabled",
            "policies_public",
        }
    }
    return {
        **blank_text,
        **{k: v for k, v in DEFAULTS.items() if k in PUBLIC_FIELDS},
        "announce_enabled": False,
        "hidden_sections": [],
        "hidden_cards": [],
        "faq": [],
        "distribution_mode": "apk",
        "apk_page_enabled": False,
        "policies_public": False,
    }


async def public_payload(session: AsyncSession) -> dict[str, Any]:
    """ما يخرج من `GET /public/site` — **بقائمة سماحٍ ولا شيءَ خارجها**.

    **ويُقرأ معه ما لا يسكن هنا**: نسبةُ العمولة من إعداد العمولة، ومفاتيحُ
    الميزات من مصدر `GET /config`. **قراءةٌ لا نسخة**، فلا رقمَ يفترق ولا
    مفتاحَ ثانٍ لمفهومٍ واحد.
    """
    row = await read(session)
    if row is None:
        payload = _default_payload()
    else:
        payload = {field: getattr(row, field) for field in PUBLIC_FIELDS}

    commission: Decimal = await settings_service.commission_percent_for(
        session, SITE_COUNTRY
    )
    flags = await settings_service.get_flags(session, SITE_COUNTRY)

    # **النسبةُ نصٌّ لا عائم** — قاعدةُ `NUMERIC(12,3)` في هذا المستودع:
    # **الرقمُ لا يمرّ بعائمٍ في أيِّ طريق**، ولو كان نسبةً لا مبلغاً.
    payload["commission_percent"] = str(commission)
    # **الأثرُ قبل النسبة** (قرارُ المالك ٢٠٢٦-٠٩-٠٦): «بِع الفرقَ لا الرقم».
    #
    # **ويُحسب هنا لا في الصفحة**: `100 − النسبة` حسابُ مالٍ، **و§14 يحصره في
    # الخلفية** — ويمنعه `check:money-math` في الواجهة أصلاً. **ومن المصدر
    # نفسِه الذي تخرج منه النسبة**، فلا يفترق الرقمان أبداً مهما بُدّلت.
    payload["driver_keeps_per_100"] = str(
        (Decimal("100") - commission).quantize(Decimal("0.01")).normalize()
    )
    payload["features"] = flags
    return payload
