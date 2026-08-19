"""شحن محفظة الراكب (SPEC القسم 7).

قنوات الشحن ثلاث: Telr فوري آلي (المرحلة 6)، وكليك تحويلاً على alias الشركة
يُدخل الراكب مرجعه ثم تؤكده الإدارة، وكاش يشحنه موظف من اللوحة. القناتان
الأخيرتان تمران من هنا لأن لا API يؤكدهما — يؤكدهما إنسان.

**لا رصيد يتغيّر إلا عند التأكيد.** الطلب المعلّق أثرٌ نصّي لا مالي، فالقيد
يُكتب لحظة `confirmed` وحدها.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInput, InvalidStatusTransition, NotFound
from app.models.enums import (
    WalletOwnerType,
    AuditAction,
    TopupMethod,
    TopupRequestStatus,
    WalletTransactionType,
)
from app.models.user import User
from app.models.wallet import WalletTopupRequest
from app.services import audit, cancellation, wallet
from app.services.pricing import round_money

# القنوات التي يفتح الراكب طلبها بنفسه: كليك وحدها. الكاش يُنشئه الموظف
# مؤكداً عند استلام المال، والبطاقة لا تمر بطلبٍ أصلاً (شحن فوري، المرحلة 6).
RIDER_METHODS: tuple[TopupMethod, ...] = (TopupMethod.CLIQ,)

# ما يُنشئه الموظف من اللوحة نيابةً عن الراكب
STAFF_METHODS: tuple[TopupMethod, ...] = (TopupMethod.CASH, TopupMethod.CLIQ)


def _now() -> datetime:
    return datetime.now(UTC)


async def get_request(
    session: AsyncSession, request_id: uuid.UUID, *, for_update: bool = False
) -> WalletTopupRequest:
    """`for_update` إلزامي لكل مسار يغيّر الحالة.

    تأكيدان متزامنان يقرآن `pending` معاً قبل أن يُثبّت أحدهما تغييره، فيمر
    كلاهما من فحص الحالة. مفتاح عدم التكرار يمنع الشحن مرتين، لكن حارس
    الحالة يجب أن يحرس بنفسه لا أن يتّكل على الذي بعده.
    """
    stmt = select(WalletTopupRequest).where(WalletTopupRequest.id == request_id)
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)

    request = await session.scalar(stmt)
    if request is None:
        raise NotFound("طلب الشحن غير موجود")
    return request


async def list_for_owner(
    session: AsyncSession, owner_id: uuid.UUID, *, limit: int, offset: int
) -> Sequence[WalletTopupRequest]:
    stmt = (
        select(WalletTopupRequest)
        .where(WalletTopupRequest.owner_id == owner_id)
        .order_by(WalletTopupRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return (await session.scalars(stmt)).all()


async def list_all(
    session: AsyncSession,
    *,
    status: TopupRequestStatus | None,
    limit: int,
    offset: int,
) -> Sequence[WalletTopupRequest]:
    stmt = select(WalletTopupRequest).order_by(WalletTopupRequest.created_at.desc())
    if status is not None:
        stmt = stmt.where(WalletTopupRequest.status == status)
    return (await session.scalars(stmt.limit(limit).offset(offset))).all()


async def create_request(
    session: AsyncSession,
    *,
    owner: User,
    method: TopupMethod,
    amount: Decimal,
    reference: str | None,
    declared: WalletOwnerType | None = None,
) -> WalletTopupRequest:
    """طلب شحن يفتحه الراكب بنفسه بعد أن يحوّل على alias الشركة."""
    if method not in RIDER_METHODS:
        raise InvalidInput("قناة الشحن هذه لا تُطلب من التطبيق")
    # مرجع الحوالة هو كل ما تملكه الإدارة للمطابقة — طلبٌ بلا مرجع لا يُؤكَّد
    if not (reference or "").strip():
        raise InvalidInput("مرجع الحوالة مطلوب")

    await wallet.require_wallet_enabled(session, owner.country_code)
    wallet.require_not_frozen(owner)
    # **يُعلَن ويُختم**: المحفظةُ تُقرَّر هنا وتُقرأ عند التأكيد، فلا تُشتقّ
    # من دورٍ قد يكون دورين يومَها (SPEC §22)
    owner_type = wallet.owner_type_for(owner, declared=declared)

    amount = _validated_amount(amount)
    request = WalletTopupRequest(
        owner_id=owner.id,
        owner_type=owner_type,
        method=method,
        amount=amount,
        reference=reference.strip(),
        status=TopupRequestStatus.PENDING,
    )
    session.add(request)
    await session.flush()
    return request


def _validated_amount(amount: Decimal) -> Decimal:
    amount = round_money(amount)
    if amount <= 0:
        raise InvalidInput("مبلغ الشحن يجب أن يكون أكبر من صفر")
    return amount


async def confirm(
    session: AsyncSession,
    *,
    request: WalletTopupRequest,
    owner: User,
    actor: User,
) -> WalletTopupRequest:
    """تأكيد الإدارة → قيد `topup` في نفس المعاملة (SPEC القسم 7/14)."""
    if request.status != TopupRequestStatus.PENDING:
        raise InvalidStatusTransition()

    wallet.require_not_frozen(owner)

    entry = await wallet.record(
        session,
        owner=owner,
        # **من الصفِّ لا من الدور**: الطلبُ يحمل محفظتَه منذ إنشائه
        owner_type=request.owner_type,
        tx_type=WalletTransactionType.TOPUP,
        amount=request.amount,
        reference=request.reference,
        created_by=actor.id,
        # الطلب نفسه مفتاح عدم التكرار: تأكيدان متزامنان لا يشحنان مرتين
        idempotency_key=f"topup:{request.id}",
    )

    request.status = TopupRequestStatus.CONFIRMED
    request.processed_by = actor.id
    request.processed_at = _now()
    request.transaction_id = entry.id

    # **ودَينُ إلغاءٍ يُسدَّد لحظةَ اكتمال الشحن** (`CANCELLATION-FEE.md` §7):
    # «فوريٌّ كلما دخل المالُ المنصّة» — بلا مراجعةٍ إداريةٍ وبلا دورةٍ مجدولة،
    # وإلا سأل الكبتنُ الدعمَ عن مالٍ في الطريق
    await cancellation.on_wallet_funded(session, user=owner)

    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="wallet_topup_request",
        entity_id=request.id,
        details={"status": request.status.value, "method": request.method.value},
    )
    return request


async def reject(
    session: AsyncSession,
    *,
    request: WalletTopupRequest,
    actor: User,
    note: str | None,
) -> WalletTopupRequest:
    if request.status != TopupRequestStatus.PENDING:
        raise InvalidStatusTransition()

    request.status = TopupRequestStatus.REJECTED
    request.processed_by = actor.id
    request.processed_at = _now()
    request.note = note

    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="wallet_topup_request",
        entity_id=request.id,
        details={"status": request.status.value},
    )
    return request


async def create_confirmed(
    session: AsyncSession,
    *,
    owner: User,
    actor: User,
    method: TopupMethod,
    amount: Decimal,
    reference: str | None,
    declared: WalletOwnerType | None = None,
) -> WalletTopupRequest:
    """شحن يُنشئه الموظف مؤكداً — نقطة الكاش المعتمدة (SPEC القسم 7).

    يمر بجدول الطلبات وإن لم ينتظر شيئاً: مصدرُ كل شحنة واحد، فلا يظهر في
    اللوحة رصيدٌ لا طلبَ وراءه.
    """
    if method not in STAFF_METHODS:
        raise InvalidInput("قناة الشحن هذه لا تُنشأ من اللوحة")

    await wallet.require_wallet_enabled(session, owner.country_code)
    owner_type = wallet.owner_type_for(owner, declared=declared)
    request = WalletTopupRequest(
        owner_id=owner.id,
        owner_type=owner_type,
        method=method,
        amount=_validated_amount(amount),
        reference=(reference or "").strip() or None,
        status=TopupRequestStatus.PENDING,
    )
    session.add(request)
    await session.flush()
    return await confirm(session, request=request, owner=owner, actor=actor)
