from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.core.currency import currency_for_country
from app.core.phone import dial_code_for, national_length_for
from app.core.deps import DbSession
from app.models.enums import CountryCode, VehicleCategory
from app.schemas.auth import AuthMethodResponse
from app.schemas.config import ConfigOut, CountryConfigOut
from app.services import otp, settings_service, verification
from app.services.providers import credentials as credentials_service
from app.services.providers.registry import PROVIDERS

router = APIRouter(tags=["config"])


async def _auth_method(session) -> AuthMethodResponse:
    """نفس ما يعيده `GET /auth/method` — مصدرٌ واحد لا وصفان يفترقان."""
    method = await verification.active_method(session)
    return AuthMethodResponse(
        login="password",
        verification=method,
        otp_length=otp.CODE_LENGTH if method == verification.SMS_OTP else None,
    )


@router.get("/config", response_model=ConfigOut)
async def get_public_config(
    session: DbSession, country_code: CountryCode | None = None
) -> ConfigOut:
    """الإعدادات العامة للواجهات — بلا مصادقة (تحتاجها شاشة الدخول نفسها).

    تحمل الحقول العامة بطبيعتها فقط: التوكن العام لـ Mapbox، مفاتيح الميزات،
    والعملة. الحقول السرية في عقود المزودين لا تغادر الخلفية (SPEC القسم 4).
    """
    countries = [country_code] if country_code is not None else list(CountryCode)

    return ConfigOut(
        app=settings.app_name,
        default_country_code=settings.default_country_code,
        auth=await _auth_method(session),
        countries=[
            CountryConfigOut(
                country_code=country,
                currency=currency_for_country(country),
                features=await settings_service.get_flags(session, country),
                vehicle_categories=list(VehicleCategory),
                dial_code=dial_code_for(country),
                national_number_length=national_length_for(country),
            )
            for country in countries
        ],
        # كلُّ عقدٍ يحمل حقلاً `expose_to_clients` يُنشر هنا بحقوله العامة
        # وحدها — لا قائمةً يدوية تُنسى عند إضافة مزود (المرحلة 8-ب أضافت
        # `firebase_auth`، وواجهةُ الدخول لا تعمل بغير معرّف مشروعه)
        providers={
            spec.key.value: await credentials_service.client_config(session, spec.key)
            for spec in PROVIDERS.values()
            if any(field.expose_to_clients for field in spec.fields)
        },
    )
