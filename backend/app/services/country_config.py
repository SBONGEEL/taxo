"""بناءُ وصفِ الدولة — **بانٍ واحدٌ لبابين** (الشكلُ الثامن).

`GET /config` و`GET /admin/countries` ينشران الوصفَ نفسَه: الأولُ **مصفّىً**
للتطبيقات، والثاني **كاملاً** للوحة. ولو بنى كلٌّ منهما وصفَه لصار حقلٌ يُملأ في
أحدهما ويُنسى في الآخر — وهو بعينه ما وقع في عروض الاشتراكات، وكلُّ اختبارٍ
أخضرُ لأن كلَّ بابٍ كان صادقاً عن نفسه.

**والظهورُ ليس حقلاً في الوصف**: هو صفةُ سوقٍ تقرؤها اللوحةُ وتصفّي بها الخلفيةُ
`/config` — والتطبيقُ لا يحتاج أن يعرف عن دولةٍ لا يراها شيئاً.
"""

from __future__ import annotations

from app.core.currency import COUNTRY_NAME, CURRENCY_LABEL, CURRENCY_NAME, currency_for_country, decimals_of
from app.core.i18n import translate
from app.core.phone import dial_code_for, national_length_for
from app.models.enums import CountryCode, FeatureKey
from app.schemas.config import CountryConfigOut
from app.services import campaigns, categories, markets, otp, settings_service, verification


def _area(country: CountryCode) -> list[float]:
    from app.core import service_area

    box = service_area.box_for(country)
    return [box.min_lat, box.max_lat, box.min_lng, box.max_lng]


async def build(session, country: CountryCode) -> CountryConfigOut:
    """إعدادات دولةٍ كما تراها الواجهات — قراءةٌ خالصة بلا إنشاء صفوف."""
    quiet = await campaigns.get_settings(session, country)
    # **يُقرأ من الإعداد لا من نصّ** — والقناةُ تُخفى حين لا يُضبط
    pay = await settings_service.get_payment_settings(session, country)
    # **قاعدةُ التقريب من بيتها الواحد** (`rounding.policy_of`) — مطفأةٌ لسوقٍ بلا صفّ
    from app.services import rounding

    policy = rounding.policy_of(pay)
    channels = await verification.available_methods(session, country)
    # **فئاتُ الرحلة المطلوبة الآن** (SPEC §٦٧) — المدمجتان بوجهيهما الافتراضيّين ما لم يُبذر لهما صفّ
    keys = await categories.requestable_keys(session, country)
    rows = {row.key: row for row in await categories.for_country(session, country)}
    method = channels[0] if channels else verification.NONE
    currency = currency_for_country(country)
    return CountryConfigOut(
        country_code=country,
        # **بلغة الطلب** — اللوحةُ ترسل `ar` صراحةً، والتطبيقان لغتَهما (§٧٣-هـ/٥)
        name=translate(COUNTRY_NAME[country]),
        status=await markets.status_of(session, country),
        signup=await markets.signup_state(session, country),
        area=_area(country),
        currency=currency,
        # **بلغة الطلب** (§٧٦-ع/٢) — «DA» في الواجهة الفرنسيّة لا «د.ج»
        currency_label=translate(CURRENCY_LABEL[currency]),
        currency_name=translate(CURRENCY_NAME[currency]),
        currency_decimals=decimals_of(currency),
        features=await settings_service.get_flags(session, country),
        vehicle_categories=keys,
        ride_categories=[categories.public_face(key, rows.get(key)) for key in keys],
        dial_code=dial_code_for(country),
        national_number_length=national_length_for(country),
        quiet_hours_start=(
            quiet.quiet_hours_start.strftime("%H:%M") if quiet else None
        ),
        quiet_hours_end=quiet.quiet_hours_end.strftime("%H:%M") if quiet else None,
        quiet_hours_timezone=quiet.timezone if quiet else None,
        cliq_alias=(pay.cliq_alias or None) if pay else None,
        verification=method,
        verification_channels=list(channels),
        otp_length=(
            otp.CODE_LENGTH if method in verification.CODE_CHANNELS else None
        ),
        # **بانٍ واحدٌ لبابين** — فاللوحةُ ترى ما يراه التطبيق، ولا يُملأ حقلٌ
        # في أحدهما ويُنسى في الآخر (الشكلُ الثامن)
        email_signup=await verification.email_signup_available(session, country),
        rounding_enabled=policy.enabled,
        # **الوحدةُ والاتجاهُ المضبوطان ولو كان مطفأً** — اللوحةُ تقرأ الوصفَ نفسَه، والتطبيقُ لا يقرؤهما إلا مشتعلاً
        rounding_unit=pay.rounding_unit if pay is not None else policy.unit,
        rounding_mode=pay.rounding_mode if pay is not None else policy.mode,
    )


async def is_visible(session, country: CountryCode) -> bool:
    """هل تُنشر هذه الدولةُ للتطبيقات؟

    **والسكوتُ ظهور** (`DEFAULT_ENABLED_FLAGS`): الإخفاءُ صفٌّ صريحٌ يكتبه
    إنسان، وإلا اختفت كلُّ دولةٍ على تثبيتٍ لم يُبذر.
    """
    return await settings_service.is_feature_enabled(
        session, country, FeatureKey.COUNTRY_VISIBLE
    )


async def visible_countries(session) -> list[CountryCode]:
    return [c for c in CountryCode if await is_visible(session, c)]
