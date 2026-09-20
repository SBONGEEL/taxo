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
from app.core.deps import (
    FinanceManager,
    DbSession,
    ListReader,
    RedisDep,
    StaffUser,
)
from app.core.exceptions import InvalidInput, NotFound
from app.models.driver import Driver
from app.models.enums import (
    AuditAction,
    CountryCode,
    TopupRequestStatus,
    WalletOwnerType,
    WalletTransactionType,
    WithdrawalStatus,
)
from app.models.user import User
from app.models.wallet_freeze import WalletFreeze
from app.schemas.wallet import (
    AdjustmentCreate,
    AdminTopupCreate,
    MarkPaidRequest,
    CliqClaimOut,
    RejectClaimIn,
    ConfirmTopup,
    RejectRequest,
    TopupRequestOut,
    WalletFreezeRequest,
    WalletOut,
    WalletTransactionOut,
    WithdrawalOut,
    WithdrawalPayoutOut,
)
from app.schemas.admin_payment import AdminWithdrawalRow
from app.services import cliq_claims
from app.services import drivers as drivers_service
from app.services import cliq_subscriptions, commission_view
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


async def _wallet_out(
    session: AsyncSession, user: User, declared: WalletOwnerType | None = None
) -> WalletOut:
    owner_type = wallet_service.owner_type_for(user, declared=declared)
    return WalletOut(
        owner_id=user.id,
        owner_type=owner_type,
        balance=await wallet_service.balance(session, user.id, owner_type),
        currency=currency_for_country(user.country_code),
        frozen=wallet_service.is_frozen(user, owner_type),
    )


# ------------------------------------------------------------------ المحافظ


@router.get("/wallets/{user_id}", response_model=WalletOut)
async def get_wallet(
    user_id: uuid.UUID,
    _staff: StaffUser,
    session: DbSession,
    wallet: WalletOwnerType | None = Query(
        default=None,
        description="أيُّ المحفظتين — يلزم لحاملِ الدورين وحدَه",
    ),
) -> WalletOut:
    """محفظةُ حسابٍ — **والعمليةُ تعلن أيَّهما، لا دورُ صاحبها** (§22).

    **وكان هذا البابُ لا يعلن شيئاً** (عطبٌ قِيس 2026-09-02، §46٫٦): فحسابٌ
    يحمل الدورين يرتدّ `409 wallet_owner_undecided` **وتبقى بطاقةُ المحفظة على
    دوّارةٍ أبداً في درج الملفّ**. **والخلفيةُ كانت مُحقّة** — والناقصُ
    الإعلان.

    **والمُعامِلُ اختياريٌّ بقصد**: نداءٌ بلا `wallet` يسلك ما كان يسلكه حرفاً،
    **فصاحبُ الدور الواحد لا يُطالَب بما لا معنى له**، **وحاملُ الدورين يرتدّ
    بالخطأ المسمّى** لا بتخمين. **ولا يُمنح الإعلانُ شيئاً**: `owner_type_for`
    تفحص أن صاحبَه يملك دورَ تلك المحفظة وإلا رفضت.
    """
    return await _wallet_out(
        session, await _get_user(session, user_id), wallet
    )


@router.get(
    "/wallets/{user_id}/transactions", response_model=list[WalletTransactionOut]
)
async def list_wallet_transactions(
    user_id: uuid.UUID,
    _staff: StaffUser,
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    wallet: WalletOwnerType | None = Query(
        default=None,
        description="أيُّ المحفظتين — يلزم لحاملِ الدورين وحدَه",
    ),
) -> list[WalletTransactionOut]:
    """كشف حساب المحفظة كاملاً — أساس الفصل في النزاعات (SPEC القسم 13.4).

    **ويعلن جانبَه كما يعلنه `get_wallet`**: بطاقةُ الرصيد ودفترُها **سطحان
    لشيءٍ واحد**، **وإعلانُ أحدهما دون الآخر يعرض رصيدَ محفظةٍ فوق دفترِ
    الأخرى** — وهو أسوأُ من ٤٠٩.
    """
    user = await _get_user(session, user_id)
    entries = await wallet_service.history(
        session,
        user.id,
        wallet_service.owner_type_for(user, declared=wallet),
        limit=limit,
        offset=offset,
    )
    # **البانِي نفسُه الذي يخدم بابَ صاحب المحفظة** (الشكلُ الثامن): من يقرأ
    # كشفَ كبتنٍ من اللوحة يجب أن يرى ما يراه صاحبُه — نسبةَ العمولة المجمَّدة
    # وكلَّ ما يُحسب. وبانيان لحمولةٍ واحدةٍ يفترقان بحقلٍ يملؤه أحدُهما
    return await commission_view.rows_with_percent(session, entries)


@router.post("/wallets/{user_id}/freeze", response_model=WalletOut)
async def freeze_wallet(
    user_id: uuid.UUID,
    payload: WalletFreezeRequest,
    admin: FinanceManager,
    session: DbSession,
    wallet: WalletOwnerType | None = Query(
        default=None,
        description="أيُّ المحفظتين — يلزم لحاملِ الدورين وحدَه",
    ),
) -> WalletOut:
    """تجميد المحفظة دون حظر الحساب (SPEC القسم 7/13.3)."""
    return await _set_frozen(session, user_id, admin, True, payload.reason, wallet)


@router.post("/wallets/{user_id}/unfreeze", response_model=WalletOut)
async def unfreeze_wallet(
    user_id: uuid.UUID,
    payload: WalletFreezeRequest,
    admin: FinanceManager,
    session: DbSession,
    wallet: WalletOwnerType | None = Query(
        default=None,
        description="أيُّ المحفظتين — يلزم لحاملِ الدورين وحدَه",
    ),
) -> WalletOut:
    return await _set_frozen(session, user_id, admin, False, payload.reason, wallet)


async def _set_frozen(
    session: AsyncSession,
    user_id: uuid.UUID,
    admin: User,
    frozen: bool,
    reason: str | None,
    declared: WalletOwnerType | None = None,
) -> WalletOut:
    """**وإعلانُ المحفظة هنا كإعلانها في `get_wallet`** (§D6، 1-أ/2).

    **والتجميدُ صار للمحفظة نفسِها** (1-أ/6): الإعلانُ يختار **المحفظةَ التي
    تُجمَّد**، لا المحفظةَ التي يعرضها الجوابُ وحدَها. **والسكوتُ كما كان** —
    صاحبُ الدور الواحد لا يُسأل عمّا لا معنى له، وحاملُ الدورين يرتدّ بالخطأ
    المسمّى.

    **ووجودُ الصفِّ هو التجميد**: الرفعُ حذفُه، والتاريخُ في الأرشيف كما كان.
    """
    user = await _get_user(session, user_id)
    owner_type = wallet_service.owner_type_for(user, declared=declared)
    existing = next(
        (row for row in user.wallet_freezes if row.owner_type is owner_type), None
    )
    if frozen and existing is None:
        user.wallet_freezes.append(
            WalletFreeze(owner_type=owner_type, reason=reason, frozen_by=admin.id)
        )
    elif frozen and existing is not None:
        # تجميدٌ على تجميد: السببُ الأحدثُ هو ما يُقرأ في اللوحة
        existing.reason = reason
        existing.frozen_by = admin.id
    elif not frozen and existing is not None:
        user.wallet_freezes.remove(existing)

    # **والأرشيفُ يقول أيَّ محفظة** — وبغيره يُقرأ سجلُّ حاملِ الدورين بجوابين
    details: dict[str, object] = {"wallet_frozen": frozen, "wallet": owner_type.value}
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
    await session.refresh(user)
    return await _wallet_out(session, user, declared)


@router.post("/wallets/{user_id}/adjustments", response_model=WalletTransactionOut)
async def create_adjustment(
    user_id: uuid.UUID,
    payload: AdjustmentCreate,
    admin: FinanceManager,
    session: DbSession,
) -> WalletTransactionOut:
    """قيد تصحيح موجب أو سالب — المخرج الوحيد لتصحيح دفترٍ لا يُعدَّل.

    **والمحفظةُ تأتي من الطلب لا من دور صاحب الحساب** (SPEC §22): تصحيحُ
    المشرف **قرارٌ ماليٌّ لا سياقَ يقرّره** — لا رحلةَ ولا تطبيقَ فتحه ولا
    ختمَ على صفّ. فحاملُ الدورين يُسأل، **ولا يُخمَّن له**.
    """
    user = await _get_user(session, user_id)
    entry = await wallet_service.record(
        session,
        owner=user,
        owner_type=payload.wallet,
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
    # **`read.only`** (§٤٧٫١٠) — **والبتُّ تحتها `FinanceManager` كما كان**:
    # القراءةُ تُحرس باسمها، **ولا يتحرّك مالٌ بصلاحية قراءة**
    _reader: ListReader,
    session: DbSession,
    status_filter: TopupRequestStatus | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=120, description="اسمُ صاحبه أو رقمُه"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[TopupRequestOut]:
    requests = await topups.list_all(
        session, status=status_filter, limit=limit, offset=offset, q=q
    )
    return [TopupRequestOut.model_validate(request) for request in requests]


@router.post("/topups/{request_id}/confirm", response_model=TopupRequestOut)
async def confirm_topup(
    request_id: uuid.UUID,
    payload: ConfirmTopup,
    admin: FinanceManager,
    session: DbSession,
    redis: RedisDep,
) -> TopupRequestOut:
    """تأكيد وصول حوالة كليك/الكاش → الرصيد يتحرك الآن (SPEC القسم 7).

    **والمبلغُ مبلغُ المشرف** (قرارُ المالك 2026-08-29): ما قرأه في كشف
    الحساب، لا ما كتبه المستخدمُ في طلبه.
    """
    request = await topups.get_request(session, request_id, for_update=True)
    owner = await _get_user(session, request.owner_id)
    request = await topups.confirm(
        session, request=request, owner=owner, actor=admin, amount=payload.amount
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
    admin: FinanceManager,
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
    admin: FinanceManager,
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


@router.get("/withdrawals", response_model=list[AdminWithdrawalRow])
async def list_withdrawal_requests(
    _staff: StaffUser,
    session: DbSession,
    status_filter: WithdrawalStatus | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=120, description="اسمُ صاحبه أو رقمُه"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AdminWithdrawalRow]:
    """طلباتُ الصرف **ومعها أصحابُها** (§٤٧٫١٩، 2026-09-04).

    **وكان الجدولُ لا يعرض إنساناً البتّة**: المبلغُ والقناةُ والحالُ
    والتاريخ. **فالمشرفُ يوافق على صرفِ مالٍ ولا يرى لمن** — والبحثُ بالاسم
    كان يعمل (`driver_clause`) **والنتيجةُ لا تقول أيَّ اسمٍ طابقت**.

    **والأسماءُ تُقرأ باستعلامٍ ثانٍ لا بضمّ** — قرارُ `ride_log.payment_
    summaries` نفسُه: ضمٌّ على `drivers`+`users` يضاعف الصفوفَ إن تعدّدت
    المركبات، **فتصير صفحةُ الخمسين أقلَّ من خمسين صامتةً**.
    """
    requests = await withdrawals.list_all(
        session, status=status_filter, limit=limit, offset=offset, q=q
    )
    parties = await drivers_service.parties_of(
        session, [request.driver_id for request in requests]
    )
    return [
        AdminWithdrawalRow(
            **WithdrawalOut.model_validate(request).model_dump(),
            driver=parties[request.driver_id],
        )
        for request in requests
    ]


@router.post("/withdrawals/{request_id}/approve", response_model=WithdrawalOut)
async def approve_withdrawal(
    request_id: uuid.UUID, admin: FinanceManager, session: DbSession
) -> WithdrawalOut:
    request = await withdrawals.get_request(session, request_id, for_update=True)
    request = await withdrawals.approve(session, request=request, actor=admin)
    await session.commit()
    return WithdrawalOut.model_validate(request)


@router.post("/withdrawals/{request_id}/reject", response_model=WithdrawalOut)
async def reject_withdrawal(
    request_id: uuid.UUID,
    payload: RejectRequest,
    admin: FinanceManager,
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
    request_id: uuid.UUID, admin: FinanceManager, session: DbSession
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
    admin: FinanceManager,
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


# ------------------------------------------- مطالباتُ كليك اليدوية (اشتراكات)


@router.get("/cliq-claims", response_model=list[CliqClaimOut])
async def list_cliq_claims(
    _: FinanceManager, session: DbSession, country: CountryCode | None = None
) -> list[CliqClaimOut]:
    """المطالباتُ اليدويةُ المعلّقة — **ما ينتظر عينَ مشرف**."""
    rows = await cliq_subscriptions.list_pending(session, country=country)
    return [CliqClaimOut(**await cliq_claims.claim_row(session, row)) for row in rows]


@router.post("/cliq-claims/{order_id}/confirm", response_model=CliqClaimOut)
async def confirm_cliq_claim(
    order_id: uuid.UUID,
    payload: ConfirmTopup,
    admin: FinanceManager,
    session: DbSession,
) -> CliqClaimOut:
    """**تأكيدُ الدفع** — الخطوةُ الواحدةُ التي يقرأها الاشتراك.

    **والمبلغُ مبلغُ المشرف**، **ولا تفعيلَ بأقلَّ من الثمن**: ناقصٌ يُبقي
    المطالبةَ معلّقةً بفرقها مكتوباً، والمشرفُ يرفض أو ينتظر التكملة.
    """
    if payload.amount is None:
        raise InvalidInput("المبلغ الذي وصل مطلوب")
    order, _activated = await cliq_subscriptions.confirm_payment(
        session, order_id=order_id, actor=admin, credited=payload.amount
    )
    # **الحمولةُ تُبنى قبل الإيداع، والبانِي يجلب الدافعَ بنفسه** — فقراءةُ
    # علاقةٍ بعد `commit` (أو بعد `flush` يفرّغ ما قبله) تُحمَّل كسولاً خارج
    # السياق: `MissingGreenlet` بعينه. **وقِيس مرّتين في يومٍ واحد** —
    # أمسكه `test_two_confirmations_of_one_cliq_claim_activate_once`.
    row = await cliq_claims.claim_row(session, order)
    await session.commit()
    return CliqClaimOut(**row)


@router.get("/cliq-claims/declared", response_model=list[CliqClaimOut])
async def list_declared_claims(
    _: FinanceManager, session: DbSession, country: CountryCode | None = None
) -> list[CliqClaimOut]:
    """**من ضغط «حوّلتُ» وينتظر** — صفحةُ المدفوعات تقرأ هذا الباب.

    **وهي غيرُ `/cliq-claims`**: تلك تعرض **كلَّ من فتح الشاشة**، وهذه **من
    قال إنه حوّل**. ومن فتح ونسي لا ينتظر شيئاً، **ومن حوّل ينتظر تأكيداً
    لمالٍ خرج من حسابه**.

    **والأغراضُ كلُّها فيها** — اشتراكاً كانت أو دَيناً: صاحبُ المال ينتظر
    الجوابَ نفسَه، **وقائمتان لانتظارٍ واحدٍ تُنسى إحداهما**.
    """
    rows = await cliq_claims.declared_pending(session, country=country)
    return [CliqClaimOut(**await cliq_claims.claim_row(session, row)) for row in rows]


@router.post("/cliq-claims/{order_id}/reject", response_model=CliqClaimOut)
async def reject_cliq_claim(
    order_id: uuid.UUID,
    payload: RejectClaimIn,
    admin: FinanceManager,
    session: DbSession,
) -> CliqClaimOut:
    """**رفضٌ بسببٍ مكتوبٍ يُعرض على صاحبه** (قرارُ المالك 2026-09-01).

    **ولا رفضَ صامت**: من حوّل مالاً ورُفض طلبُه يستحق أن يعرف لماذا —
    و«مرفوض» وحدَها تُنتج مكالمةَ دعمٍ لا جواباً.
    """
    order = await cliq_claims.reject(
        session, order_id=order_id, reason=payload.reason
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="provider_order",
        entity_id=order.id,
        # **والسببُ يُسجَّل نصّاً** — وهو من الاستثناء المكتوب: سببٌ يكتبه
        # مشرفٌ **هو جوهرُ القيد**، لا قيمةَ حقلٍ تُخفى
        details={"action": "reject", "reason": payload.reason},
    )
    row = await cliq_claims.claim_row(session, order)
    await session.commit()
    return CliqClaimOut(**row)
