"""سحب من محفظة الكبتن (SPEC القسم 9).

`pending → approved → paid` مع `rejected` مخرجاً من الأوليين. المحاسب يحوّل
خارج النظام (كليك على `cliq_alias` أو حوالة بنكية) ثم يسجل المرجع، وعندها —
وعندها وحدها — يُكتب قيد `withdrawal`.

**الراكب لا يسحب أبداً** (SPEC القسم 7): لا مسار هنا يقبل غير كبتن.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.exceptions import (
    InsufficientBalance,
    InvalidInput,
    InvalidStatusTransition,
    NotFound,
    WalletLimitExceeded,
)
from app.models.driver import Driver
from app.models.enums import (
    DriverStatus,
    AuditAction,
    WalletOwnerType,
    WalletTransactionType,
    WithdrawalMethod,
    WithdrawalStatus,
)
from app.models.user import User
from app.models.wallet import PENDING_WITHDRAWAL_STATUSES, WithdrawalRequest
from app.services import audit, cancellation, settings_service, wallet
from app.services.payout import (
    PayoutError,
    PayoutRequest,
    PayoutState,
    get_payout_provider,
)
from app.services.pricing import round_money

# ما ليس هنا ممنوع — نفس نهج آلة حالات الرحلة
ALLOWED_TRANSITIONS: dict[WithdrawalStatus, frozenset[WithdrawalStatus]] = {
    WithdrawalStatus.PENDING: frozenset(
        {WithdrawalStatus.APPROVED, WithdrawalStatus.REJECTED}
    ),
    # الرفض بعد الموافقة وارد: قد يتعذّر التحويل فعلياً بعد اعتماده
    WithdrawalStatus.APPROVED: frozenset(
        {WithdrawalStatus.PAID, WithdrawalStatus.REJECTED}
    ),
    WithdrawalStatus.PAID: frozenset(),
    WithdrawalStatus.REJECTED: frozenset(),
}


def _now() -> datetime:
    return datetime.now(UTC)


def _require_transition(
    request: WithdrawalRequest, target: WithdrawalStatus
) -> None:
    if target not in ALLOWED_TRANSITIONS[request.status]:
        raise InvalidStatusTransition(
            f"لا يمكن الانتقال من «{request.status.value}» إلى «{target.value}»"
        )


async def get_request(
    session: AsyncSession, request_id: uuid.UUID, *, for_update: bool = False
) -> WithdrawalRequest:
    """`for_update` إلزامي لكل مسار يغيّر الحالة.

    بدونه يقرأ ضغطتان متزامنتان على «مدفوع» الحالةَ نفسها قبل أن يُثبّت
    أيّهما تغييره، فتمر كلتاهما من `_require_transition` — ولا يُنقذ المالَ
    وقتها إلا مفتاح عدم التكرار، والحارس لا يُترك حارساً وحيداً. نفس نهج
    `rides.cancel_ride` مع قفل صف الرحلة.
    """
    stmt = select(WithdrawalRequest).where(WithdrawalRequest.id == request_id)
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)

    request = await session.scalar(stmt)
    if request is None:
        raise NotFound("طلب السحب غير موجود")
    return request


async def list_for_driver(
    session: AsyncSession, driver_id: uuid.UUID, *, limit: int, offset: int
) -> Sequence[WithdrawalRequest]:
    stmt = (
        select(WithdrawalRequest)
        .where(WithdrawalRequest.driver_id == driver_id)
        .order_by(WithdrawalRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return (await session.scalars(stmt)).all()


async def list_all(
    session: AsyncSession,
    *,
    status: WithdrawalStatus | None,
    limit: int,
    offset: int,
) -> Sequence[WithdrawalRequest]:
    stmt = select(WithdrawalRequest).order_by(WithdrawalRequest.created_at.desc())
    if status is not None:
        stmt = stmt.where(WithdrawalRequest.status == status)
    return (await session.scalars(stmt.limit(limit).offset(offset))).all()


async def _reserved_amount(session: AsyncSession, driver_id: uuid.UUID) -> Decimal:
    """مجموع الطلبات القائمة التي لم تُخصم بعد.

    القيد لا يُكتب إلا عند `paid`، فرصيدٌ لم يُمس بعدُ ليس رصيداً متاحاً:
    بدون عدّ هذه الطلبات يطلب الكبتن نفس المبلغ مرتين ويُدفع له مرتين.
    """
    total = await session.scalar(
        select(func.coalesce(func.sum(WithdrawalRequest.amount), 0)).where(
            WithdrawalRequest.driver_id == driver_id,
            WithdrawalRequest.status.in_(PENDING_WITHDRAWAL_STATUSES),
        )
    )
    return round_money(Decimal(total))


async def available_balance(
    session: AsyncSession, driver: Driver, user: User
) -> Decimal:
    """الرصيد القابل للسحب = الرصيد − ما حجزته طلبات قائمة − **المحتجَز**.

    **والمحتجَزُ شرطٌ لا قيد** (البند ١٣): لا تُكتب حركةٌ تحجزه، فقيدٌ يُكتب
    لحجزه يجعل الرصيدَ يكذب على صاحبه — يقرأ رقماً ناقصاً بلا أن يُدفع له.
    وهو نفسُ شكلِ `_reserved_amount` القائم منذ المرحلة 5.

    **ويسقط شرطُه لمن أُلغي تفعيلُ حسابه**: المحتجَزُ وُجد ليَخرج في تلك
    اللحظة بعينها، فبقاؤه بعدها احتجازٌ لمالٍ بلا سبب.
    """
    current = await wallet.balance(session, user.id, WalletOwnerType.DRIVER)
    held = await _reserved_amount(session, driver.id)
    # **وما قبضه بيده لكبتنٍ آخر ليس ماله** (`CANCELLATION-FEE.md` §6-أ): دخل
    # رصيدَه قيداً؟ لا — لم يدخله أصلاً، لكنه في جيبه نقداً وعليه تحويلُه.
    # فسحبُه كلَّ رصيده يجعل المنصّةَ تدفع له ما تعرف أنه عند غيره، ثم تطالبه
    # به بلا شيءٍ يُخصم منه. **شرطٌ على السحب لا قيدٌ في الدفتر**، كالمحتجَز
    carried = await cancellation.carrier_dues_of(session, driver.id)
    reserve = Decimal("0.000")
    if driver.status is not DriverStatus.DEACTIVATED:
        limits = await settings_service.get_or_create_wallet_settings(
            session, user.country_code
        )
        reserve = limits.withdrawal_reserve_amount
    # **ولا ينزل تحت الصفر** (قِيس على جهازٍ حقيقيّ 2026-08-20: رصيدٌ صفرٌ
    # واحتجازُ ٥٫٠٠٠ أعطى «الرصيد المتاح −5.000 د.أ»). **و«المتاح» لا يكون
    # سالباً بالتعريف**: أقلُّ ما يمكن سحبُه لا شيء. والسالبُ يُقرأ **ديناً**،
    # والمحتجَزُ ليس ديناً — فالرقمُ يقول ما ليس واقعاً.
    #
    # **وهذا لا يناقض `earnings.net` الذي يُترك سالباً عمداً**: هناك السالبُ
    # **صحيح** (عمولةُ رحلاتٍ نقديةٍ بلا أرباحَ تقابلها، ومحفظتُه تنقص فعلاً)،
    # وإخفاؤه يترك الكبتنَ يرى رصيدَه ينزل بلا سبب. هنا السالبُ **غيرُ صحيح**:
    # لا أحدَ يطالبه بخمسة. القاعدةُ واحدةٌ في الحالتين — **يُعرض ما يقع**.
    return max(Decimal("0.000"), current - held - reserve - carried)


async def create_request(
    session: AsyncSession,
    *,
    driver: Driver,
    user: User,
    amount: Decimal,
    method: WithdrawalMethod,
) -> WithdrawalRequest:
    """طلب سحب جديد — يُرفض إن جاوز المتاح أو نزل عن الحد الأدنى."""
    amount = round_money(amount)
    if amount <= 0:
        raise InvalidInput("مبلغ السحب يجب أن يكون أكبر من صفر")

    wallet.require_not_frozen(user)

    if method == WithdrawalMethod.CLIQ and not (driver.cliq_alias or "").strip():
        raise InvalidInput("أضف alias كليك في ملفك قبل طلب السحب عبره")

    limits = await settings_service.get_or_create_wallet_settings(
        session, user.country_code
    )
    if amount < limits.min_withdrawal_amount:
        raise WalletLimitExceeded(
            f"الحد الأدنى للسحب {limits.min_withdrawal_amount}"
        )

    # القفل قبل الفحص: طلبان متزامنان لا يعبران معاً على نفس الرصيد
    await wallet.lock_wallet(session, user.id)
    if amount > await available_balance(session, driver, user):
        raise InsufficientBalance("الرصيد المتاح لا يكفي هذا الطلب")

    request = WithdrawalRequest(
        driver_id=driver.id,
        amount=amount,
        method=method,
        status=WithdrawalStatus.PENDING,
    )
    session.add(request)
    await session.flush()
    return request


async def _transition(
    session: AsyncSession,
    *,
    request: WithdrawalRequest,
    target: WithdrawalStatus,
    actor: User,
    note: str | None = None,
    reference: str | None = None,
) -> WithdrawalRequest:
    _require_transition(request, target)
    request.status = target
    request.processed_by = actor.id
    request.processed_at = _now()
    if note is not None:
        request.note = note
    if reference is not None:
        request.reference = reference

    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="withdrawal_request",
        entity_id=request.id,
        details={"status": target.value},
    )
    return request


async def approve(
    session: AsyncSession, *, request: WithdrawalRequest, actor: User
) -> WithdrawalRequest:
    """اعتماد الطلب — لا يخصم شيئاً، المال لم يخرج بعد."""
    return await _transition(
        session, request=request, target=WithdrawalStatus.APPROVED, actor=actor
    )


async def reject(
    session: AsyncSession,
    *,
    request: WithdrawalRequest,
    actor: User,
    note: str | None,
) -> WithdrawalRequest:
    return await _transition(
        session,
        request=request,
        target=WithdrawalStatus.REJECTED,
        actor=actor,
        note=note,
    )


async def pay_via_provider(
    session: AsyncSession,
    *,
    request: WithdrawalRequest,
    driver: Driver,
    owner: User,
    actor: User,
) -> tuple[WithdrawalRequest, PayoutState]:
    """تحويلٌ آلي عبر مزود payout ثم `paid` إن قال المزود «حوّلت».

    يحل محل يد المحاسب لا حكمه: الطلب يظل يمر بـ `approved` قبل هذا المسار.

    **النداء يقع تحت قفل صف الطلب، وهذا مقصود.** القاعدة العامة تمنع حجز صفٍّ
    طوال نداءٍ شبكي *حين يمكن أن يسبق النداءُ القفل* — وهنا لا يمكن: النداء
    نفسه يخرج المال، فتركُه خارج القفل يعني حوالتين لضغطتين متزامنتين. ونطاق
    القفل صفٌّ واحد، والمهلة مسقوفة في `payout/base.py`.

    `paid` لا تعني «طلبنا التحويل» بل «قال المزود إنه تم»: ما لم يُحسم يبقى
    `approved` بلا قيدٍ في الدفتر — ورصيدُ الكبتن ما زال محجوزاً بطلبه، فلا
    يُصرف مرتين ولا يضيع.
    """
    _require_transition(request, WithdrawalStatus.PAID)

    if request.method is not WithdrawalMethod.CLIQ:
        # لا عمود لحساب بنكي في `drivers` (SPEC القسم 4)، ووجهةٌ نخترعها
        # حوالةٌ تذهب إلى لا مكان. الحوالة البنكية تبقى يدوية
        raise InvalidInput("التحويل الآلي متاح لكليك وحدها — الحوالة البنكية يدوية")

    destination = (driver.cliq_alias or "").strip()
    if not destination:
        raise InvalidInput("لا يوجد alias كليك لهذا الكبتن")

    provider = await get_payout_provider(session, owner.country_code)
    state = await provider.send_payout(
        PayoutRequest(
            # مرجعُنا يذهب مع الحوالة: به يميّز المزود إعادةَ الطلب من طلبٍ ثانٍ
            reference=f"withdrawal:{request.id}",
            amount=request.amount,
            currency=currency_for_country(owner.country_code),
            method=request.method,
            beneficiary_name=owner.name,
            destination=destination,
        )
    )

    if state.settled and not state.paid:
        raise PayoutError(f"رفض المزود الحوالة: {state.status_text}")
    if not state.paid:
        # قيد التنفيذ: لا قيد ولا تعليم. يُعاد الاستعلام لاحقاً أو يُحوَّل يدوياً
        return request, state

    return (
        await mark_paid(
            session,
            request=request,
            owner=owner,
            actor=actor,
            reference=state.provider_ref,
        ),
        state,
    )


async def mark_paid(
    session: AsyncSession,
    *,
    request: WithdrawalRequest,
    owner: User,
    actor: User,
    reference: str,
) -> WithdrawalRequest:
    """المحاسب حوّل وسجّل المرجع → قيد `withdrawal` (SPEC القسم 9)."""
    _require_transition(request, WithdrawalStatus.PAID)
    if not reference.strip():
        raise InvalidInput("مرجع التحويل مطلوب لتعليم الطلب مدفوعاً")

    entry = await wallet.record(
        session,
        owner=owner,
        tx_type=WalletTransactionType.WITHDRAWAL,
        amount=-request.amount,
        reference=reference.strip(),
        created_by=actor.id,
        # الطلب نفسه مفتاح عدم التكرار — ضغطتان لا تخصمان مرتين
        idempotency_key=f"withdrawal:{request.id}",
    )
    request.transaction_id = entry.id
    return await _transition(
        session,
        request=request,
        target=WithdrawalStatus.PAID,
        actor=actor,
        reference=reference.strip(),
    )
