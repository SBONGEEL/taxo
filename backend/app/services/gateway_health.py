"""**صحّةُ الوسيط الآليّ** (SPEC §٨٢-أ/١ و٦، أمرُ المالك ٢٠٢٦-١٠-٢٢) — فحصٌ قبل فتح الصفحة، وإشعارُ المالك حين يتوقّف وحين يعود.

**الحالُ في Redis لا في القاعدة**: مفتاحٌ لكلِّ وسيطٍ وسوقٍ يقول «متوقّفٌ منذ». **ووجودُه وغيابُه يُكتبان بأمرٍ ذرّيّ** (`SET NX` و`DELETE`)
— فعشرةُ دافعين يصطدمون بالانقطاع معاً إشعارٌ واحدٌ للمالك لا عشرة، وعودتُه إشعارٌ واحد.

**ومن يكتشف العودة؟** فحصُ الصفحة التالية، **والتسويةُ الدوريّة** (`probe_all`) — فوسيطٌ عاد في الليل يُعرف ولو لم يدفع أحد.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CountryCode
from app.models.provider_credential import ProviderCredential

logger = logging.getLogger(__name__)

_KEY = "gateway:down:{}:{}"


async def note(integration: str, country: CountryCode, *, up: bool) -> None:
    """**يكتب الحالَ ويُشعر المالكَ عند تبدّلها وحدَه** — والفشلُ في Redis لا يُسقط دفعاً."""
    from app.core.redis_client import get_redis_client
    from app.services import alert_capture

    key = _KEY.format(integration, country.value)
    try:
        redis = get_redis_client()
        if up:
            changed = bool(await redis.delete(key))
            kind = "gateway_up"
        else:
            changed = bool(await redis.set(key, datetime.now(UTC).isoformat(), nx=True))
            kind = "gateway_down"
    except Exception:  # pragma: no cover - Redis معطّلٌ لا يمنع دفعاً
        logger.warning("تعذّرت كتابةُ حال الوسيط %s/%s", integration, country.value, exc_info=True)
        return
    if changed:
        alert_capture.ship_after_commit(None, kind, "signal", uuid.uuid4(), country=country.value, gateway=integration)


async def is_down(integration: str, country: CountryCode) -> bool:
    from app.core.redis_client import get_redis_client

    try:
        return bool(await get_redis_client().exists(_KEY.format(integration, country.value)))
    except Exception:  # pragma: no cover
        return False


async def require_up(gateway, integration: str, country: CountryCode) -> None:
    """**قبل أن يُرسل الدافعُ إلى صفحة**: فحصٌ سريع — متوقّفٌ أو بطيءٌ جدّاً ⇐ `GatewayDown` بلغته، ويُشعَر المالكُ أوّلَ مرّة."""
    from app.services import payment_gateways

    health = getattr(gateway, "health", None)
    if health is None:
        return
    try:
        await health()
    except payment_gateways.GatewayDown:
        await note(integration, country, up=False)
        raise
    await note(integration, country, up=True)


async def probe_all(session: AsyncSession) -> int:
    """**كلُّ عقدٍ مفعَّلٍ لوسيطٍ يفحص صحّتَه** — من التسوية الدوريّة؛ يعيد عددَ المتوقّف."""
    from app.services import payment_gateways

    down = 0
    for integration, key in payment_gateways.PROVIDER_KEYS.items():
        rows = (
            await session.scalars(
                select(ProviderCredential).where(
                    ProviderCredential.provider_key == key, ProviderCredential.is_active.is_(True)
                )
            )
        ).all()
        for row in rows:
            if row.country_code is None:
                continue
            country = CountryCode(row.country_code)
            try:
                gateway = await payment_gateways.gateway_for(session, integration, country)
            except payment_gateways.GatewayUnavailable:
                continue
            health = getattr(gateway, "health", None)
            if health is None:
                continue
            try:
                await health()
            except payment_gateways.GatewayDown:
                down += 1
                await note(integration, country, up=False)
                continue
            except payment_gateways.GatewayError:
                continue
            await note(integration, country, up=True)
    return down
