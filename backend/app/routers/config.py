from __future__ import annotations

from fastapi import APIRouter

from app.core import validation_rules
from app.core.config import settings
from app.core.deps import DbSession
from app.models.enums import CountryCode
from app.schemas.auth import AuthMethodResponse
from app.schemas.config import ConfigOut
from app.services import country_config, otp, verification
from app.services.providers import credentials as credentials_service
from app.services.providers.registry import PROVIDERS

router = APIRouter(tags=["config"])


async def _auth_method(session, country: CountryCode) -> AuthMethodResponse:
    """نفس ما يعيده `GET /auth/method` — مصدرٌ واحد لا وصفان يفترقان.

    وبدولةٍ منذ 12-هـ: قناةُ واتساب مفتاحُها per-country، فوصفٌ بلا دولةٍ يعلن
    قناةً قد تكون مطفأةً في سوق القارئ.
    """
    methods = await verification.available_methods(session, country)
    method = methods[0] if methods else verification.NONE
    return AuthMethodResponse(
        login="password",
        verification=method,
        otp_length=(
            otp.CODE_LENGTH if method in verification.CODE_CHANNELS else None
        ),
        channels=list(methods),
    )


@router.get("/config", response_model=ConfigOut)
async def get_public_config(
    session: DbSession, country_code: CountryCode | None = None
) -> ConfigOut:
    """الإعدادات العامة للواجهات — بلا مصادقة (تحتاجها شاشة الدخول نفسها).

    تحمل الحقول العامة بطبيعتها فقط: التوكن العام لـ Mapbox، مفاتيح الميزات،
    والعملة. الحقول السرية في عقود المزودين لا تغادر الخلفية (SPEC القسم 4).
    """
    asked = [country_code] if country_code is not None else list(CountryCode)

    # **الدولةُ المطفأةُ لا تُنشر** (قرارُ المالك 2026-08-19): سوقٌ يُبنى قبل أن
    # يُفتح لا يظهر في قائمة اختيارٍ ولا في تسجيل. **والإخفاءُ هنا لا في
    # التطبيقات**: بيتٌ واحدٌ للحقيقة، فإشعالُ المفتاح يُظهرها في اللحظة نفسِها
    # بلا بناءٍ ولا نشر. والخلفيةُ والبياناتُ والإعداداتُ لها كما هي — هذا
    # إخفاءُ واجهةٍ لا إيقافُ خدمة.
    #
    # **واللوحةُ لا تقرأ من هنا**: لها `GET /admin/countries` وترى الكلَّ دائماً.
    countries = [c for c in asked if await country_config.is_visible(session, c)]

    # **والافتراضيةُ لا تُعلَن وهي مخفيّة**: تطبيقٌ يقرأ اسمَ دولةٍ ليست في
    # القائمة يقع على `undefined` — فتصير الأولى الظاهرةَ، أو تبقى كما هي إن
    # لم يظهر شيءٌ (وحينها لا قائمةَ أصلاً والسؤالُ لا يُطرح).
    default = settings.default_country_code
    if countries and default not in countries:
        default = countries[0]

    return ConfigOut(
        app=settings.app_name,
        default_country_code=default,
        # مُشتقّةٌ من المخططات عند كل نداء — لا جدولَ حدودٍ يُكتب بجانبها ويبرد
        validation=validation_rules.published_rules(),
        auth=await _auth_method(session, country_code or default),
        countries=[await country_config.build(session, c) for c in countries],
        # كلُّ عقدٍ يحمل حقلاً `expose_to_clients` يُنشر هنا بحقوله العامة
        # وحدها — لا قائمةً يدوية تُنسى عند إضافة مزود (المرحلة 8-ب أضافت
        # `firebase_auth`، وواجهةُ الدخول لا تعمل بغير معرّف مشروعه)
        providers={
            spec.key.value: await credentials_service.client_config(session, spec.key)
            for spec in PROVIDERS.values()
            if any(field.expose_to_clients for field in spec.fields)
        },
    )
