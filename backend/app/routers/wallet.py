from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.currency import currency_for_country
from app.core.deps import CurrentDriver, CurrentUser, DbSession, RedisDep, RiderUser
from app.core.exceptions import NotFound, RateLimited
from app.core.phone import InvalidPhoneNumber, resolve_phone
from app.models.enums import UserRole, WalletOwnerType, WalletTransactionType
from app.models.driver import Driver
from app.models.user import User
from app.models.enums import AccountKind
from app.schemas.payment import CardOrderOut, CardTopupCreate
from app.schemas.wallet import (
    CliqTopupCreate,
    CliqTopupOut,
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
from app.services import cancellation, commission_view
from app.services import (
    card_payments,
    cliq_topups,
    settings_service,
    topups,
    wallet as wallet_service,
    withdrawals,
)

router = APIRouter(prefix="/wallet", tags=["wallet"])

# البحث بالهاتف يكشف اسماً مقابل رقم — بسقفٍ لكل مستخدم كي لا يصير المسار
# أداةَ مسحٍ لدليل هواتف (SPEC القسم 14)
RECIPIENT_LOOKUP_LIMIT = 20
RECIPIENT_LOOKUP_WINDOW_SECONDS = 300

# فتحُ عملية شحنٍ بالبطاقة نداءٌ لمزود خارجي — سقفٌ يكفي المحاولات المعقولة
CARD_TOPUP_LIMIT = 10
CARD_TOPUP_WINDOW_SECONDS = 300


# **إعلانُ المحفظة** (SPEC §22): هذه المساراتُ يخدمها التطبيقان معاً
# (`CurrentUser`)، فمن حمل الدورين لا يقول الدورُ أيَّ محفظةٍ يعني. والإعلانُ
# اختياريٌّ عمداً: صاحبُ دورٍ واحدٍ لا يُطالَب بشيء، ولا يُخرج هذا أحداً من
# جلسةٍ قائمة — نفسُ منطق `app` في `app_scope`.
WalletChoice = Annotated[
    WalletOwnerType | None,
    Query(alias="wallet", description="أيُّ محفظةٍ تعني — لمن يحمل الدورين"),
]


async def _wallet_out(
    session, user: User, declared: WalletOwnerType | None = None
) -> WalletOut:
    owner_type = wallet_service.owner_type_for(user, declared=declared)
    return WalletOut(
        owner_id=user.id,
        owner_type=owner_type,
        balance=await wallet_service.balance(session, user.id, owner_type),
        currency=currency_for_country(user.country_code),
        frozen=wallet_service.is_frozen(user, owner_type),
        # **الاثنان معاً في نداءٍ واحد**: شاشةُ المحفظة تُفتح مرةً، ونداءٌ
        # ثانٍ لرقمٍ يُعرض بجانب الرصيد يجعل الشاشةَ ترسم نصفَ حقيقةٍ ثم تكملها
        cancellation_debt=(
            await cancellation.debt_of(session, user.id)
            if user.role is UserRole.RIDER
            else Decimal("0.000")
        ),
        pending_compensation=await _pending_compensation(session, user),
    )


async def _pending_compensation(session: AsyncSession, user: User) -> Decimal:
    """مستحقاتُ كبتنٍ لم تصل بعد — وصفرٌ لمن ليس كبتناً."""
    if user.role is not UserRole.DRIVER:
        return Decimal("0.000")
    driver = await session.scalar(select(Driver).where(Driver.user_id == user.id))
    if driver is None:
        return Decimal("0.000")
    return await cancellation.pending_for_driver(session, driver.id)


# ------------------------------------------------------------------ الرصيد


@router.get("/me", response_model=WalletOut)
async def get_my_wallet(
    user: CurrentUser, session: DbSession, wallet: WalletChoice = None
) -> WalletOut:
    """رصيد المحفظة وحالتها — للراكب والكبتن معاً.

    القراءة لا تمر بمفتاح `wallet_enabled`: رصيدٌ سابقٌ لإطفاء المفتاح يبقى
    مرئياً لصاحبه وإن تعذّر إنفاقه.
    """
    return await _wallet_out(session, user, wallet)


@router.get("/me/transactions", response_model=list[WalletTransactionOut])
async def list_my_transactions(
    user: CurrentUser,
    session: DbSession,
    wallet: WalletChoice = None,
    tx_type: WalletTransactionType | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[WalletTransactionOut]:
    entries = await wallet_service.history(
        session,
        user.id,
        wallet_service.owner_type_for(user, declared=wallet),
        limit=limit,
        offset=offset,
        tx_type=tx_type,
    )
    # **النسبةُ المجمَّدة تُلحَق باستعلامٍ ثانٍ على الصفحة** — لا ضمٍّ إلى الأول:
    # الرحلةُ الواحدةُ تحمل أكثرَ من قيد (أجرةٌ وعمولةٌ وسدادُ سلفة)، فالضمُّ
    # يضاعف الصفَّ ويُسقط قيوداً من صفحةٍ مسقوفة (قاعدةُ `services/ride_log.py`)
    return await commission_view.rows_with_percent(session, entries)


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

    # **حسابُ `taxo` وحدَه** (§D9.1، 1-أ/4): التحويلُ بين راكبين، والرقمُ قد
    # يحمل حسابَ زبونٍ أو تاجرٍ لا صلةَ له بالمحفظة المحوَّل إليها
    recipient = await session.scalar(
        select(User).where(
            User.phone == normalized, User.account_kind == AccountKind.TAXO
        )
    )
    if recipient is None or not recipient.has_role(UserRole.RIDER):
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
    payload: TopupRequestCreate,
    user: CurrentUser,
    session: DbSession,
    wallet: WalletChoice = None,
) -> TopupRequestOut:
    """طلب شحن كليك ينتظر تأكيد الإدارة — لا رصيد يتغيّر قبله."""
    request = await topups.create_request(
        session,
        owner=user,
        method=payload.method,
        amount=payload.amount,
        reference=payload.reference,
        declared=wallet,
    )
    await session.commit()
    return TopupRequestOut.model_validate(request)


@router.post(
    "/me/topups/card",
    response_model=CardOrderOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_card_topup(
    payload: CardTopupCreate,
    user: CurrentUser,
    session: DbSession,
    redis: RedisDep,
    wallet: WalletChoice = None,
) -> CardOrderOut:
    """شحن بالبطاقة — فوريٌّ آلي فلا يمر بطلبٍ ينتظر إنساناً (SPEC القسم 7).

    مساره الخاص لا `POST /me/topups`: ذاك يعيد صفَّ طلبٍ معلّق، وهذا يعيد رابط
    صفحة الدفع (أو حالاً نهائية إن كانت على بطاقة محفوظة). ردّان مختلفان
    لعمليتين مختلفتين — ودمجُهما في مسار واحد يعني حقولاً فارغة في كل ردّ.

    وله سقفٌ لكل مستخدم: كل نداءٍ يفتح عملية عند مزود خارجي، فمسارٌ بلا سقف
    مسارٌ يُغرق المزود بحسابنا (القسم 14).
    """
    limit = await rate_limit.hit(
        redis,
        f"wallet:card-topup:{user.id}",
        limit=CARD_TOPUP_LIMIT,
        window_seconds=CARD_TOPUP_WINDOW_SECONDS,
    )
    if not limit.allowed:
        raise RateLimited(retry_after=limit.retry_after)

    order = await card_payments.start_wallet_topup(
        session,
        owner=user,
        amount=payload.amount,
        save_card=payload.save_card,
        saved_card_id=payload.saved_card_id,
        declared=wallet,
    )
    await session.commit()
    return CardOrderOut.model_validate(order)


@router.post(
    "/me/topups/cliq",
    response_model=CliqTopupOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_cliq_topup(
    payload: CliqTopupCreate,
    user: CurrentUser,
    session: DbSession,
    redis: RedisDep,
    wallet: WalletChoice = None,
) -> CliqTopupOut:
    """شحن بكليك الآلي — رمز QR بالمبلغ ومرجعٍ يشهد عليه حساب التاجر.

    503 حين لا عقد acquirer مفعّل: القناة اليدوية (`POST /me/topups`) هي
    الطريق حينها، ولا تُدمج القناتان في مسارٍ واحد لأن ردّيهما مختلفان —
    ذاك طلبٌ ينتظر موظفاً وهذا رمزٌ يُمسح (SPEC القسم 7).
    """
    limit = await rate_limit.hit(
        redis,
        f"wallet:cliq-topup:{user.id}",
        limit=CARD_TOPUP_LIMIT,
        window_seconds=CARD_TOPUP_WINDOW_SECONDS,
    )
    if not limit.allowed:
        raise RateLimited(retry_after=limit.retry_after)

    order = await cliq_topups.start_topup(
        session, owner=user, amount=payload.amount, declared=wallet
    )
    await session.commit()
    return _cliq_out(order)


@router.get("/me/topups/cliq/{cart_id}", response_model=CliqTopupOut)
async def check_cliq_topup(
    cart_id: str, user: CurrentUser, session: DbSession, redis: RedisDep
) -> CliqTopupOut:
    """يسأل حساب التاجر عن الحوالة ويسوّي الشحن إن وصلت.

    ليس مسار احتياط: هو المسار — لا webhook في هذه القناة، والدفتر لا يتحرك
    إلا بجواب المزود للخلفية (نفس قاعدة قناة البطاقة، SPEC القسم 6.4).
    """
    order = await cliq_topups.order_for_user(session, cart_id, user)
    order = await cliq_topups.reconcile(session, order)
    await session.commit()
    # شحنٌ اكتمل قد يكون سدّد رسمَ إلغاءٍ معلّقاً (`CANCELLATION-FEE.md` §7)
    await cancellation.announce_settled_for_debtor(session, redis, user=user)
    return _cliq_out(order)


def _cliq_out(order) -> CliqTopupOut:
    return CliqTopupOut(
        cart_id=order.cart_id,
        amount=order.amount,
        currency=order.currency,
        status=order.status,
        qr_payload=order.qr_payload,
        deep_link=order.redirect_url,
        transaction_id=order.transaction_id,
    )


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
        frozen=wallet_service.is_frozen(user, WalletOwnerType.DRIVER),
        pending_compensation=await cancellation.pending_for_driver(session, driver.id),
        carrier_dues=await cancellation.carrier_dues_of(session, driver.id),
        available_for_withdrawal=available,
        min_withdrawal_amount=(
            limits.min_withdrawal_amount if limits is not None else Decimal("0.000")
        ),
        withdrawal_reserve_amount=(
            limits.withdrawal_reserve_amount
            if limits is not None
            else Decimal("0.000")
        ),
        commission_this_month=await commission_view.this_month(
            session,
            user_id=user.id,
            country=user.country_code,
            now=datetime.now(UTC),
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
