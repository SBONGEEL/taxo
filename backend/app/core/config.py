from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models.enums import CountryCode

# backend/app/core/config.py -> parents[3] == جذر المستودع
REPO_ROOT = Path(__file__).resolve().parents[3]
# ...و parents[2] == مجلد `backend/` نفسه. الفرق مهم داخل الحاوية: المصدر
# مربوطٌ على `/app` فيصير جذر المستودع `/` — صالحاً لملف `.env` الذي لا وجود
# له هناك أصلاً (compose يمرر `env_file`)، غيرَ صالحٍ لمسارٍ نكتب فيه
BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """إعدادات التطبيق.

    مصدر الأسرار: متغيرات البيئة أولاً، ثم `.env.local` في جذر المستودع.
    هنا **أسرار البنية التحتية فقط** (DB, Redis, JWT, مفتاح التشفير).
    مفاتيح المزودين الخارجيين مكانها جدول `provider_credentials` (المرحلة 2).
    """

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env.local", REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "TAXO"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://taxo:taxo@localhost:5432/taxo"
    redis_url: str = "redis://localhost:6379/0"
    sql_echo: bool = False

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # تشفير provider_credentials at rest
    credentials_encryption_key: str | None = None

    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 300

    # بثّ الموقع عبر REST: الكبتن يبث كل 3 ثوانٍ (20 في الدقيقة)، والسقف
    # يترك هامشاً لإعادة المحاولة بعد انقطاع (SPEC القسم 10)
    location_rate_limit_requests: int = 30
    location_rate_limit_window_seconds: int = 60

    # مستندات الكبتن (المرحلة 9-ب). **مسارٌ لا خدمةُ تخزينٍ سحابية**: مفاتيح
    # أي مزوّد خارجي مكانها `provider_credentials` وصفحةُ العقود، فإدخال S3
    # اليوم يعني مفتاحاً في `.env` — وهو بالضبط ما يمنعه القسم 14. المجلد على
    # حجمٍ مسمّى في compose فلا يذهب مع إعادة البناء ولا يدخل Git.
    document_storage_root: Path = BACKEND_ROOT / "var" / "documents"
    document_max_bytes: int = 5 * 1024 * 1024
    # الرفع عمليةٌ ثقيلة (قرص + تحقق)، والسقف لكل كبتن لا لكل عنوان: ثلاثة
    # مستنداتٍ وإعادةُ رفعِ ما رُفض تكفيها هذه النافذة بفارقٍ واسع
    document_upload_rate_limit: int = 20
    document_upload_rate_limit_window_seconds: int = 3600

    # عنوانا العودة من صفحة الدفع المستضافة — عناوينُ نشرٍ لا أسرارُ مزود،
    # فمكانها هنا لا في `provider_credentials`. الأول عنوان هذه الخلفية كما
    # يراها العالم (يبنى عليه رابط المزود الوهمي)، والثاني صفحةُ الواجهة التي
    # يعود إليها المتصفح ثم تسأل الخلفية عن الحال (SPEC القسم 6.4).
    public_api_base_url: str = "http://localhost:8001"
    # **عنوانٌ لكل تطبيق**: صفحةُ المزود تعيد المتصفح إلى من فتحها، وعنوانٌ
    # واحد كان يعيد الكبتنَ إلى تطبيق الراكب — فقناةُ البطاقة كلُّها كانت
    # معطّلةً عنده لا شاشةَ البطاقات وحدها
    card_return_url: str = "http://localhost:5173/payments/card/return"
    card_return_url_driver: str = "http://localhost:5174/payments/card/return"

    # الدولة التي تفترضها شاشاتُ ما قبل الدخول في التطبيقين (بادئةُ الهاتف
    # الظاهرة أمام الحقل). إعدادُ نشرٍ لا سرّ، كـ`cors_origins`؛ ونشرُه في
    # `GET /config` هو ما يمنع كتابة «962» في كود الواجهات
    default_country_code: CountryCode = CountryCode.JO

    # ومعها `127.0.0.1`: نفس المضيف باسمٍ آخر، و`localhost` على بعض أجهزة
    # التطوير يُحلّ إلى `::1` بينما تنشر Docker على IPv4 وحده — فتفشل النداءات
    # بخطأ CORS يبدو عطلاً في الواجهة وهو عطلُ اسمٍ لا أكثر
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        # بديلُ منفذ تطبيق الراكب حين يشغل 5173 شيءٌ آخر على جهاز المطوّر
        # (`CUSTOMER_APP_PORT` في compose). **رقمٌ واحدٌ موثَّق لا نطاق**:
        # قائمةٌ مفتوحة تُبطل الحماية التي وُجدت من أجلها
        "http://localhost:5176",
        "http://127.0.0.1:5176",
    ]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
