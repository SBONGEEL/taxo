"""نقطة القرار الوحيدة: هل لهذه الدولة عقد CliQ آلي، ومن يخدمه.

كليكُ الشحن يعمل يدوياً بلا هذا العقد (طلبٌ يؤكده موظف — SPEC القسم 7)،
ويعمل آلياً به. ولذلك `get_cliq_provider_or_none`: **غيابُ العقد ليس عطلاً**
بل هو الوضع الافتراضي الذي يصفه القسم 15/أ.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.models.enums import CountryCode, ProviderKey
from app.services.cliq.acquirer import CliqAcquirerProvider
from app.services.cliq.base import (
    CliqCharge,
    CliqChargeRequest,
    CliqChargeState,
    CliqError,
    CliqProvider,
    CliqUnavailable,
)
from app.services.cliq.mock import MockCliqProvider
from app.services.providers import credentials as credentials_service

__all__ = [
    "CliqAcquirerProvider",
    "CliqCharge",
    "CliqChargeRequest",
    "CliqChargeState",
    "CliqError",
    "CliqProvider",
    "CliqUnavailable",
    "MockCliqProvider",
    "build_provider",
    "company_alias",
    "get_cliq_provider",
    "get_cliq_provider_or_none",
]


def company_alias(values: Mapping[str, Any]) -> str:
    """alias الشركة الذي يُحوَّل عليه — يظهر في رمز الـ QR وللدافع."""
    return str(values.get("company_alias") or "").strip()


def build_provider(values: Mapping[str, Any]) -> CliqProvider:
    if credentials_service.is_mock(values) and not settings.is_production:
        return MockCliqProvider(
            get_redis_client(), company_alias=company_alias(values) or "TAXO"
        )

    endpoint = str(values.get("endpoint") or "").strip()
    merchant_id = str(values.get("merchant_id") or "").strip()
    api_key = str(values.get("api_key") or "").strip()
    alias = company_alias(values)
    if not endpoint or not merchant_id or not api_key or not alias:
        raise CliqUnavailable("عقد كليك الآلي ناقص الحقول")

    return CliqAcquirerProvider(
        endpoint=endpoint,
        merchant_id=merchant_id,
        api_key=api_key,
        company_alias=alias,
    )


async def get_cliq_provider(
    session: AsyncSession, country_code: CountryCode
) -> CliqProvider:
    values = await credentials_service.get_values(
        session, ProviderKey.CLIQ_ACQUIRER, country_code
    )
    if not values:
        raise CliqUnavailable()
    return build_provider(values)


async def get_cliq_provider_or_none(
    session: AsyncSession, country_code: CountryCode
) -> CliqProvider | None:
    """المزود إن كان عقده مفعّلاً وكاملاً، وإلا `None` — فيبقى المسار اليدوي."""
    values = await credentials_service.get_values(
        session, ProviderKey.CLIQ_ACQUIRER, country_code
    )
    if not values:
        return None
    try:
        return build_provider(values)
    except CliqUnavailable:
        return None
