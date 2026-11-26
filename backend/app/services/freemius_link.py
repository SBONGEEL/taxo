"""**ربطُ دفعة Freemius بطلبها عندنا** (أمرُ المالك ٢٠٢٦-١١-٢٦، `design/OWNER-2026-11-26-FREEMIUS-BACKUP.md`).

**لماذا بابٌ مستقلّ**: صفحةُ Freemius لا تحمل مرجعَنا (لا حقلَ حرّاً يعود في الإشعار — `payment_gateways/freemius.py`)، فالإشعارُ يقول
«دفعةُ كذا لصاحب البريد كذا على الخطّة كذا»، **ولا يقول أيَّ طلبٍ عندنا**. فهنا يُختار الطلب:

1. **طلبٌ يحمل معرّفَ هذه الدفعة بعينه** (`external_id = "fs:<id>"`) — إعادةُ الإشعار تجده هو، فلا يُربط طلبٌ ثانٍ ولا يُقيَّد مالٌ مرّتين.
2. **وإلا فأحدثُ طلبٍ لصاحب هذا البريد بمبلغ هذه الخطّة** عبر Freemius في آخر ٤٨ ساعة، **المعلَّقُ قبل الملغى**: دفعٌ وصل بعد أن أُلغي
   الطلبُ أو انتهت مهلتُه يُقيَّد ولا يضيع (`settle_from_gateway` بحالاته المتأخّرة).

**والقفل**: الطلبُ المختارُ يُقفل (`for_update`) **ثمّ يُسأل ثانيةً**: أربطَ إشعارٌ متزامنٌ هذه الدفعةَ بطلبٍ آخر والتزمَ بين السؤالين؟ —
فإشعاران للدفعة نفسِها في اللحظة نفسِها لا يربطانها بطلبين (`READ COMMITTED`: السؤالُ الثاني يرى ما التُزم قبله). **ولا قفلَ جديد**:
صفُّ الطلب في موضعه من ترتيب الأقفال («الطلب/الدفعة» بعد الرحلة)، وهذا البابُ أوّلُ ما يقفل في معاملته.

**ودفعةٌ لا طلبَ يطابقها** (بريدٌ بُدّل في الصفحة، أو خطّةٌ لا تطابق المبلغ) **لا تُربط بأقرب طلب**: تُسجَّل خطأً يراه المالك، ويُجاب
Freemius بنجاح — والمالُ عنده يُعاد أو يُعتمد يدويّاً بقرار. الربطُ الخاطئُ أسوأُ من غيابه: يفعّل اشتراكَ غير الدافع.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PaymentRequestStatus
from app.models.payment_request import PayMethod, PaymentRequest
from app.models.user import User
from app.services import payment_requests
from app.services.payment_gateways.freemius import EXTERNAL_PREFIX

logger = logging.getLogger(__name__)

INTEGRATION = "freemius"
#: **أقدمُ طلبٍ يُربط بدفعة** — صفحةٌ فُتحت قبل يومين ودُفعت الآن تُقيَّد؛ وما قبلها يُراجَع يدويّاً
BIND_WINDOW_HOURS = 48
_BINDABLE = (PaymentRequestStatus.PENDING, PaymentRequestStatus.CANCELLED, PaymentRequestStatus.REJECTED)


async def bind(session: AsyncSession, gateway: object, external_id: str, *, now: datetime | None = None) -> PaymentRequest | None:
    """**الطلبُ الذي تخصّه هذه الدفعة** — مربوطاً بمعرّفها؛ و`None` حين لا طلبَ يطابقها (يُسجَّل ولا يُخمَّن)."""
    existing = await payment_requests.find_external(session, integration=INTEGRATION, external_id=external_id)
    if existing is not None:
        return existing
    binding = getattr(gateway, "pending_binding", lambda _eid: None)(external_id)
    if binding is None:
        # **استردادٌ لدفعةٍ لا طلبَ لها عندنا، أو إشعارٌ نُسي** — لا شيءَ يُربط
        logger.error("Freemius: إشعارٌ لدفعةٍ لا طلبَ لها عندنا (%s)", external_id)
        return None
    email, amount = binding.get("email") or "", binding.get("amount")
    if not email or amount is None:
        logger.error("Freemius: دفعةٌ بلا بريدٍ أو بخطّةٍ لا تطابق مبلغاً عندنا (%s) — لم تُربط", external_id)
        return None
    since = (now or datetime.now(UTC)) - timedelta(hours=BIND_WINDOW_HOURS)
    candidate = await session.scalar(
        select(PaymentRequest.id)
        .join(PayMethod, PayMethod.id == PaymentRequest.provider_id)
        .join(User, User.id == PaymentRequest.user_id)
        .where(
            PayMethod.integration == INTEGRATION,
            func.lower(User.email) == email,
            PaymentRequest.amount == amount,
            PaymentRequest.status.in_(_BINDABLE),
            PaymentRequest.created_at >= since,
            or_(PaymentRequest.external_id.is_(None), ~PaymentRequest.external_id.startswith(EXTERNAL_PREFIX)),
        )
        .order_by(case((PaymentRequest.status == PaymentRequestStatus.PENDING, 0), else_=1), PaymentRequest.created_at.desc())
        .limit(1)
    )
    if candidate is None:
        logger.error("Freemius: دفعةٌ لا طلبَ يطابقها (%s، المبلغ %s) — لم تُربط؛ راجعها في لوحة Freemius", external_id, amount)
        return None
    locked = await payment_requests.get_request(session, candidate, for_update=True)
    # **السؤالُ الثاني بعد القفل** — إشعارٌ متزامنٌ للدفعة نفسِها ربطها والتزم بين السؤالين: يُعاد طلبُه هو ولا يُربط هذا
    again = await payment_requests.find_external(session, integration=INTEGRATION, external_id=external_id)
    if again is not None:
        return again
    if locked.external_id and locked.external_id.startswith(EXTERNAL_PREFIX):
        # **دفعةٌ أخرى أخذت هذا الطلبَ بين السؤالين** — لا يُربط طلبٌ بدفعتين
        logger.error("Freemius: الطلبُ %s رُبط بدفعةٍ أخرى قبل %s — لم تُربط", locked.id, external_id)
        return None
    locked.external_id = external_id
    await session.flush()
    return locked
