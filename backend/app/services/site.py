"""إعداداتُ الصفحة التعريفية — **بيتٌ واحدٌ للقراءة والكتابة**.

**والصفحةُ لا تقرّر شيئاً** (قاعدةُ `customer-app` نفسُها في `ARCHITECTURE.md`):
كلُّ نصٍّ ورابطٍ ومفتاحٍ تعرضه يأتي من هنا، **ولا قيمةَ قابلةٌ للتغيير مخبوزةٌ
في HTML**. وما يُبدَّل من اللوحة يصل الزائرَ بلا نشرٍ ولا بناء.

## والباب العام قائمةُ سماحٍ صريحة — لا استبعادٌ ضمنيّ

**`public_payload` يبني القاموسَ حقلاً حقلاً** ولا يُسلسل النموذج. **والفرقُ
ليس أسلوباً**: `model_dump()` ناقصاً حقولاً مستبعدةً **ينشر أيَّ عمودٍ يُضاف
غداً**، ومن يضيف عموداً لا يمرّ على قائمة الاستبعاد. **فالسماحُ يُكتب مرّةً،
والاستبعادُ يُنسى في كلِّ إضافة.**

## والمفاتيحُ تُقرأ من مصدرها ولا تُنسخ

**مفاتيحُ الميزات** من `settings_service.get_flags` — **وهي التي يقرؤها
`GET /config`**. فلا مفتاحَ ثانٍ لمفهومٍ قائم.

## ولا رقمَ مالٍ يخرج من هنا — **ولا نسبةُ العمولة** (§٦٩-ب، ٢٠٢٦-١٠-٠٩)

**قرارُ المالك ٢٠٢٦-٠٩-٠٥**: «لا أرقام أسعار اشتراك ولا مبالغ عروض ولا مكافآت
في أي موضع». **فالعرضُ يخرج اسماً بلا سعر** — `offer_name` و`offer_free` ولا
`price` ولا `price_after`.

**وكانت نسبةُ العمولة «الرقمَ الوحيدَ المسموح»، ومعها `driver_keeps_per_100`
محسوباً منها** — حتى قرّر المالكُ مع الموقع الجديد: «لا نسبةَ عمولةٍ رقماً في
أيِّ موضع» (§٦٩-أ/٣). **فنُزعت من الباب نفسِه لا من الرسم وحدَه** (قاعدةُ
§٥٢٫٣ في النزع): صفحةٌ لا ترسم رقماً يصلها **تبقى تحمله في حمولتها** ويقرؤه من
يفتح أدوات المطوّر. **والنسبةُ باقيةٌ في مصدرها** (`commission_settings`)، وشاشةُ
«الموقع» في اللوحة تقرؤها من هناك لا من هنا (`routers/admin_site.py`).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CountryCode
from app.models.site import NEW_CARDS_DEFAULT, SiteSettings
from app.services import settings_service

#: **سوقُ الصفحة** — الأردنُ وحدَه بقرار المالك، ومنه تُقرأ المفاتيح.
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
    "new_cards",
    "faq",
    "faq_enabled",
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
        "TAXO — تاكسي بالتطبيق للراكب والكبتن في الأردن. اشتراكٌ للكبتن بنسبةٍ "
        "تُجمَّد ما دام سارياً، خدمة نسائية، ومحفظة ودفع بأكثر من طريقة."
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
            "new_cards",
            "faq",
            "faq_enabled",
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
        "new_cards": list(NEW_CARDS_DEFAULT),
        "faq": [],
        "faq_enabled": False,
        "distribution_mode": "apk",
        "apk_page_enabled": False,
        "policies_public": False,
    }


async def public_payload(session: AsyncSession) -> dict[str, Any]:
    """ما يخرج من `GET /public/site` — **بقائمة سماحٍ ولا شيءَ خارجها**.

    **ويُقرأ معه ما لا يسكن هنا**: مفاتيحُ الميزات من مصدر `GET /config` —
    **قراءةٌ لا نسخة**، فلا مفتاحَ ثانٍ لمفهومٍ واحد.

    **ولا نسبةَ عمولةٍ ولا ما يُشتقّ منها** (§٦٩-ب): كانا هنا —
    `commission_percent` و`driver_keeps_per_100` — **ونُزعا من الباب نفسِه**،
    و`check:site` (١٣) يمنع عودتَهما إلى هذا الملفّ بالاسم.
    """
    row = await read(session)
    if row is None:
        payload = _default_payload()
    else:
        payload = {field: getattr(row, field) for field in PUBLIC_FIELDS}
    # **الأسئلةُ لا تُنشر ما دام قسمُها مطفأً** (§٧١-ج/٩): نصٌّ يُراجع في اللوحة لا يصل حمولةَ زائرٍ قبل أن يُشعَل
    if not payload["faq_enabled"]:
        payload["faq"] = []

    payload["features"] = await settings_service.get_flags(session, SITE_COUNTRY)
    return payload


async def commission_for_panel(session: AsyncSession) -> str:
    """**نسبةُ العمولة السارية لشاشة «الموقع» في اللوحة** — من مصدرها لا من الباب العامّ.

    **تُعرض للمشرف ولا تُنشر** (§٦٩-ب): شاشةُ الموقع تقول له أيَّ نسبةٍ تسري
    وأنّ بيتَها شاشةُ الإعدادات، **والصفحةُ العامّةُ لا تحملها**. **ونصٌّ لا
    عائم** — قاعدةُ `NUMERIC(12,3)` في هذا المستودع: الرقمُ لا يمرّ بعائمٍ في
    أيِّ طريق، ولو كان نسبةً لا مبلغاً.
    """
    return str(await settings_service.commission_percent_for(session, SITE_COUNTRY))
