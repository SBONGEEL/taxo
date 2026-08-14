from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import FeatureKey, ProviderKey


@dataclass(frozen=True, slots=True)
class ProviderField:
    """حقل واحد في عقد مزود.

    `secret=True` يعني أنه لا يخرج من الخلفية أبداً: يُقنّع في اللوحة
    (`****`) ولا يظهر في `GET /config`.
    `expose_to_clients=True` يعني أنه عام بطبيعته (مثل Mapbox pk) وتسلّمه
    الخلفية للواجهات عبر `GET /config`.
    """

    key: str
    label: str
    secret: bool = True
    required: bool = True
    # **نوعُ الحقل — أُضيف 2026-08-14 بعد عطبٍ كلّف تشخيصاً كاملاً.**
    # كانت البطاقةُ تصف الحقولَ بلا نوع، فترسم اللوحةُ **كلَّ حقلٍ صندوقَ نصّ**
    # — بما فيها مفاتيحُ التشغيل. فمن كتب «false» أرسل النصَّ `"false"`،
    # و`bool("false")` في بايثون **صادق**: أيُّ نصٍّ غيرِ فارغ صادق. فكان
    # مفتاحُ «مزوّد وهمي» **يُشعَل حين يُطفأ** في سبعة عقود، ومعه `test_mode`
    # في بوابة البطاقة — أي ثمانيةُ مواضعَ من شكلٍ واحد.
    kind: str = "text"
    expose_to_clients: bool = False


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    key: ProviderKey
    label: str
    fields: tuple[ProviderField, ...]
    # الميزة التي تُفعَّل تلقائياً لدولة العقد عند تفعيله (SPEC القسم 4)
    feature_key: FeatureKey | None = None
    # هل العقد لكل دولة على حدة أم عقد عام واحد؟
    per_country: bool = False

    def field(self, key: str) -> ProviderField | None:
        return next((f for f in self.fields if f.key == key), None)

    @property
    def secret_field_keys(self) -> frozenset[str]:
        return frozenset(f.key for f in self.fields if f.secret)


# حقلٌ واحد بنفس المعنى في كل عقدٍ له مزودٌ وهمي (SPEC القسم 15/أ): تُبنى
# الميزة كاملةً الآن وتُجرَّب بلا حسابٍ ولا شبكة، ويُتجاهل الحقل في الإنتاج —
# مزودٌ يقول «تم» بلا أن يفعل بابٌ لا يُترك مفتوحاً حيث مالٌ أو دخولٌ حقيقي.
MOCK_FIELD = ProviderField(
    key="use_mock",
    label="مزود وهمي (تطوير واختبار فقط)",
    secret=False,
    required=False,
    kind="toggle",
)


PROVIDERS: dict[ProviderKey, ProviderSpec] = {
    ProviderKey.MAPBOX: ProviderSpec(
        key=ProviderKey.MAPBOX,
        label="Mapbox — الخرائط والمسارات",
        fields=(
            ProviderField(
                key="public_token",
                label="التوكن العام (pk)",
                secret=False,
                expose_to_clients=True,
            ),
            ProviderField(key="secret_token", label="التوكن السري (sk)"),
        ),
    ),
    ProviderKey.TELR: ProviderSpec(
        key=ProviderKey.TELR,
        label="Telr — الدفع بالبطاقة",
        fields=(
            ProviderField(key="store_id", label="معرّف المتجر"),
            ProviderField(key="auth_key", label="مفتاح المصادقة"),
            ProviderField(
                kind="toggle",
                key="test_mode",
                label="وضع Sandbox",
                secret=False,
                required=False,
            ),
            # مزودٌ وهمي بلا شبكة ولا حساب (SPEC القسم 15): يُشغّل مسار البطاقة
            # كاملاً للتجربة والاختبار قبل وصول بيانات Sandbox. يُتجاهل في
            # الإنتاج — انظر `services/card_gateway/__init__.py`.
            MOCK_FIELD,
        ),
        feature_key=FeatureKey.CARD_ENABLED,
        per_country=True,
    ),
    ProviderKey.SMS: ProviderSpec(
        key=ProviderKey.SMS,
        label="مزود الرسائل القصيرة",
        # تفعيل هذا العقد يحوّل الدخول إلى OTP آلياً — لا feature flag له،
        # القرار في services/auth/sms_provider_enabled.
        fields=(
            ProviderField(key="provider_name", label="اسم المزود", secret=False),
            ProviderField(key="api_key", label="مفتاح الـ API"),
            ProviderField(key="sender_id", label="اسم المُرسل", secret=False),
            # عنوان الإرسال — غير مطلوب مع المزود الوهمي، ومطلوب بغيره
            ProviderField(
                key="endpoint", label="عنوان الإرسال", secret=False, required=False
            ),
            MOCK_FIELD,
        ),
    ),
    ProviderKey.WHATSAPP: ProviderSpec(
        key=ProviderKey.WHATSAPP,
        label="WhatsApp — التحقق من الهاتف (OTP)",
        # **ولا `feature_key` هنا عمداً** خلافاً لعقود البطاقة وكليك: المزامنةُ
        # التلقائية تُشعل مفتاحَ **دولة العقد** عند تفعيله، وهذا عقدٌ عامٌّ لا
        # دولةَ له — فمزامنتُه ستُشعل مفتاحاً بلا سوقٍ محدد. والمالكُ طلب أن يبقى
        # المفتاح `whatsapp_otp_enabled` بيده: مطفأً حتى يُشعله لكل سوقٍ بضغطة
        # زر في شاشة الإعدادات. فالعقدُ يقول «نستطيع» والمفتاحُ يقول «نفعل هنا».
        #
        # **والواجهة رسميةٌ من ميتا حصراً** (WhatsApp Cloud API على Graph):
        # لا مكتبةَ واتساب غير رسمية في هذا المشروع — أتمتةُ حسابٍ شخصي مخالفةٌ
        # لشروط واتساب وعقوبتُها حظرُ الرقم، أي توقّفُ تسجيل المستخدمين كلهم بلا
        # إنذارٍ ومن رقمٍ لا يُسترجَع.
        fields=(
            ProviderField(
                key="phone_number_id",
                label="معرّف رقم الأعمال (Phone Number ID)",
                secret=False,
            ),
            # سرٌّ حقيقي: من يملكه يرسل بصفتنا إلى كل من كلّمنا
            ProviderField(key="access_token", label="رمز الوصول (Access Token)"),
            ProviderField(
                key="template_name",
                label="اسم قالب المصادقة",
                secret=False,
            ),
            ProviderField(
                key="template_language",
                label="لغة القالب (رمز مثل ar)",
                secret=False,
                required=False,
            ),
            # اختياريٌّ للإرسال، **ولازمٌ لاختبار القالب**: بغيره يتحقق زرُّ
            # الاختبار من الرقم والتوكن ولا يعرف إن كان اسمُ القالب صحيحاً —
            # وهو أكثرُ ما يُخطئ فيه الإعداد
            ProviderField(
                key="waba_id",
                label="معرّف حساب الأعمال (WABA ID)",
                secret=False,
                required=False,
            ),
            MOCK_FIELD,
        ),
    ),
    ProviderKey.FIREBASE_AUTH: ProviderSpec(
        key=ProviderKey.FIREBASE_AUTH,
        label="Firebase — التحقق من الهاتف (OTP)",
        # تفعيل هذا العقد يجعل الدخول برمز Firebase — لا feature flag له،
        # القرار في `services/auth.get_auth_strategy` وحدها.
        #
        # **عقدٌ مستقل عن `fcm` وإن كان المشروع واحداً**، لسببين: التحقق من
        # رمز الهوية لا يحتاج مفتاح حساب الخدمة أصلاً (يكفيه `project_id`
        # ومفاتيح Google العامة)، فلا داعي لأن يحمل عقدُ الدخول سرّاً لا
        # يستعمله؛ وإطفاءُ الإشعارات قرارٌ لا يجوز أن يُطفئ الدخول معه —
        # وعقدٌ واحد يجعلهما مفتاحاً واحداً.
        # **الحقول الأربعة العامة هي «إعداد تطبيق الويب»** الذي تحتاجه حزمة
        # Firebase على الجهاز لتشغيل تدفّق التحقق (المرحلة 9). كلها تُنشر في
        # حزمة أي تطبيق ويب يستعمل Firebase — عامّةٌ بطبيعتها كتوكن Mapbox
        # العام — لكنها قيمُ مشروعٍ بعينه، فمكانها العقدُ لا ملفُّ إعداداتٍ في
        # الواجهة (SPEC القسم 14: لا مفاتيح مزودين خارج هذا الجدول).
        # وغيابُها لا يعطّل شيئاً في الخلفية: التحقق من رمز الهوية يكفيه
        # `project_id` ومفاتيح Google العامة، فتبقى الثلاثة الأخرى اختيارية
        # لعقدٍ لا واجهةَ ويب له.
        fields=(
            ProviderField(
                key="project_id",
                label="معرّف مشروع Firebase",
                secret=False,
                # يُنشر للواجهات: تطبيقُ العميل يحتاجه ليتحقق من الرقم أصلاً،
                # وهو معرِّفٌ عام كتوكن Mapbox العام
                expose_to_clients=True,
            ),
            ProviderField(
                key="api_key",
                label="مفتاح الويب العام (apiKey)",
                secret=False,
                required=False,
                expose_to_clients=True,
            ),
            ProviderField(
                key="auth_domain",
                label="نطاق التحقق (authDomain)",
                secret=False,
                required=False,
                expose_to_clients=True,
            ),
            ProviderField(
                key="app_id",
                label="معرّف تطبيق الويب (appId)",
                secret=False,
                required=False,
                expose_to_clients=True,
            ),
            MOCK_FIELD,
        ),
    ),
    ProviderKey.CLIQ_ACQUIRER: ProviderSpec(
        key=ProviderKey.CLIQ_ACQUIRER,
        label="CliQ — التكامل الآلي (شحن المحفظة)",
        fields=(
            ProviderField(key="merchant_id", label="معرّف التاجر"),
            ProviderField(key="api_key", label="مفتاح الـ API"),
            ProviderField(
                key="endpoint", label="عنوان الخدمة", secret=False, required=False
            ),
            # alias الشركة الذي يُحوَّل عليه (SPEC القسم 7) — يظهر في رمز الـ QR
            # ولصاحب الحوالة، فهو عامٌّ بطبيعته لا سرّ
            ProviderField(
                key="company_alias",
                label="alias الشركة",
                secret=False,
                required=False,
            ),
            MOCK_FIELD,
        ),
        feature_key=FeatureKey.CLIQ_ENABLED,
        per_country=True,
    ),
    ProviderKey.FCM: ProviderSpec(
        key=ProviderKey.FCM,
        label="FCM — الإشعارات",
        # **الحقول العامة الأربعة تكرارٌ مقصود لما في عقد `firebase_auth`**،
        # وهو ثمنُ استقلال العقدين الذي يقرره القسم 15/أ: إطفاءُ الإشعارات لا
        # يجوز أن يُطفئ الدخول، فلا يقرأ أحدهما حقولَ الآخر. والحالة التي
        # تجعل التكرار ضرورةً لا زينة: مُحقِّقٌ عبر مزود SMS تقليدي وإشعاراتٌ
        # عبر FCM — عقد الدخول حينها مطفأٌ تماماً والتطبيق ما زال يحتاج إعداد
        # تطبيق الويب ليطلب رمز جهاز (المرحلة 9). والقيم عامّةٌ بطبيعتها:
        # تُنشر في حزمة كل تطبيق ويب يستقبل إشعارات.
        fields=(
            ProviderField(
                key="project_id",
                label="معرّف المشروع",
                secret=False,
                expose_to_clients=True,
            ),
            ProviderField(
                key="api_key",
                label="مفتاح الويب العام (apiKey)",
                secret=False,
                required=False,
                expose_to_clients=True,
            ),
            ProviderField(
                key="app_id",
                label="معرّف تطبيق الويب (appId)",
                secret=False,
                required=False,
                expose_to_clients=True,
            ),
            ProviderField(
                key="sender_id",
                label="معرّف المُرسل (messagingSenderId)",
                secret=False,
                required=False,
                expose_to_clients=True,
            ),
            # مفتاح Web Push العام (VAPID): بغيره لا يصدر المتصفح رمز جهاز
            # أصلاً. عامٌّ بطبيعته — الخاصُّ منه يبقى عند Google
            ProviderField(
                key="vapid_key",
                label="مفتاح Web Push العام (VAPID)",
                secret=False,
                required=False,
                expose_to_clients=True,
            ),
            ProviderField(
                key="service_account_json",
                label="حساب الخدمة (JSON)",
                required=False,
            ),
            MOCK_FIELD,
        ),
    ),
    ProviderKey.PAYOUT: ProviderSpec(
        key=ProviderKey.PAYOUT,
        label="مزود التحويلات الآلية للسحوبات",
        fields=(
            ProviderField(
                key="endpoint", label="عنوان الخدمة", secret=False, required=False
            ),
            ProviderField(key="api_key", label="مفتاح الـ API"),
            MOCK_FIELD,
        ),
        per_country=True,
    ),
}


def get_spec(provider_key: ProviderKey) -> ProviderSpec:
    return PROVIDERS[ProviderKey(provider_key)]
