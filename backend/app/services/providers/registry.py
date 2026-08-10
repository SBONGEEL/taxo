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
        fields=(
            ProviderField(
                key="project_id",
                label="معرّف مشروع Firebase",
                secret=False,
                # يُنشر للواجهات: تطبيقُ العميل يحتاجه ليتحقق من الرقم أصلاً،
                # وهو معرِّفٌ عام كتوكن Mapbox العام
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
        fields=(
            ProviderField(key="project_id", label="معرّف المشروع", secret=False),
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
