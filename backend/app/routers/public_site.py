"""ما تقرؤه الصفحةُ التعريفيةُ العامة — **قراءةٌ محضة، بلا جلسةٍ وبلا كتابة**.

**ولا مسارَ هنا يكتب حرفاً** (شرطُ المالك 2026-08-21): لا تسجيل، ولا جمعَ
بيانات، ولا أثرَ في القاعدة. **وصارا `GET`ين اثنين منذ البند ٨** — والشرطُ هو
هو: قراءتان محضتان.

**والثاني `app-version`، وموضعُه هنا بعلّته**: يُسأل **قبل الدخول** — ومن
حزمتُه أقدمُ من الحدِّ **لا يُفتح له بابٌ يسجّل به دخولاً أصلاً**، فبابٌ
يحرسه `CurrentUser` كان يجعل شاشةَ التحديث الإلزاميّ مستحيلةً على من تخصّه.
**ولا يقرأ شيئاً عن شخص**: تطبيقٌ ورقمُ حزمة.

**ولماذا بابٌ عامٌّ للعرض أصلاً**: الصفحةُ تعِد الكبتنَ بـ«الشهر الأول مجاناً»،
**والوعدُ يُقرأ من العرض القائم لا يُكتب نصّاً** — فعرضٌ أُطفئ أو نفد سقفُه
**يختفي سطرُه من نفسه**. وهي قاعدةُ ورقة الترحيب بعينها: **ورقةٌ تعِد بما نفد
أسوأُ من ورقةٍ صامتة**.

**وما يُنشر هنا عرضٌ عامٌّ لا عرضُ شخص**: `audience` من `all` أو `new_driver`
وحدَهما — أي ما ينطبق على **من لا حسابَ له بعد**. وعرضُ `lapsed` أو `manual`
يخصّ كبتناً بعينه، ونشرُه على صفحةٍ عامة يَعِد من لا يستحقّه (الفرعُ و من
البند ٥٤).

**ولا يُنشر سقفُه ولا ميزانيتُه**: «بقي ٣ مقاعد» رقمٌ يُستعمل ضغطاً، ونحن لا
نعرف إن كان صادقاً لحظةَ القراءة.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import DbSession
from app.models.enums import (
    ClientApp,
    CountryCode,
    FeatureKey,
    PolicyApp,
    PolicyDocType,
)
from app.models.subscription_offer import (
    AUDIENCE_ALL,
    AUDIENCE_NEW_DRIVER,
    SubscriptionOffer,
)
from app.models.subscription import SubscriptionPlan
from app.schemas.app_release import AppVersionOut
from app.schemas.public_site import (
    RequiredPolicyOut,
    LandingOfferOut,
    LandingOut,
    PublicPolicyOut,
    SiteOut,
)
from app.services import (
    policies as policies_service,
    pricing,
    releases as releases_service,
    settings_service,
    site as site_service,
)

router = APIRouter(prefix="/public", tags=["public"])

#: الجمهورُ الذي يصحّ نشرُه لمن لا حسابَ له.
PUBLIC_AUDIENCES = (AUDIENCE_ALL, AUDIENCE_NEW_DRIVER)


@router.get("/landing", response_model=LandingOut)
async def landing(
    session: DbSession, country_code: CountryCode = CountryCode.JO
) -> LandingOut:
    """أفضلُ عرضٍ عامٍّ قائمٍ الآن — أو لا شيء."""
    if not await settings_service.is_feature_enabled(
        session, country_code, FeatureKey.SUBSCRIPTION_OFFERS_ENABLED
    ):
        return LandingOut(offer=None)

    now = datetime.now(UTC)
    offers = (
        await session.execute(
            select(SubscriptionOffer).where(
                SubscriptionOffer.country_code == country_code,
                SubscriptionOffer.is_active.is_(True),
                SubscriptionOffer.audience.in_(PUBLIC_AUDIENCES),
                (SubscriptionOffer.starts_at.is_(None))
                | (SubscriptionOffer.starts_at <= now),
                (SubscriptionOffer.ends_at.is_(None))
                | (SubscriptionOffer.ends_at > now),
            )
        )
    ).scalars().all()
    if not offers:
        return LandingOut(offer=None)

    plans = (
        await session.execute(
            select(SubscriptionPlan).where(
                SubscriptionPlan.country_code == country_code,
                SubscriptionPlan.is_active.is_(True),
            )
        )
    ).scalars().all()
    if not plans:
        return LandingOut(offer=None)

    # **أكبرُ توفيرٍ لا أوّلُ خطة** — الصفحةُ تُقرأ في ثوانٍ، والرقمُ الذي يجذب
    # هو الأكبر. وهي قاعدةُ `pickWelcomeOffer` نفسُها، مطبَّقةً على من لا
    # حسابَ له
    best: LandingOfferOut | None = None
    best_saving = Decimal("-1")
    for offer in offers:
        for plan in plans:
            if offer.plan_id is not None and offer.plan_id != plan.id:
                continue
            cut = pricing.round_money(plan.price * offer.discount_value / 100)
            if offer.max_discount is not None:
                cut = min(cut, offer.max_discount)
            after = pricing.round_money(max(Decimal("0.000"), plan.price - cut))
            saving = plan.price - after
            if saving > best_saving:
                best_saving = saving
                # **الحسابُ داخلٌ والرقمُ لا يخرج** (قرارُ المالك ٢٠٢٦-٠٩-٠٥):
                # `after` و`plan.price` يقرّران **أيَّ عرضٍ يُنشر**، ثمّ يبقيان
                # هنا. **ولا سعرَ ولا سعرَ مشطوبٍ يغادر هذا الباب** — والصفحةُ
                # تكتب اسمَ العرض كما كتبه المشرف.
                best = LandingOfferOut(
                    name=offer.name,
                    plan_name=plan.name,
                    free=after == 0,
                )
    return LandingOut(offer=best if best_saving > 0 else None)


@router.get("/app-version", response_model=AppVersionOut)
async def app_version(
    session: DbSession,
    app: ClientApp,
    build: int | None = None,
) -> AppVersionOut:
    """ماذا يفعل التطبيقُ عند الإقلاع — **البند ٨ (§39٫٨، §43)**.

    **والحكمُ يخرج محسوباً لا رقمين يقارنهما العميل**: ثلاثةُ تطبيقاتٍ تكتب
    المقارنةَ بأنفسها **ثلاثُ نسخٍ من قاعدةٍ واحدة**، تفترق أوّلَ ما تتغيّر
    ولا شيءَ يفشل. وهي §14 مطبَّقةً على حكمٍ لا على مبلغ.

    **و`build` اختياريةٌ بقصد**: من لا يعرف رقمَ حزمته — متصفّحٌ، أو غلافٌ لا
    يجيب ملحقُه — **لا يُقفل بالظنّ**. والقفلُ عقوبةٌ على قِدَمٍ مثبَت.

    **وبلا سجلٍّ لهذا التطبيق: `ok` بحقولٍ فارغة** — لا «كلُّ النسخ مرفوضة».
    **فغيابُ السجلِّ يعطّل الحجبَ لا التطبيق.**
    """
    verdict = await releases_service.verdict_for(session, app=app, build=build)
    return AppVersionOut(
        state=verdict.state,
        latest_build=verdict.latest_build,
        min_supported_build=verdict.min_supported_build,
        download_url=verdict.download_url,
        release_notes=verdict.release_notes,
        reminder_hours=verdict.reminder_hours,
    )


@router.get("/site", response_model=SiteOut)
async def site(session: DbSession) -> SiteOut:
    """ما تعرضه الصفحةُ التعريفية — **قراءةٌ محضةٌ بقائمة سماح** (§52).

    **وثالثُ `GET` في هذا الملفّ، والشرطُ هو هو**: بلا جلسة، وبلا كتابة، وبلا
    حقلٍ يخصّ شخصاً. **ولا يُنشئ صفّاً**: مسارٌ يفتحه زائرٌ لا يكتب في القاعدة
    — وهي قاعدةُ `commission_percent_for` بحرفها.

    **والحقولُ من `services/site.PUBLIC_FIELDS` لا من تسلسلِ النموذج**: عمودٌ
    يُضاف إلى الجدول **لا يظهر هنا حتى يُذكر في القائمة**. والاستبعادُ الضمنيُّ
    هو ما يُنسى، والسماحُ الصريحُ يُكتب مرّة.

    **ومعه ما يُقرأ من مصدره**: نسبةُ العمولة من `commission_settings`،
    والمفاتيحُ من مصدر `GET /config` — **قراءةٌ لا نسخة**.
    """
    payload = await site_service.public_payload(session)
    return SiteOut(**payload)


@router.get("/policy", response_model=PublicPolicyOut | None)
async def policy(
    session: DbSession,
    doc_type: PolicyDocType,
    app: PolicyApp = PolicyApp.RIDER,
) -> PublicPolicyOut | None:
    """وثيقةٌ للويب — **أو `None`، وهي حالٌ صحيحةٌ لا خطأ**.

    **والمنعُ هنا لا في الصفحة**: حارسٌ في الواجهة وحدَها يُتجاوَز بـ`curl`،
    **فالنصُّ لا يغادر الخلفيةَ ما لم يخضرَّ المفتاحان**.

    **وأيُّ تطبيقٍ نصُّه؟ يُسأل، وافتراضُه الراكب** (وُسّع ٢٠٢٦-٠٩-٠٧ بأمر
    المالك): كان يخدم `RIDER` **دائماً** بعلّةٍ صحيحةٍ في موضعها — «الموقعُ
    يخاطب الجمهورَ العامّ». **والعلّةُ سقطت حين صار الرابطُ رابطَ متجر**:
    Google Play **يقرن رابطَ السياسة بالتطبيق**، فرابطُ تطبيق الكبتن يجب أن
    يعرض نصَّ الكبتن — **ووثيقةٌ أوسعُ ليست وثيقتَه**.

    **ولا نسخةَ ثالثةٌ تُخترع**: النصّان قائمان في الجدول أصلاً، **وهذا اختيارٌ
    بينهما لا تأليفُ ثالث**. والافتراضُ يبقى الراكبَ **فلا يتغيّر نداءٌ قائم**.

    **والمُعامِلُ لا يمنح شيئاً**: المفتاحان اللذان يحرسان النصَّ يُقرآن قبله
    كما كانا — `policies_public` ثمّ `is_published`.
    """
    row = await site_service.read(session)
    if row is None or not row.policies_public:
        return None

    doc = await policies_service.published(
        session,
        country=site_service.SITE_COUNTRY,
        doc_type=doc_type,
        app=app,
    )
    if doc is None:
        return None
    return PublicPolicyOut(
        doc_type=doc.doc_type.value,
        # **من الصفِّ لا من الطلب**: لو رُدَّ ما سُئل عنه لَشهد الحقلُ لنفسه.
        app=doc.app.value,
        version=doc.version,
        body_ar=doc.body_ar,
        published_at=doc.published_at,
    )


@router.get("/policies/required", response_model=list[RequiredPolicyOut])
async def required_policies(
    session: DbSession, country_code: CountryCode, app: PolicyApp
) -> list[RequiredPolicyOut]:
    """**ما يلزم قبولُه قبل إنشاء حساب** في هذا التطبيق وهذا السوق.

    **وبلا مصادقة بقصد**: يُقرأ **قبل** أن يوجد حساب. والنصُّ منشورٌ للناس
    أصلاً، **فلا سرَّ فيه يُحرَس بتوكن**.

    **ولا يمرّ بمفتاح `policies_public`** خلافاً لـ`GET /public/policy`:
    **ذاك مفتاحُ الموقع** — «أتُعرض الوثيقةُ على `taxo.tajora.ly`؟» —
    **وهذا سؤالُ التطبيق**: «ما الذي يوافق عليه من يسجّل؟». **وربطُهما بمفتاحٍ
    واحدٍ يجعل إخفاءَ صفحةٍ على الويب يُسقط بوّابةَ القبول في التطبيقين**،
    وهو أثرٌ لا يقصده من يطفئ مفتاحَ موقع.

    **وقائمةٌ فارغةٌ حالٌ صحيحة** — سوقٌ بلا وثيقةٍ منشورة.
    """
    docs = await policies_service.required_for(session, country=country_code, app=app)
    return [
        RequiredPolicyOut(
            id=doc.id,
            doc_type=doc.doc_type.value,
            app=doc.app.value,
            version=doc.version,
            body_ar=doc.body_ar,
            published_at=doc.published_at,
        )
        for doc in docs
    ]
