"""**حارسُ MoonPay Commerce وهو حيّ** (أمرُ المالك ٢٠٢٦-١١-١٤، البند ٨): «watch every payment — if a webhook fails verification, a credit
doesn't match what arrived, a payment is credited twice, or card payments keep failing, turn the switch OFF immediately and tell me».

**ما يُطفئ الطريقةَ آليّاً** (المفتاحان معاً في الأردن، بسطرٍ في التدقيق، **وإشعارٌ للمالك** `payment_method_hidden`):
1. **إشعارٌ يحمل توقيعاً لا يطابق** — من بابه في `routers/payment_requests.gateway_webhook`. وطرقُ البابِ بلا ترويسة التوقيع لا يُطفئ شيئاً.
2. **ما وصل لا يطابق ما طُلب** — الطلبُ يبقى «قيد المعالجة» بلا قيد (`apply_gateway_outcome`)، والطريقةُ تُطفأ.
3. **إخفاقاتٌ متتالية** — آخرُ `FAILURE_STREAK` طلباتٍ حُسمت بهذه الطريقة في السوق كلُّها «فشل».

**و«قُيِّد مرّتين» لا يقع بالبناء**: القيدُ بمفتاح `payment_request:<المعرّف>` الفريد في الدفتر، وإشعارٌ مكرَّرٌ يجد الطلبَ محسوماً
(`test_moonpay.py` يقيسه). **ودفعُ صاحبها للغرض نفسِه مرّتين** (`PAID_TWICE`) ليس عطباً: الزائدُ في محفظته كما في كلِّ وسيط.

**والإشعالُ بعده قرارُ المالك أو من يملك «مفاتيح الميزات»** — لا يعود وحدَه.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CountryCode, FeatureKey, PaymentRequestStatus
from app.models.payment_request import PayMethod, PaymentRequest

INTEGRATION = "moonpay"
FLAGS = (FeatureKey.MOONPAY_DRIVER_ENABLED, FeatureKey.MOONPAY_RIDER_ENABLED)
#: **كم إخفاقاً متتالياً يُطفئ** — ثلاثةٌ في السوق، لا لدافعٍ واحد
FAILURE_STREAK = 3

CAUSE_SIGNATURE = "إشعارٌ من MoonPay Commerce بتوقيعٍ لا يطابق"
CAUSE_MISMATCH = "وصل دفعٌ بمبلغٍ لا يطابق المطلوب"
CAUSE_FAILURES = "إخفاقاتٌ متتالية في الدفع"


async def trip(session: AsyncSession, *, cause: str, country: CountryCode = CountryCode.JO) -> bool:
    """**يُطفئ المفتاحين ويُشعر المالك** — و`False` إن كانا مطفأين قبلُ (فلا يتكرّر الإشعار). الالتزامُ على المستدعي."""
    from app.services import alert_capture, settings_service

    was_on = False
    for key in FLAGS:
        was_on = await settings_service.is_feature_enabled(session, country, key) or was_on
        await settings_service.set_flag(
            session, country_code=country, feature_key=key, enabled=False, actor=None,
            reason=f"إطفاءٌ آليّ — {cause}"[:200],
        )
    if was_on:
        alert_capture.ship_after_commit(
            session, "payment_method_hidden", "signal", uuid.uuid4(),
            country=CountryCode(country).value, method="MoonPay Commerce", cause=cause,
        )
    return was_on


async def observe(session: AsyncSession, *, request: PaymentRequest, event) -> None:
    """**بعد كلِّ حسمٍ من MoonPay** — مبلغٌ لا يطابق، أو ثالثُ إخفاقٍ متتالٍ ⇐ `trip`."""
    from app.services.pricing import as_money

    if event.outcome is PaymentRequestStatus.APPROVED:
        if event.amount is not None and as_money(event.amount) != request.amount:
            await trip(session, cause=CAUSE_MISMATCH, country=request.country_code)
        return
    if event.outcome is not PaymentRequestStatus.REJECTED:
        return
    await session.flush()
    recent = (
        await session.scalars(
            select(PaymentRequest.status)
            .join(PayMethod, PayMethod.id == PaymentRequest.provider_id)
            .where(
                PayMethod.integration == INTEGRATION,
                PaymentRequest.country_code == request.country_code,
                PaymentRequest.status.in_((PaymentRequestStatus.APPROVED, PaymentRequestStatus.REJECTED)),
            )
            .order_by(PaymentRequest.updated_at.desc())
            .limit(FAILURE_STREAK)
        )
    ).all()
    if len(recent) >= FAILURE_STREAK and all(status is PaymentRequestStatus.REJECTED for status in recent):
        await trip(session, cause=CAUSE_FAILURES, country=request.country_code)
