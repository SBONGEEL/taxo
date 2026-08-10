"""نقطة القرار الوحيدة: هل لهذه الدولة عقد تحويلات آلي، ومن يخدمه.

بلا العقد يبقى المسار اليدوي الذي يصفه القسم 9 (المحاسب يحوّل ثم يسجّل
المرجع)، وبه يصير زرّاً واحداً. الاثنان قائمان معاً عمداً: مزودٌ متوقف لا
يجوز أن يحبس مال كبتنٍ ينتظر سحبه.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.models.enums import CountryCode, ProviderKey
from app.services.payout.base import (
    PayoutError,
    PayoutProvider,
    PayoutRequest,
    PayoutState,
    PayoutUnavailable,
)
from app.services.payout.http_payout import HttpPayoutProvider
from app.services.payout.mock import MockPayoutProvider
from app.services.providers import credentials as credentials_service

__all__ = [
    "HttpPayoutProvider",
    "MockPayoutProvider",
    "PayoutError",
    "PayoutProvider",
    "PayoutRequest",
    "PayoutState",
    "PayoutUnavailable",
    "build_provider",
    "get_payout_provider",
]


def build_provider(values: Mapping[str, Any]) -> PayoutProvider:
    if bool(values.get("use_mock")) and not settings.is_production:
        return MockPayoutProvider(get_redis_client())

    endpoint = str(values.get("endpoint") or "").strip()
    api_key = str(values.get("api_key") or "").strip()
    if not endpoint or not api_key:
        raise PayoutUnavailable("عقد التحويلات الآلية ناقص العنوان أو المفتاح")
    return HttpPayoutProvider(endpoint=endpoint, api_key=api_key)


async def get_payout_provider(
    session: AsyncSession, country_code: CountryCode
) -> PayoutProvider:
    values = await credentials_service.get_values(
        session, ProviderKey.PAYOUT, country_code
    )
    if not values:
        raise PayoutUnavailable()
    return build_provider(values)
