"""**قاطعُ الدائرة لطرق الدفع** (SPEC §٨٧/١، أمرُ المالك ٢٠٢٦-١٠-٢٨) — ثلاثُ إخفاقاتٍ متتاليةٍ عند وسيطٍ تُخفي طريقتَه آليّاً.

**لمَ**: Edahabia فشلت ستّاً من ستٍّ عند Chargily (`design/CHARGILY-EDAHABIA-FAILURES.md`) والطريقةُ معروضةٌ للناس — كلُّ دافعٍ بعد
الثاني دفع ثمنَ ما عُرف. **فالإخفاءُ يقع عند الثالث بلا انتظار أحد**، ويُشعَر المالك، **ويرى الدافعُ لافتةً تدلّه على البدائل**.

**ما يُعدّ إخفاقاً**: دفعةٌ عند وسيطٍ **رفضها الوسيطُ نفسُه** (`rejected` بلا مراجِع) — لا إلغاءُ الدافع ولا مهلتُه، فمن عاد ولم يُكمل لم
يجد طريقاً مسدوداً. **و«متتالية»** بترتيب حسمها: آخرُ ثلاثٍ حُسمت عند الوسيط كلُّها رفض. **ودفعةٌ ناجحةٌ واحدةٌ تقطع السلسلة.**
**وعقدُ التجربة لا يُخفي طريقةً حيّة** — مالُه لا وجودَ له، وفشلُه فشلُ اختبار.

**ولا يعيدها إلا المالك** (نصُّه: «You never re-enable a hidden payment method yourself — only the owner, from the panel») — بسببٍ مكتوبٍ
ووقت (`restore`)، **والبابُ العامُّ لتحرير الطريقة يرفض تفعيلَ مخفيّة** ولو ملك صاحبُه `settings.write`.

**وترتيبُ الأقفال**: يُستدعى من داخل حسم الدفعة (صفُّ الطلب مقفل)، **ثمّ يُقفل صفَّ الطريقة** — ولا مسارَ يقفل الطريقةَ ثمّ الطلب.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInput, PermissionDenied
from app.models.enums import AuditAction, CountryCode, PaymentRequestPurpose, PaymentRequestStatus, UserRole
from app.models.payment_request import PayMethod, PaymentRequest
from app.models.user import User
from app.services import audit

#: **ثلاثٌ بنصِّ المالك** — «auto-hide after 3 consecutive failures»
FAILURE_STREAK = 3

#: **ما حسمه الوسيطُ** — المعتمَدُ والمردودُ نجاحٌ، والمرفوضُ إخفاق؛ والملغى خارجُهما (الدافعُ لم يُكمل)
_DECIDED = (PaymentRequestStatus.APPROVED, PaymentRequestStatus.REFUNDED, PaymentRequestStatus.REJECTED)

AUTO_REASON = "أُخفيت آليّاً بعد {} إخفاقاتٍ متتاليةٍ عند الوسيط"


def _now() -> datetime:
    return datetime.now(UTC)


async def failure_streak(session: AsyncSession, provider_id) -> int:
    """**كم إخفاقاً متتالياً الآن** — من آخر ما حسمه الوسيطُ لهذه الطريقة، حتى أوّلِ نجاح."""
    rows = (
        await session.scalars(
            select(PaymentRequest.status)
            .where(
                PaymentRequest.provider_id == provider_id,
                PaymentRequest.external_id.is_not(None),
                PaymentRequest.status.in_(_DECIDED),
                # **ما حسمه الوسيطُ لا المراجِع** — رفضُ موظّفٍ لتحويلٍ يدويٍّ ليس عطباً في الطريقة
                PaymentRequest.reviewed_by.is_(None),
            )
            .order_by(func.coalesce(PaymentRequest.reviewed_at, PaymentRequest.updated_at).desc())
            .limit(FAILURE_STREAK * 4)
        )
    ).all()
    streak = 0
    for status in rows:
        if status is not PaymentRequestStatus.REJECTED:
            break
        streak += 1
    return streak


async def after_failure(session: AsyncSession, request: PaymentRequest, *, test_money: bool) -> bool:
    """**بعد رفض الوسيط لدفعة**: إن بلغت السلسلةُ حدَّها أُخفيت الطريقةُ وأُشعر المالك — ويعيد «أأُخفيت الآن؟»."""
    if test_money or request.provider.integration is None:
        return False
    await session.flush()
    if await failure_streak(session, request.provider_id) < FAILURE_STREAK:
        return False
    provider = await session.scalar(
        select(PayMethod)
        .where(PayMethod.id == request.provider_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if provider is None or not provider.enabled:
        return False
    reason = AUTO_REASON.format(FAILURE_STREAK)
    provider.enabled = False
    provider.hidden_auto = True
    provider.hidden_reason = reason
    provider.hidden_at = _now()
    await audit.record(
        session,
        actor=None,
        action=AuditAction.UPDATE,
        entity_type="payment_provider",
        entity_id=provider.id,
        details={"action": "auto_hide", "reason": reason, "streak": FAILURE_STREAK},
    )
    from app.services import alert_capture

    alert_capture.ship_after_commit(
        session, "payment_method_hidden", "payment_provider", provider.id,
        country=provider.country_code.value, method=provider.name, gateway=provider.integration,
    )
    return True


async def hide(session: AsyncSession, *, provider: PayMethod, actor: User, reason: str) -> PayMethod:
    """**المالكُ يُخفي طريقةً بسببٍ مكتوب** — فلا يعيدها غيرُه (كإخفاء Chargily في الجزائر، §٨٦)."""
    if not actor.has_role(UserRole.OWNER):
        raise PermissionDenied("إخفاءُ طريقة دفعٍ بسببٍ قرارُ المالك")
    text = (reason or "").strip()
    if not text:
        raise InvalidInput("اكتب سببَ الإخفاء", field="reason")
    provider.enabled = False
    provider.hidden_auto = False
    provider.hidden_reason = text[:500]
    provider.hidden_at = _now()
    await audit.record(
        session, actor=actor, action=AuditAction.UPDATE, entity_type="payment_provider", entity_id=provider.id,
        details={"action": "hide", "reason": provider.hidden_reason},
    )
    return provider


async def restore(session: AsyncSession, *, provider: PayMethod, actor: User, reason: str) -> PayMethod:
    """**إعادةُ طريقةٍ مخفيّة — المالكُ وحدَه، بسببٍ ووقت** (نصُّه: «owner-only turn back on with reason and time»)."""
    if not actor.has_role(UserRole.OWNER):
        raise PermissionDenied("إعادةُ طريقةٍ مخفيّةٍ للمالك وحدَه")
    text = (reason or "").strip()
    if not text:
        raise InvalidInput("اكتب سببَ الإعادة", field="reason")
    if provider.hidden_reason is None:
        raise InvalidInput("هذه الطريقةُ ليست مخفيّة", field="reason")
    was = provider.hidden_reason
    provider.hidden_reason = None
    provider.hidden_at = None
    provider.hidden_auto = False
    provider.enabled = True
    await audit.record(
        session, actor=actor, action=AuditAction.UPDATE, entity_type="payment_provider", entity_id=provider.id,
        details={"action": "restore", "reason": text[:500], "was_hidden_for": was, "at": _now().isoformat()},
    )
    return provider


def require_not_hidden(provider: PayMethod, *, enabling: bool) -> None:
    """**البابُ العامُّ لا يفعّل مخفيّة** — إعادتُها بزرِّ المالك وحدَه (`restore`)."""
    if enabling and provider.hidden_reason is not None:
        raise PermissionDenied("هذه الطريقةُ مخفيّةٌ بسببٍ مكتوب — يعيدها المالكُ وحدَه بزرِّ «إعادة التشغيل»")


async def paused_names(
    session: AsyncSession, country: CountryCode, purpose: PaymentRequestPurpose
) -> list[str]:
    """**لافتةُ الدافع** (§٨٧/١): أسماءُ طرق الوسيط **التي أخفاها القاطعُ** في سوقه لهذا الغرض — فيرى أن البطاقةَ متوقّفةٌ مؤقّتاً ويختار بديلاً.

    **وما أخفاه المالكُ بيده لا يُعلَن «متوقّفاً مؤقّتاً»** (قِيس على الإنتاج ٢٠٢٦-١٠-٢٩): Chargily مخفيٌّ بقراره، فكانت اللافتةُ تقول
    «الذهبية وCIB متوقّفٌ مؤقّتاً» **فوق** «بطاقة الذهبية أو CIB (SofizPay)» القائمة — جملةٌ تنفي ما تحتها. القرارُ ليس عطلاً."""
    column = PayMethod.for_subscription if purpose is PaymentRequestPurpose.SUBSCRIPTION else PayMethod.for_topup
    rows = (
        await session.scalars(
            select(PayMethod.name)
            .where(
                PayMethod.country_code == country,
                PayMethod.integration.is_not(None),
                PayMethod.enabled.is_(False),
                PayMethod.hidden_reason.is_not(None),
                PayMethod.hidden_auto.is_(True),
                column.is_(True),
            )
            .order_by(PayMethod.sort_order, PayMethod.name)
        )
    ).all()
    return list(dict.fromkeys(rows))
