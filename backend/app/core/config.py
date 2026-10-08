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

    # **بلا افتراضٍ يحمل بيانَ اعتماد** (2026-08-24): كان
    # `postgresql+asyncpg://taxo:taxo@localhost:5432/taxo` — **فوافق جهازَ
    # المطوّر صدفةً**، وبيئةٌ ناقصةٌ تقع عليه بدل أن تقف. وهو نفسُ ما أسقط
    # `suite.sh` في CI طوال عمره. **والقاعدة: لا احتياطَ صامتٌ لسرّ.**
    database_url: str = ""
    redis_url: str = "redis://localhost:6379/0"
    sql_echo: bool = False

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    # **لا قارئَ له منذ SPEC §60** — رمزُ التجديد بلا عمر، والجلسةُ تبقى حتى يخرج
    # صاحبُها. **باقٍ لأن ملفّاتِ البيئة القائمة تضبطه**، ونزعُه يجعلها تضبط ما لا يوجد
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
    # **مِيجاءان لا خمسة** (2026-08-20) — **وخُفض بعد أن بُني الضغط لا قبله**:
    # خفضُه أولاً يكسر رفعاً يعمل اليوم. والتطبيقُ يضغط إلى ١٦٠٠ بكسل وجودةِ
    # ٠٫٨ (`driver-app/src/lib/shrink.ts`)، فوثيقةٌ حقيقيةٌ تخرج ٢٠٠–٤٠٠ ك.ب.
    #
    # **والحسابُ هو العلّة**: ١١ وثيقةً للكبتن الواحد × ٥ ميجا = ٥٥ ميجا،
    # فألفٌ وثمانمئة كبتنٍ يملؤون قرصَ الخادم (١٠٠ جيجا) ومعه تتوقف القاعدةُ
    # والنسخُ والسجلات. وبمِيجاءَين يصير الأسوأُ ٢٢ ميجا — أي أربعةَ أضعافِ
    # السَّعة.
    document_max_bytes: int = 2 * 1024 * 1024
    # الرفع عمليةٌ ثقيلة (قرص + تحقق)، والسقف لكل كبتن لا لكل عنوان: ثلاثة
    # مستنداتٍ وإعادةُ رفعِ ما رُفض تكفيها هذه النافذة بفارقٍ واسع
    document_upload_rate_limit: int = 20
    document_upload_rate_limit_window_seconds: int = 3600

    # ── مكالمةُ الرحلة (SPEC §٦٦-ج، §٦٦-د/٢) ────────────────────────────────
    #
    # **المُرحِّلُ (TURN) على خادمنا — coturn بسرٍّ مشترك (`use-auth-secret`)**، لا مزوّدٌ مدفوعٌ ولا خادمُ STUN لغيرنا (قرارُ
    # المالك). **والسرُّ بنيةٌ تحتيّةٌ لا عقدُ مزوّد**: يتقاسمه الخادمان (هذا وcoturn) ولا يُدخل من اللوحة، فمكانُه بيئةُ الخادم
    # كـ`JWT_SECRET` — **ولا قيمةَ افتراضيّةَ له**: لا احتياطَ صامتٌ لسرّ.
    #
    # **وغيابُهما في التطوير والاختبار مقصود**: `ice_servers` يخرج قائمةً فارغة، **فيتّصل الطرفان بمرشّحي الشبكة المحلّية
    # وحدَهم** (host candidates) — يكفي جهازين على شبكةٍ واحدة، ولا يعبر NAT. وذلك ما يجعل المُرحِّلَ قرارَ نشرٍ لا شرطَ تشغيل.
    turn_shared_secret: str | None = None
    #: عناوينُ المُرحِّل مفصولةً بفاصلة — مثلاً `turn:turn.example:3478?transport=udp,turn:turn.example:3478?transport=tcp`
    turn_urls: str = ""
    #: **عمرُ بيانات الدخول المؤقّتة — ساعتان، أطولُ من أطول مكالمة** (كانت عشرَ دقائق، وصُحّحت ٢٠٢٦-١٠-٠٨).
    #:
    #: **والعلّةُ في المُرحِّل لا في البدء**: الحجزُ على coturn يُجدَّد طوالَ المكالمة (`Refresh` كلَّ بضع دقائق، ومعه
    #: `CreatePermission`/`ChannelBind`)، **وكلُّ طلبٍ منها يحمل الاسمَ نفسَه بختمه** — فإن انقضى الختمُ رُفض التجديدُ وسقط الصوتُ
    #: في منتصف المكالمة، **ولا بابَ يُصدر بياناتٍ جديدةً أثناءها** (تُصدر مع البدء والردّ وحدهما). **وعشرُ دقائق كانت تُسقط
    #: كلَّ مكالمةٍ عبر المُرحِّل نحو دقيقتها العاشرة** (غيرُ مقيسٍ على coturn حيّ — والسقفُ يرتفع لأن ثمنَه صغير).
    #:
    #: **وثمنُ الساعتين**: من نسخ البيانات من تطبيقه يملك مُرحِّلَنا ساعتين لا عشرَ دقائق — **وهي لا تُصدر إلا لطرفَي رحلةٍ في
    #: نافذتها**، والمُرحِّلُ يرفض العناوينَ الخاصّة (`deploy/coturn/turnserver.conf`)
    turn_credential_ttl_seconds: int = 2 * 3600
    #: **سقفُ التسجيل المرفوع** — عشرُ دقائقَ بـOpus على ٣٢ك.ب/ث نحو ٢٫٤ ميجا، فعشرةٌ تتّسع لمكالمةٍ طويلةٍ ولا تملأ قرصاً
    call_recording_max_bytes: int = 10 * 1024 * 1024

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
        # ── نطاقاتُ النفق التجريبيّ (٢٠٢٦-٠٩-٠٩) ──────────────────────────
        #
        # **العلّةُ مقيسةٌ من سجلّ هاتفٍ حقيقيّ**: حزمةُ `ly.tajora.rider.test`
        # تُحمَّل شاشاتُها من `dev-app.tajora.ly` وتنادي `dev-api.tajora.ly`،
        # فأجاب الخادمُ **بلا ترويسة `Access-Control-Allow-Origin`**:
        #
        #     Access to fetch at 'https://dev-api.tajora.ly/api/v1/config'
        #     from origin 'https://dev-app.tajora.ly' has been blocked by
        #     CORS policy
        #
        # **والنفقُ بُني لهذا بعينه** — لتجريب الحزم على هاتفٍ حقيقيّ —
        # **والقائمةُ لم تعرفه قطّ**. فبابٌ مبنيٌّ ومنفذُه مغلق، وهو «بابٌ بلا
        # زرّ» في ثوبِ إعداد.
        #
        # **وتُكتب أسماءً لا نطاقاً**: القائمةُ المفتوحة تُبطل الحماية التي
        # وُجدت لها — وهي القاعدةُ نفسُها المكتوبةُ فوق عن المنفذ 5176.
        # **ومصدرُها `channels.json`** (قناة `test` → `shellUrl`)، وتُقرأ منه
        # حين تُضاف رابعة.
        #
        # **والتطبيقُ يقرأ الفشلَ «تعذّر الوصول إلى الخدمة»** — ولا يستطيع
        # أدقَّ منه: **رفضُ CORS معتِمٌ بالتصميم**، لا يبلغ الشيفرةَ سببُه.
        "https://dev-app.tajora.ly",
        "https://dev-driver.tajora.ly",
        "https://dev-admin.tajora.ly",
        # ── أصلُ حزمة iOS (قرارُ المالك 2026-09-29) ─────────────────────────
        #
        # **على iOS تُجمَّع الشاشاتُ داخل الحزمة** فأصلُها `capacitor://localhost`
        # لا النطاق — وبغيره يُردّ كلُّ نداءٍ يحمل `Authorization` عند طلبه
        # التمهيديّ. **وهو أصلٌ لا يحمله موقعٌ على الويب**: CORS يحرس
        # المتصفّحات، وتطبيقٌ أصليٌّ ينادي الخلفيةَ بلا CORS أصلاً — فقبولُه
        # لا يفتح لموقعٍ باباً. **وأندرويد غلافٌ على النطاق** فلا يحتاجه.
        "capacitor://localhost",
    ]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


#: **أسرارٌ لا افتراضَ لها** — يقف الإقلاعُ إن نقص أحدُها ويُسمّيه.
#:
#: **والقاعدةُ قاعدةُ المشروع** (`SPEC.md` §25.5، `CLAUDE.md`): «بيئةٌ ناقصةٌ
#: تُوقف الإقلاعَ وتسمّي الناقص» — **ولا احتياطَ صامتٌ لسرّ**. وكانت مخالَفةً
#: هنا: عنوانُ القاعدة يحمل `taxo:taxo` فيقع عليه من نسي ضبطَه، **فيعمل على
#: جهازٍ ويصمت على آخر**.
#:
#: **و`jwt_secret` ليس فيها اليومَ بقرارٍ معلَن**: افتراضُه `change-me` من
#: الصنف نفسِه **وأخطرُ**، **ولم يُدرَج لأن إدراجَه يوقف كلَّ بيئةٍ لا تضبطه
#: — والإنتاجُ لا يُقاس من هنا**. معروضٌ على المالك (HANDOFF).
REQUIRED_SECRETS: tuple[tuple[str, str], ...] = (
    ("database_url", "DATABASE_URL"),
)


def _require_secrets(values: Settings) -> Settings:
    """يقف ويسمّي — **ولا يطبع قيمةً**، فالرسالةُ تُقرأ في سجلٍّ لا يُنظَّف."""
    missing = [env for attr, env in REQUIRED_SECRETS if not getattr(values, attr, "")]
    if missing:
        raise RuntimeError(
            "بيئةٌ ناقصة — لا إقلاعَ بلا: "
            + "، ".join(missing)
            + ". اضبطها في ملفِّ البيئة (`.env.local` محلياً، `.env` على الخادم)."
            + " **ولا احتياطَ صامتٌ لسرّ**: عنوانٌ افتراضيٌّ يوافق جهازاً"
            + " ويخالف آخر، وهو ما يجعل العطبَ يظهر بعد النشر لا قبله."
        )
    return values


@lru_cache
def get_settings() -> Settings:
    return _require_secrets(Settings())


settings = get_settings()
