from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.core.currency import currency_for_country
from app.core.deps import AuthStrategyDep, DbSession
from app.models.enums import CountryCode, ProviderKey, VehicleCategory
from app.schemas.config import ConfigOut, CountryConfigOut
from app.services import settings_service
from app.services.providers import credentials as credentials_service

router = APIRouter(tags=["config"])


@router.get("/config", response_model=ConfigOut)
async def get_public_config(
    session: DbSession, strategy: AuthStrategyDep, country_code: CountryCode | None = None
) -> ConfigOut:
    """الإعدادات العامة للواجهات — بلا مصادقة (تحتاجها شاشة الدخول نفسها).

    تحمل الحقول العامة بطبيعتها فقط: التوكن العام لـ Mapbox، مفاتيح الميزات،
    والعملة. الحقول السرية في عقود المزودين لا تغادر الخلفية (SPEC القسم 4).
    """
    countries = [country_code] if country_code is not None else list(CountryCode)

    return ConfigOut(
        app=settings.app_name,
        auth=strategy.describe(),
        countries=[
            CountryConfigOut(
                country_code=country,
                currency=currency_for_country(country),
                features=await settings_service.get_flags(session, country),
                vehicle_categories=list(VehicleCategory),
            )
            for country in countries
        ],
        providers={
            ProviderKey.MAPBOX.value: await credentials_service.client_config(
                session, ProviderKey.MAPBOX
            )
        },
    )
