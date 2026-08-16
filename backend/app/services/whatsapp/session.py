"""حالُ جلسة البوابة الذاتية — **سؤالٌ واحدٌ تسأله اللوحةُ والمهمّةُ الدورية**.

ومكانُه خدمةٌ لا راوتر لأن له قارئَين: صفحةُ العقود (ليقرأ إنسان)، والمهمّةُ
كلَّ دقيقة (لتنبّه حين تسقط). وقاعدةٌ يقرؤها بابان وتُكتب في أحدهما هي قاعدةٌ
يفترق البابان عليها.

**والحالُ خمسٌ لا اثنتان**، وهذا هو كلُّ ما تشتريه هذه الشاشة:

| الحال | ما تعنيه | ومن يتحرك |
|---|---|---|
| `linked` | مرتبطةٌ وترسل | لا أحد |
| `awaiting_qr` | **تنتظر إنساناً يمسح رمزاً** | المشرف، الآن |
| `disconnected` | سقطت وتحاول العودة وحدها | لا أحد بعد |
| `unreachable` | البوابةُ نفسُها لا تُجيب | من يملك الخادم |
| `off` | العقدُ ليس على القناة الذاتية أصلاً | لا أحد |

**ودمجُها في «متصل/غير متصل» هو ما يجعل جلسةً تسقط صامتة**: الثانيةُ تنتظر
إنساناً والثالثةُ تنتظر شبكة، ومن يقرأ «غير متصل» لا يعرف أيَّهما فينتظر ما لا
يأتي — وتسجيلُ المستخدمين واقفٌ طوالها.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AuditAction, ProviderKey
from app.models.user import User
from app.schemas.provider import WhatsAppSessionOut
from app.services import audit
from app.services.providers import credentials as credentials_service
from app.services.whatsapp import TRANSPORT_BAILEYS, WhatsAppError, build_provider
from app.services.whatsapp.baileys import BaileysGatewayProvider

# الحالُ حين لا تكون القناةُ الذاتيةَ أصلاً — **ليست عطلاً**: القناةُ الرسمية
# لا جلسةَ لها تُراقَب، والشاشةُ تقولها بدل أن تعرض «غير متصل» عن شيءٍ لا وجودَ له
STATE_OFF = "off"


async def _provider(session: AsyncSession) -> BaileysGatewayProvider | None:
    """المزودُ الذاتيُّ إن كان العقدُ عليه — و`None` فيما عداه.

    **ولا يرمي على عقدٍ ناقص**: شاشةُ الحالة تُفتح غالباً *لأن* شيئاً ناقص.
    """
    values = await credentials_service.get_values(session, ProviderKey.WHATSAPP)
    if not values:
        return None
    if str(values.get("transport") or "").strip() != TRANSPORT_BAILEYS:
        return None
    try:
        provider = build_provider(values)
    except Exception:  # pragma: no cover - عقدٌ ناقصٌ يُقرأ «مطفأة»
        return None
    return provider if isinstance(provider, BaileysGatewayProvider) else None


def _off(note: str) -> WhatsAppSessionOut:
    return WhatsAppSessionOut(state=STATE_OFF, last_error=note, needs_human=False)


async def read(session: AsyncSession) -> WhatsAppSessionOut:
    """الحالُ ومعها رمزُ الربط إن وُجد — **في نداءٍ واحد**."""
    provider = await _provider(session)
    if provider is None:
        return _off("العقد ليس على القناة الذاتية")

    raw: dict[str, Any] = await provider.session_status()
    state = str(raw.get("state") or "unreachable")

    qr: str | None = None
    if state == "awaiting_qr":
        # **الرمزُ يُطلب حين يُحتاج فقط**: نداءٌ ثانٍ في كل استطلاعٍ للحالة
        # يضاعف حركةً لا تُقرأ — والمهمّةُ الدورية تسأل كلَّ دقيقة
        try:
            qr = await provider.session_qr()
        except WhatsAppError:
            qr = None

    return WhatsAppSessionOut(
        state=state,
        phone=raw.get("phone"),
        since=raw.get("since"),
        last_error=raw.get("last_error"),
        needs_human=bool(raw.get("needs_human")),
        queue_depth=int(raw.get("queue_depth") or 0),
        qr=qr,
    )


async def logout(session: AsyncSession, *, admin: User) -> WhatsAppSessionOut:
    """يفصل الجلسةَ ويمحو حالتَها — والـcommit للراوتر."""
    provider = await _provider(session)
    if provider is None:
        return _off("العقد ليس على القناة الذاتية")

    await provider.session_logout()
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="whatsapp_session",
        details={"action": "logout"},
    )
    return await read(session)
