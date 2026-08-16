"""إدارة المحافظ من اللوحة (SPEC القسم 13.3/13.5).

القسمة بين الدورين ثابتة: `support` يقرأ ويفصل في النزاعات، و`admin` وحده
يحرّك مالاً — تأكيد شحنة، اعتماد سحب، تجميد محفظة، أو قيد تصحيح. وكل إجراء
منها يدخل سجل التدقيق في نفس معاملة التغيير.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.deps import AdminUser, DbSession, RedisDep, StaffUser
from app.core.exceptions import NotFound
from app.models.driver import Driver
from app.models.enums import (
    AuditAction,
    TopupRequestStatus,
    WalletTransactionType,
    WithdrawalStatus,
)
from app.models.user import User
from app.schemas.wallet import (
    AdjustmentCreate,
    AdminTopupCreate,
    MarkPaidRequest,
    RejectRequest,
    TopupRequestOut,
    WalletFreezeRequest,
    WalletOut,
    WalletTransactionOut,
    WithdrawalOut,
    WithdrawalPayoutOut,
)
from app.services import (
    audit,
    cancellation,
    topups,
    wallet as wallet_service,
    withdrawals,
)

router = APIRouter(prefix="/admin", tags=["admin"])


async def _get_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("الحساب غير موجود")
    return user


async def _wallet_out(session: AsyncSession, user: User) -> WalletOut:
    owner_type = wallet_service.owner_type_for(user)
    return WalletOut(
        owner_id=user.id,
        owner_type=owner_type,
        balance=await wallet_service.balance(session, user.id, owner_type),
        currency=currency_for_country(user.country_code),
        frozen=user.wallet_frozen,
    )


# ------------------------------------------------------------------ المحافظ


@router.get("/wallets/{user_id}", response_model=WalletOut)
async def get_wallet(
    user_id: uuid.UUID, _staff: StaffUser, session: DbSession
) -> WalletOut:
    return await _wallet_out(session, await _get_user(session, user_id))


@router.get(
    "/wallets/{user_id}/transactions", response_model=list[WalletTransactionOut]
)
async def list_wallet_transactions(
    user_id: uuid.UUID,
    _staff: StaffUser,
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[WalletTransactionOut]:
    """كشف حساب المحفظة كاملاً — أساس الفصل في النزاعات (SPEC القسم 13.4)."""
    user = await _get_user(session, user_id)
    entries = await wallet_service.history(
        session,
        user.id,
        wallet_service.owner_type_for(user),
        limit=limit,
        offset=offset,
    )
    return [WalletTransactionOut.model_validate(entry) for entry in entries]


@router.post("/wallets/{user_id}/freeze", response_model=WalletOut)
async def freeze_wallet(
    user_id: uuid.UUID,
    payload: WalletFreezeRequest,
    admin: AdminUser,
    session: DbSession,
) -> WalletOut:
    """تجميد المحفظة دون حظر الحساب (SPEC القسم 7/13.3)."""
    return await _set_frozen(session, user_id, admin, True, payload.reason)


@router.post("/wallets/{user_id}/unfreeze", response_model=WalletOut)
async def unfreeze_wallet(
    user_id: uuid.UUID,
    payload: WalletFreezeRequest,
    admin: AdminUser,
    session: DbSession,
) -> WalletOut:
    return await _set_frozen(session, user_id, admin, False, payload.reason)


async def _set_frozen(
    session: AsyncSession,
    user_id: uuid.UUID,
    admin: User,
    frozen: bool,
    reason: str | None,
) -> WalletOut:
    user = await _get_user(session, user_id)
    wallet_service.owner_type_for(user)
    user.wallet_frozen = frozen

    details: dict[str, object] = {"wallet_frozen": frozen}
    if reason:
        details["reason"] = reason
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="wallet",
        entity_id=user.id,
        details=details,
    )
    await session.commit()
    return await _wallet_out(session, user)


@router.post("/wallets/{user_id}/adjustments", response_model=WalletTransactionOut)
async def create_adjustment(
    user_id: uuid.UUID,
    payload: AdjustmentCreate,
    admin: AdminUser,
    session: DbSession,
) -> WalletTransactionOut:
    """قيد تصحيح موجب أو سالب — المخرج الوحيد لتصحيح دفترٍ لا يُعدَّل."""
    user = await _get_user(session, user_id)
    entry = await wallet_service.record(
        session,
        owner=user,
        tx_type=WalletTransactionType.ADJUSTMENT,
        amount=payload.amount,
        reference=payload.reason,
        created_by=admin.id,
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="wallet_transaction",
        entity_id=entry.id,
        # `details` لا يحمل قيماً — أسماء الحقول فقط (SPEC القسم 14)
        details={"type": WalletTransactionType.ADJUSTMENT.value},
    )
    await session.commit()
    return WalletTransactionOut.model_validate(entry)


# ------------------------------------------------------------ طلبات الشحن


@router.get("/topups", response_model=list[TopupRequestOut])
async def list_topup_requests(
    _staff: StaffUser,
    session: DbSession,
    status_filter: TopupRequestStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[TopupRequestOut]:
    requests = await topups.list_all(
        session, status=status_filter, limit=limit, offset=offset
    )
    return [TopupRequestOut.model_validate(request) for request in requests]


@router.post("/topups/{request_id}/confirm", response_model=TopupRequestOut)
async def confirm_topup(
    request_id: uuid.UUID, admin: AdminUser, session: DbSession, redis: RedisDep
) -> TopupRequestOut:
    """تأكيد وصول حوالة كليك/الكاش → الرصيد يتحرك الآن (SPEC القسم 7)."""
    request = await topups.get_request(session, request_id, for_update=True)
    owner = await _get_user(session, request.owner_id)
    request = await topups.confirm(
        session, request=request, owner=owner, actor=admin
    )
    await session.commit()
    # شحنٌ اكتمل قد يكون سدّد رسمَ إلغاءٍ معلّقاً (`CANCELLATION-FEE.md` §7)،
    # فيُخبَر من وصله مالُه — **بعد الـcommit** كبقية البثّ
    await cancellation.announce_settled_for_debtor(session, redis, user=owner)
    return TopupRequestOut.model_validate(request)


@router.post("/topups/{request_id}/reject", response_model=TopupRequestOut)
async def reject_topup(
    request_id: uuid.UUID,
    payload: RejectRequest,
    admin: AdminUser,
    session: DbSession,
) -> TopupRequestOut:
    request = await topups.get_request(session, request_id, for_update=True)
    request = await topups.reject(
        session, request=request, actor=admin, note=payload.note
    )
    await session.commit()
    return TopupRequestOut.model_validate(request)


@router.post("/wallets/{user_id}/topups", response_model=TopupRequestOut)
async def create_staff_topup(
    user_id: uuid.UUID,
    payload: AdminTopupCreate,
    admin: AdminUser,
    session: DbSession,
    redis: RedisDep,
) -> TopupRequestOut:
    """شحن كاش من نقطة معتمدة — يُنشأ ويُؤكَّد معاً (SPEC القسم 7)."""
    owner = await _get_user(session, user_id)
    request = await topups.create_confirmed(
        session,
        owner=owner,
        actor=admin,
        method=payload.method,
        amount=payload.amount,
        reference=payload.reference,
    )
    await session.commit()
    await cancellation.announce_settled_for_debtor(session, redis, user=owner)
    return TopupRequestOut.model_validate(request)


# ------------------------------------------------------------ طلبات السحب


@router.get("/withdrawals", response_model=list[WithdrawalOut])
async def list_withdrawal_requests(
    _staff: StaffUser,
    session: DbSession,
    status_filter: WithdrawalStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[WithdrawalOut]:
    requests = await withdrawals.list_all(
        session, status=status_filter, limit=limit, offset=offset
    )
    return [WithdrawalOut.model_validate(request) for request in requests]


@router.post("/withdrawals/{request_id}/approve", response_model=WithdrawalOut)
async def approve_withdrawal(
    request_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> WithdrawalOut:
    request = await withdrawals.get_request(session, request_id, for_update=True)
    request = await withdrawals.approve(session, request=request, actor=admin)
    await session.commit()
    return WithdrawalOut.model_validate(request)


@router.post("/withdrawals/{request_id}/reject", response_model=WithdrawalOut)
async def reject_withdrawal(
    request_id: uuid.UUID,
    payload: RejectRequest,
    admin: AdminUser,
    session: DbSession,
) -> WithdrawalOut:
    request = await withdrawals.get_request(session, request_id, for_update=True)
    request = await withdrawals.reject(
        session, request=request, actor=admin, note=payload.note
    )
    await session.commit()
    return WithdrawalOut.model_validate(request)


@router.post("/withdrawals/{request_id}/payout", response_model=WithdrawalPayoutOut)
async def payout_withdrawal(
    request_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> WithdrawalPayoutOut:
    """تحويلٌ آلي عبر مزود payout بدل حوالةٍ يدوية (SPEC القسم 9/15-أ).

    القفلُ قبل النداء عمداً: النداء نفسه يخرج المال، فضغطتان متزامنتان بلا
    قفلٍ حوالتان. و`paid` لا تُعلَّم إلا إن قال المزود «حوّلت» — وما دون ذلك
    يبقى الطلب `approved` بلا قيدٍ في الدفتر.
    """
    request = await withdrawals.get_request(session, request_id, for_update=True)
    driver = await session.get(Driver, request.driver_id)
    if driver is None:  # pragma: no cover - يمنعه المفتاح الأجنبي
        raise NotFound("الكبتن غير موجود")

    owner = await _get_user(session, driver.user_id)
    request, state = await withdrawals.pay_via_provider(
        session, request=request, driver=driver, owner=owner, actor=admin
    )
    await session.commit()
    await session.refresh(request)
    return WithdrawalPayoutOut(
        request=WithdrawalOut.model_validate(request),
        paid=state.paid,
        provider_status=state.status_text,
    )


@router.post("/withdrawals/{request_id}/paid", response_model=WithdrawalOut)
async def mark_withdrawal_paid(
    request_id: uuid.UUID,
    payload: MarkPaidRequest,
    admin: AdminUser,
    session: DbSession,
) -> WithdrawalOut:
    """المحاسب حوّل وسجّل المرجع → قيد `withdrawal` يُكتب الآن."""
    request = await withdrawals.get_request(session, request_id, for_update=True)
    driver = await session.get(Driver, request.driver_id)
    if driver is None:  # pragma: no cover - يمنعه المفتاح الأجنبي
        raise NotFound("الكبتن غير موجود")

    # محفظة الكبتن مفتاحها `user_id` لا `driver_id` — القيود على `users.id`
    owner = await _get_user(session, driver.user_id)
    request = await withdrawals.mark_paid(
        session,
        request=request,
        owner=owner,
        actor=admin,
        reference=payload.reference,
    )
    await session.commit()
    return WithdrawalOut.model_validate(request)
