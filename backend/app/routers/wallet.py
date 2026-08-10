from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.core import rate_limit
from app.core.currency import currency_for_country
from app.core.deps import CurrentDriver, CurrentUser, DbSession, RedisDep, RiderUser
from app.core.exceptions import NotFound, RateLimited
from app.core.phone import InvalidPhoneNumber, resolve_phone
from app.models.enums import UserRole, WalletOwnerType, WalletTransactionType
from app.models.user import User
from app.schemas.wallet import (
    DriverWalletOut,
    TopupRequestCreate,
    TopupRequestOut,
    TransferRecipientOut,
    TransferRequest,
    WalletOut,
    WalletTransactionOut,
    WithdrawalCreate,
    WithdrawalOut,
)
from app.services import settings_service, topups, wallet as wallet_service, withdrawals

router = APIRouter(prefix="/wallet", tags=["wallet"])

# البحث بالهاتف يكشف اسماً مقابل رقم — بسقفٍ لكل مستخدم كي لا يصير المسار
# أداةَ مسحٍ لدليل هواتف (SPEC القسم 14)
RECIPIENT_LOOKUP_LIMIT = 20
RECIPIENT_LOOKUP_WINDOW_SECONDS = 300


async def _wallet_out(session, user: User) -> WalletOut:
    owner_type = wallet_service.owner_type_for(user)
    return WalletOut(
        owner_id=user.id,
        owner_type=owner_type,
        balance=await wallet_service.balance(session, user.id, owner_type),
        currency=currency_for_country(user.country_code),
        frozen=user.wallet_frozen,
    )


# ------------------------------------------------------------------ الرصيد


@router.get("/me", response_model=WalletOut)
async def get_my_wallet(user: CurrentUser, session: DbSession) -> WalletOut:
    """رصيد المحفظة وحالتها — للراكب والكبتن معاً.

    القراءة لا تمر بمفتاح `wallet_enabled`: رصيدٌ سابقٌ لإطفاء المفتاح يبقى
    مرئياً لصاحبه وإن تعذّر إنفاقه.
    """
    return await _wallet_out(session, user)


@router.get("/me/transactions", response_model=list[WalletTransactionOut])
async def list_my_transactions(
    user: CurrentUser,
    session: DbSession,
    tx_type: WalletTransactionType | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[WalletTransactionOut]:
    entries = await wallet_service.history(
        session,
        user.id,
        wallet_service.owner_type_for(user),
        limit=limit,
        offset=offset,
        tx_type=tx_type,
    )
    return [WalletTransactionOut.model_validate(entry) for entry in entries]


# ------------------------------------------------------------------ التحويل


@router.get("/transfer/recipient", response_model=TransferRecipientOut)
async def lookup_transfer_recipient(
    rider: RiderUser,
    session: DbSession,
    redis: RedisDep,
    phone: str = Query(min_length=6, max_length=20),
) -> TransferRecipientOut:
    """اسم صاحب الرقم للتأكيد قبل التحويل (SPEC القسم 7)."""
    await wallet_service.require_transfer_enabled(session, rider.country_code)

    limit = await rate_limit.hit(
        redis,
        f"wallet:recipient:{rider.id}",
        limit=RECIPIENT_LOOKUP_LIMIT,
        window_seconds=RECIPIENT_LOOKUP_WINDOW_SECONDS,
    )
    if not limit.allowed:
        raise RateLimited(retry_after=limit.retry_after)

    recipient = await _resolve_rider(session, phone, rider)
    return TransferRecipientOut(phone=recipient.phone, name=recipient.name)


@router.post("/me/transfers", response_model=WalletTransactionOut)
async def transfer_to_rider(
    payload: TransferRequest, rider: RiderUser, session: DbSession
) -> WalletTransactionOut:
    """تحويل P2P — قيدان ذرّيان في معاملة واحدة (SPEC القسم 7/14)."""
    recipient = await _resolve_rider(session, payload.recipient_phone, rider)
    entry = await wallet_service.transfer(
        session,
        sender=rider,
        recipient=recipient,
        amount=payload.amount,
        idempotency_key=payload.idempotency_key,
    )
    await session.commit()
    return WalletTransactionOut.model_validate(entry)


async def _resolve_rider(session, phone: str, sender: User) -> User:
    """المستلم بالهاتف — يُطبَّع برمز دولة المرسل قبل أي استعلام.

    404 لا 403 لغير الراكب: وجودُ رقمٍ في النظام ودورُ صاحبه ليسا معلومة
    يستحقها من يجرّب أرقاماً.
    """
    try:
        normalized = resolve_phone(phone, sender.country_code)
    except InvalidPhoneNumber as exc:
        raise NotFound("لا يوجد حساب بهذا الرقم") from exc

    recipient = await session.scalar(select(User).where(User.phone == normalized))
    if recipient is None or recipient.role != UserRole.RIDER:
        raise NotFound("لا يوجد حساب بهذا الرقم")
    return recipient


# -------------------------------------------------------------------- الشحن


@router.get("/me/topups", response_model=list[TopupRequestOut])
async def list_my_topups(
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[TopupRequestOut]:
    requests = await topups.list_for_owner(
        session, user.id, limit=limit, offset=offset
    )
    return [TopupRequestOut.model_validate(request) for request in requests]


@router.post(
    "/me/topups", response_model=TopupRequestOut, status_code=status.HTTP_201_CREATED
)
async def create_topup_request(
    payload: TopupRequestCreate, user: CurrentUser, session: DbSession
) -> TopupRequestOut:
    """طلب شحن كليك ينتظر تأكيد الإدارة — لا رصيد يتغيّر قبله."""
    request = await topups.create_request(
        session,
        owner=user,
        method=payload.method,
        amount=payload.amount,
        reference=payload.reference,
    )
    await session.commit()
    return TopupRequestOut.model_validate(request)


# -------------------------------------------------------------------- السحب


@router.get("/me/driver", response_model=DriverWalletOut)
async def get_my_driver_wallet(
    driver: CurrentDriver, user: CurrentUser, session: DbSession
) -> DriverWalletOut:
    """محفظة الكبتن مع المتاح فعلاً للسحب (SPEC القسم 9)."""
    limits = await settings_service.get_wallet_settings(session, user.country_code)
    available = await withdrawals.available_balance(session, driver, user)

    return DriverWalletOut(
        owner_id=user.id,
        owner_type=WalletOwnerType.DRIVER,
        balance=await wallet_service.balance(
            session, user.id, WalletOwnerType.DRIVER
        ),
        currency=currency_for_country(user.country_code),
        frozen=user.wallet_frozen,
        available_for_withdrawal=available,
        min_withdrawal_amount=(
            limits.min_withdrawal_amount if limits is not None else Decimal("0.000")
        ),
    )


@router.get("/me/withdrawals", response_model=list[WithdrawalOut])
async def list_my_withdrawals(
    driver: CurrentDriver,
    session: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[WithdrawalOut]:
    requests = await withdrawals.list_for_driver(
        session, driver.id, limit=limit, offset=offset
    )
    return [WithdrawalOut.model_validate(request) for request in requests]


@router.post(
    "/me/withdrawals", response_model=WithdrawalOut, status_code=status.HTTP_201_CREATED
)
async def request_withdrawal(
    payload: WithdrawalCreate,
    driver: CurrentDriver,
    user: CurrentUser,
    session: DbSession,
) -> WithdrawalOut:
    """طلب سحب — للكباتن وحدهم؛ الراكب يشحن ولا يسحب (SPEC القسم 7)."""
    request = await withdrawals.create_request(
        session, driver=driver, user=user, amount=payload.amount, method=payload.method
    )
    await session.commit()
    return WithdrawalOut.model_validate(request)
