"""نقطةُ القرار الوحيدة: **أيُّ مُرسِلِ بريدٍ يعمل الآن**.

نفسُ دور `sms.get_sms_provider` و`card_gateway.get_gateway`: المصدرُ عقدُ
`provider_credentials` **المشفَّر** لا `.env`، وإدخالُ العقد من صفحة العقود
يُشغّل القناةَ **بلا تعديل مسار**.

**والمُرسِلُ الوهميُّ ممنوعٌ في الإنتاج**: رمزٌ «يُرسل» إلى Redis يقرؤه من
يبلغ Redis لا من يملك الصندوق.

> **والمُرسِلُ الحقيقيُّ Resend** (`resend.py`) — أُذن به ٢٠٢٦-١١-٢٢ (أمرُ
> المالك الثاني، البند ٢) بعد قرار ٢٠٢٦-٠٨-٣١ «لا مُرسِلَ حتى إذنه». **وأُضيف
> كما وُعد**: ملفٌّ واحدٌ وفرعٌ في `build_provider`، **ولم يتغيّر سطرٌ فوقه**.
>
> **وعقدٌ باسم مُرسِلٍ غيرِ معروف يُرفض بنصّه** — فمن كتب «brevo» اليومَ
> **يقف ويُقال له لمَ**، ولا يمضي إلى مُرسِلٍ لا وجودَ له.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.models.enums import ProviderKey
from app.services.email.base import (
    REQUEST_TIMEOUT_SECONDS,
    EmailError,
    EmailProvider,
    EmailUnavailable,
)
from app.services.email.mock import MockEmailProvider, last_message
from app.services.email.resend import ResendEmailProvider
from app.services.providers import credentials as credentials_service

__all__ = [
    "REQUEST_TIMEOUT_SECONDS",
    "EmailError",
    "EmailProvider",
    "EmailUnavailable",
    "MockEmailProvider",
    "ResendEmailProvider",
    "build_provider",
    "get_email_provider",
    "get_email_provider_or_none",
    "last_message",
]


def build_provider(values: Mapping[str, Any]) -> EmailProvider:
    """يبني المُرسِلَ من قيم عقدٍ مفكوكِ التشفير — من هنا ومن زرِّ الاختبار."""
    if credentials_service.is_mock(values):
        if settings.is_production:
            # **الوهميُّ ممنوعٌ في الإنتاج** — رمزٌ يُقرأ من Redis لا من الصندوق
            raise EmailUnavailable("المُرسِلُ الوهميُّ لا يعمل في الإنتاج — أدخِل عقدَ Resend.")
        return MockEmailProvider(get_redis_client())

    name = str(values.get("provider_name") or "resend").strip().lower()
    if name != "resend":
        # **الرفضُ بنصّه لا سقوطٌ صامت** — مُرسِلٌ واحدٌ مبنيٌّ: Resend
        raise EmailUnavailable(
            f"مُرسِلُ البريد «{name}» غيرُ مبنيّ — المبنيُّ Resend وحدَه."
        )
    api_key = str(values.get("api_key") or "").strip()
    from_address = str(values.get("from_address") or "").strip()
    if not api_key or not from_address:
        raise EmailUnavailable("عقدُ البريد ناقص — المفتاحُ وعنوانُ المُرسِل مطلوبان.")
    return ResendEmailProvider(
        api_key=api_key,
        from_address=from_address,
        from_name=str(values.get("from_name") or "").strip(),
    )


async def get_email_provider(session: AsyncSession) -> EmailProvider:
    """المُرسِلُ المفعَّل، أو 503 إن لم يُدخل عقدُه.

    **والعقدُ عامٌّ لا per-country**: نطاقٌ واحدٌ يرسل للسوقين، **والذي يختلف
    بالدولة هو المفتاح**.
    """
    values = await credentials_service.get_values(session, ProviderKey.EMAIL)
    if not values:
        raise EmailUnavailable()
    return build_provider(values)


async def get_email_provider_or_none(session: AsyncSession) -> EmailProvider | None:
    """**غيابُ العقد حالٌ عاديّةٌ لا عطب** — كـ`fcm` و`cliq`.

    من يسأل «أتُعرض قناةُ البريد؟» يريد جواباً لا استثناءً: **القناةُ مطفأةٌ
    في أكثر التركيبات**، ورفعُ خطأٍ هنا يُسقط `/config` كلَّه على تركيبٍ سليم.
    """
    try:
        return await get_email_provider(session)
    except EmailUnavailable:
        return None
