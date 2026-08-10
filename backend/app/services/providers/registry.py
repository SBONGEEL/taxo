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
            ProviderField(
                key="use_mock",
                label="مزود وهمي (تطوير واختبار فقط)",
                secret=False,
                required=False,
            ),
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
        ),
    ),
    ProviderKey.CLIQ_ACQUIRER: ProviderSpec(
        key=ProviderKey.CLIQ_ACQUIRER,
        label="CliQ — التكامل الآلي",
        fields=(
            ProviderField(key="merchant_id", label="معرّف التاجر"),
            ProviderField(key="api_key", label="مفتاح الـ API"),
        ),
        feature_key=FeatureKey.CLIQ_ENABLED,
        per_country=True,
    ),
    ProviderKey.FCM: ProviderSpec(
        key=ProviderKey.FCM,
        label="FCM — الإشعارات",
        fields=(
            ProviderField(key="project_id", label="معرّف المشروع", secret=False),
            ProviderField(key="service_account_json", label="حساب الخدمة (JSON)"),
        ),
    ),
    ProviderKey.PAYOUT: ProviderSpec(
        key=ProviderKey.PAYOUT,
        label="مزود التحويلات الآلية للسحوبات",
        fields=(
            ProviderField(key="endpoint", label="عنوان الخدمة", secret=False),
            ProviderField(key="api_key", label="مفتاح الـ API"),
        ),
        per_country=True,
    ),
}


def get_spec(provider_key: ProviderKey) -> ProviderSpec:
    return PROVIDERS[ProviderKey(provider_key)]
