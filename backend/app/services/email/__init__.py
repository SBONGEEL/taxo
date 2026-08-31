"""نقطةُ القرار الوحيدة: **أيُّ مُرسِلِ بريدٍ يعمل الآن**.

نفسُ دور `sms.get_sms_provider` و`card_gateway.get_gateway`: المصدرُ عقدُ
`provider_credentials` **المشفَّر** لا `.env`، وإدخالُ العقد من صفحة العقود
يُشغّل القناةَ **بلا تعديل مسار**.

**والمُرسِلُ الوهميُّ ممنوعٌ في الإنتاج**: رمزٌ «يُرسل» إلى Redis يقرؤه من
يبلغ Redis لا من يملك الصندوق.

> **ولا مُرسِلَ حقيقيٌّ في هذا المجلَّد اليوم** (قرارُ المالك 2026-08-31):
> **لا يُلمس عقدُ Resend ولا يُرسل بريدٌ حقيقيٌّ حتى إذنُه**. فمن يضيفه غداً
> يكتب ملفّاً واحداً ويصله بفرعٍ في `build_provider` — **ولا يمسّ شيئاً فوقه**.
>
> **وغيابُه ليس نقصاً مسكوتاً عنه**: `build_provider` **يرفض بنصٍّ** أيَّ عقدٍ
> ليس وهميّاً — فمن أدخل عقداً حقيقيّاً اليومَ **يقف ويُقال له لمَ**، ولا
> يمضي إلى مُرسِلٍ لا وجودَ له.
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
from app.services.providers import credentials as credentials_service

__all__ = [
    "REQUEST_TIMEOUT_SECONDS",
    "EmailError",
    "EmailProvider",
    "EmailUnavailable",
    "MockEmailProvider",
    "build_provider",
    "get_email_provider",
    "get_email_provider_or_none",
    "last_message",
]


def build_provider(values: Mapping[str, Any]) -> EmailProvider:
    """يبني المُرسِلَ من قيم عقدٍ مفكوكِ التشفير — من هنا ومن زرِّ الاختبار."""
    if credentials_service.is_mock(values) and not settings.is_production:
        return MockEmailProvider(get_redis_client())

    # **الرفضُ بنصّه لا سقوطٌ صامت** — ولا مُرسِلَ حقيقيٌّ مبنيٌّ بعد
    raise EmailUnavailable(
        "لم يُبنَ مُرسِلُ بريدٍ حقيقيٌّ بعد — القناةُ تعمل بالمُرسِل الوهميّ "
        "وحدَه حتى يأذن المالك بعقدٍ حقيقيّ."
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
