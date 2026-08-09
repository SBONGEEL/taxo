"""طبقة عقود المزودين الخارجيين.

`registry` يصف حقول كل مزود (السرّي منها والعام)، و`credentials` يقرأ ويكتب
الجدول المشفّر. كل ما يحتاج مفتاح مزود في المشروع يمر من هنا — لا من `.env`.
"""

from app.services.providers.credentials import (
    MASK,
    client_config,
    get_credential,
    get_values,
    masked_values,
    provider_is_active,
)
from app.services.providers.registry import PROVIDERS, ProviderSpec, get_spec

__all__ = [
    "MASK",
    "PROVIDERS",
    "ProviderSpec",
    "client_config",
    "get_credential",
    "get_spec",
    "get_values",
    "masked_values",
    "provider_is_active",
]
