"""نظامُ الدفع الجديد — طرقُ الدفع صفوفاً لكلِّ دولة، والدفعاتُ بحالاتها الخمس (SPEC §٧٣-أ/٥، §٧٣-هـ المرحلة ١).

**لا رصيدَ يتغيّر إلا عند الاعتماد** — كالشحن اليدويّ القائم حرفاً (`services/topups.py`): الطلبُ المعلَّقُ أثرٌ نصّيٌّ لا ماليّ، والقيدُ
يُكتب لحظةَ `approved` وحدَها، **بمبلغ الموظّف الماليّ لا دعوى المستخدم**.

**و«الدفعةُ لا تُحتسب مرّتين» بثلاثة حرّاسٍ مستقلّين** (§٧٣-هـ/٦): قفلُ صفِّ الطلب قبل فحص حالته · مفتاحُ عدم التكرار في الدفتر ·
فهرسان فريدان جزئيّان للمرجع ولبصمة الإيصال. **ولا يتّكل حارسٌ على الذي بعده** (`CLAUDE.md`).

**وترتيبُ الأقفال قاعدةُ المشروع نفسُها**: صفُّ الطلب ← صفُّ الكبتن (للاشتراك) ← قفلُ المحفظة.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import amount_text, currency_for_country
from app.core.exceptions import (
    AppError,
    Conflict,
    FeatureDisabled,
    InsufficientBalance,
    InvalidInput,
    InvalidStatusTransition,
    NotFound,
)
from app.models.driver import Driver
from app.models.enums import (
    AuditAction,
    CountryCode,
    FeatureKey,
    PaymentProviderKind,
    PaymentRequestPurpose,
    PaymentRequestStatus,
    WalletOwnerType,
    WalletTransactionType,
)
from app.models.payment_request import PaymentProvider, PaymentRequest
from app.models.user import User
from app.services import (
    admin_search,
    audit,
    cancellation,
    rounding,
    settings_service,
    test_accounts,
    verification,
    wallet,
)
from app.services import drivers as drivers_service
from app.services.pricing import as_money

#: **ما إيصالُه إجباريّ** (قرارُ المالك: «صورةُ الإيصال إجباريّةٌ في التحويلات») — **ولا يُضبط من اللوحة**: حارسٌ لا تفضيل
TRANSFER_KINDS: frozenset[PaymentProviderKind] = frozenset(
    {PaymentProviderKind.BANK_TRANSFER, PaymentProviderKind.PHONE_NUMBER}
)

#: أقصرُ سببٍ يُقبل لرفضٍ أو ردٍّ أو إلغاء — **سببٌ من حرفين ليس سبباً يقرؤه صاحبُ الدفعة**
MIN_REASON = 3


class PaymentAlreadySubmitted(Conflict):
    """**هذا التحويلُ قُدِّم من قبل** — مرجعُه أو صورةُ إيصاله في طلبٍ معلَّقٍ أو معتمدٍ للطريقة نفسِها (§٧٣-هـ/٦)."""

    code = "payment_already_submitted"
    message = "هذا التحويلُ قُدِّم من قبل — مرجعُه أو إيصالُه في طلبٍ آخر"


def _now() -> datetime:
    return datetime.now(UTC)


def requires_receipt(provider: PaymentProvider) -> bool:
    """**التحويلُ اليدويُّ إيصالُه إجباريّ** — والوسيطُ الآليُّ يشهد له الـwebhook لا الصورة."""
    return provider.integration is None and provider.kind in TRANSFER_KINDS


def reference_key(reference: str | None) -> str | None:
    """**المرجعُ مطبَّعاً للفهرس الفريد** — بلا مسافاتٍ وبحروفٍ صغيرة: «AB 12» و«ab12» تحويلٌ واحد."""
    if reference is None:
        return None
    key = "".join(reference.split()).casefold()
    return key or None


def _reason(text: str | None, *, field: str) -> str:
    value = (text or "").strip()
    if len(value) < MIN_REASON:
        raise InvalidInput("اكتب السببَ كما سيقرؤه صاحبُ الدفعة", field=field)
    return value[:500]


async def is_enabled(session: AsyncSession, country: CountryCode) -> bool:
    return await settings_service.is_feature_enabled(session, country, FeatureKey.PAYMENT_REQUESTS_ENABLED)


async def require_enabled(session: AsyncSession, country: CountryCode) -> None:
    """**مطفأً لا يُفتح طلبٌ ولا تُعرض طريقة** (§٧٣-هـ/٩) — والأردنُ وليبيا مطفآن فلا يمسّهما شيءٌ هنا."""
    if not await is_enabled(session, country):
        raise FeatureDisabled("الدفعُ بهذه الطرق غيرُ متاحٍ في بلدك الآن")


# ------------------------------------------------------------------ الطرق


async def providers_for(
    session: AsyncSession, country: CountryCode, purpose: PaymentRequestPurpose | None = None
) -> list[PaymentProvider]:
    """طرقُ الدفع **المفعَّلة** لسوقٍ ولغرضٍ — بترتيب اللوحة."""
    stmt = select(PaymentProvider).where(
        PaymentProvider.country_code == country, PaymentProvider.enabled.is_(True)
    )
    if purpose is PaymentRequestPurpose.WALLET_TOPUP:
        stmt = stmt.where(PaymentProvider.for_topup.is_(True))
    elif purpose is PaymentRequestPurpose.SUBSCRIPTION:
        stmt = stmt.where(PaymentProvider.for_subscription.is_(True))
    stmt = stmt.order_by(PaymentProvider.sort_order, PaymentProvider.name)
    return list((await session.scalars(stmt)).all())


async def all_providers(session: AsyncSession, country: CountryCode | None) -> list[PaymentProvider]:
    """كلُّ الطرق — للّوحة، مفعَّلةً وموقوفة."""
    stmt = select(PaymentProvider).order_by(
        PaymentProvider.country_code, PaymentProvider.sort_order, PaymentProvider.name
    )
    if country is not None:
        stmt = stmt.where(PaymentProvider.country_code == country)
    return list((await session.scalars(stmt)).all())


async def get_provider(
    session: AsyncSession, provider_id: uuid.UUID, *, for_update: bool = False
) -> PaymentProvider:
    stmt = select(PaymentProvider).where(PaymentProvider.id == provider_id)
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    provider = await session.scalar(stmt)
    if provider is None:
        raise NotFound("طريقةُ الدفع غيرُ موجودة")
    return provider


async def available_provider(session: AsyncSession, provider_id: uuid.UUID, country: CountryCode) -> PaymentProvider:
    """**طريقةٌ مفعَّلةٌ في سوق السائل** — ومن سوقٍ آخر ٤٠٤ لا ٤٠٣: ليست معلومةً يستحقّها من يجرّب المعرّفات."""
    provider = await get_provider(session, provider_id)
    if provider.country_code != country or not provider.enabled:
        raise NotFound("طريقةُ الدفع غيرُ متاحة")
    return provider


# ------------------------------------------------------------------ الطلبات


async def get_request(
    session: AsyncSession, request_id: uuid.UUID, *, for_update: bool = False
) -> PaymentRequest:
    """**`for_update` إلزاميٌّ لكلِّ مسارٍ يغيّر الحالة** — قبل فحصها، لا بعده (`CLAUDE.md`).

    اعتمادان متزامنان يقرآن `pending` معاً قبل أن يثبّت أحدُهما، فيمرّ كلاهما من فحص الحالة؛ ومفتاحُ الدفتر يمنع القيدَ الثاني،
    **لكنّ حارسَ الحالة يحرس بنفسه** — والقيدُ ليس وحدَه ما يملكه القفل: **حالةُ الطلب** (معتمدٌ ومرفوضٌ معاً) هي ما يملكه وحدَه.
    """
    stmt = select(PaymentRequest).where(PaymentRequest.id == request_id)
    if for_update:
        stmt = stmt.with_for_update(of=PaymentRequest).execution_options(populate_existing=True)
    request = await session.scalar(stmt)
    if request is None:
        raise NotFound("طلبُ الدفع غيرُ موجود")
    return request


async def list_for_owner(
    session: AsyncSession, owner_id: uuid.UUID, *, limit: int, offset: int
) -> Sequence[PaymentRequest]:
    stmt = (
        select(PaymentRequest)
        .where(PaymentRequest.user_id == owner_id)
        .order_by(PaymentRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return (await session.scalars(stmt)).all()


async def list_all(
    session: AsyncSession,
    *,
    status: PaymentRequestStatus | None,
    country: CountryCode | None,
    q: str | None,
    limit: int,
    offset: int,
) -> Sequence[PaymentRequest]:
    stmt = select(PaymentRequest).order_by(PaymentRequest.created_at.desc())
    if status is not None:
        stmt = stmt.where(PaymentRequest.status == status)
    if country is not None:
        stmt = stmt.where(PaymentRequest.country_code == country)
    term = admin_search.normalize(q)
    if term is not None:
        # **صاحبُها أو مرجعُها** — كطابور الشحن القائم (§39٫١٢٫٤)
        stmt = stmt.where(
            or_(
                admin_search.user_clause(term, PaymentRequest.user_id),
                admin_search.text_clause(term, PaymentRequest.reference),
            )
        )
    return (await session.scalars(stmt.limit(limit).offset(offset))).all()


async def _driver_of(session: AsyncSession, user: User) -> Driver:
    driver = await session.scalar(select(Driver).where(Driver.user_id == user.id))
    if driver is None:
        raise InvalidInput("الاشتراكُ للكباتن وحدَهم", field="purpose")
    return driver


async def create(
    session: AsyncSession,
    *,
    request_id: uuid.UUID,
    owner: User,
    provider_id: uuid.UUID,
    purpose: PaymentRequestPurpose,
    amount: Decimal,
    reference: str | None,
    plan_id: uuid.UUID | None,
    receipt_path: str | None,
    receipt_content_type: str | None,
    receipt_sha256: str | None,
    declared: WalletOwnerType | None = None,
) -> PaymentRequest:
    """**طلبٌ يفتحه صاحبُه** بعد أن يدفع — معلَّقاً حتى يعتمده موظّفٌ ماليّ.

    **وكلُّ حارسٍ في الشحن اليدويّ القائم هنا بترتيبه** (`topups.create_request`): حسابُ التجربة لا يُدخل مالاً حقيقيّاً، والحسابُ
    المحدود لا يشحن، والمحفظةُ مفعَّلةٌ وغيرُ مجمَّدة، **والمبلغُ بخانات عملته ومضاعفٌ لوحدة §٧٠** — وكسرُ الدينار الجزائريّ يُردّ.
    """
    test_accounts.require_real_money(
        owner, "حسابُ التجربة لا يُشحن بدفعٍ حقيقيّ — رصيدُه من «تصحيحِ تجربة» في اللوحة وحدَه"
    )
    await require_enabled(session, owner.country_code)
    provider = await available_provider(session, provider_id, owner.country_code)

    if provider.integration is not None:
        raise InvalidInput("هذه الطريقةُ تُدفع من صفحة الوسيط لا بطلبٍ يُعتمد", field="provider_id")
    if provider.kind is PaymentProviderKind.PURCHASE_CODE:
        raise InvalidInput("بطاقاتُ الشحن تُدخل برمزها", field="provider_id")
    if purpose is PaymentRequestPurpose.WALLET_TOPUP and not provider.for_topup:
        raise InvalidInput("هذه الطريقةُ لا تشحن المحفظة", field="provider_id")
    if purpose is PaymentRequestPurpose.SUBSCRIPTION and not provider.for_subscription:
        raise InvalidInput("هذه الطريقةُ لا تدفع الاشتراك", field="provider_id")

    verification.require_usable_account(owner)
    await wallet.require_wallet_enabled(session, owner.country_code)

    # **الاشتراكُ للكبتن ومن محفظته** (SPEC §22: سياقُ الفعل لا دورُ الفاعل)
    if purpose is PaymentRequestPurpose.SUBSCRIPTION:
        declared = WalletOwnerType.DRIVER
    owner_type = wallet.owner_type_for(owner, declared=declared)
    wallet.require_not_frozen(owner, owner_type)

    amount = as_money(amount)
    if amount <= 0:
        raise InvalidInput("المبلغُ يجب أن يكون أكبرَ من صفر", field="amount")
    await rounding.require_multiple_in(session, owner.country_code, amount)

    clean_reference = (reference or "").strip()[:120] or None
    if requires_receipt(provider):
        if receipt_path is None:
            raise InvalidInput("صورةُ الإيصال مطلوبة", field="receipt")
        # **والمرجعُ كذلك** (§٧٣-هـ/٦): صورتان مختلفتان للإيصال نفسِه تُفلتان من بصمة الصورة، ولا تُفلتان من رقمه
        if clean_reference is None:
            raise InvalidInput("رقمُ التحويل كما في الإيصال مطلوب", field="reference")

    if purpose is PaymentRequestPurpose.SUBSCRIPTION:
        if plan_id is None:
            raise InvalidInput("اختر خطةَ الاشتراك", field="plan_id")
        from app.services import offers, subscriptions

        driver = await _driver_of(session, owner)
        subscriptions.require_purchasable(driver)
        plan = await subscriptions.get_plan(session, plan_id, owner.country_code)
        offer = await offers.resolve(session, driver=driver, plan=plan, for_update=False)
        price = await subscriptions.price_to_pay(session, plan, offer)
        # **أقلُّ من الثمن لا يفعّل اشتراكاً** — وأكثرُ منه يبقى فرقُه في المحفظة (§٧٣-هـ/٧)
        if amount < price.payable:
            raise InvalidInput(
                f"المبلغُ أقلُّ من ثمن الاشتراك ({amount_text(price.payable, plan.currency)})", field="amount"
            )
    else:
        plan_id = None

    request = PaymentRequest(
        id=request_id,
        user_id=owner.id,
        owner_type=owner_type,
        country_code=owner.country_code,
        currency=currency_for_country(owner.country_code),
        provider_id=provider.id,
        kind=provider.kind,
        purpose=purpose,
        plan_id=plan_id,
        amount=amount,
        status=PaymentRequestStatus.PENDING,
        reference=clean_reference,
        reference_key=reference_key(clean_reference),
        receipt_path=receipt_path,
        receipt_content_type=receipt_content_type,
        receipt_sha256=receipt_sha256,
    )
    try:
        async with session.begin_nested():
            session.add(request)
            await session.flush()
    except IntegrityError as exc:
        # **الفهرسان الفريدان هما الحارس** — لا قراءةٌ قبل الكتابة تسبقها كتابةٌ متزامنة
        if "uq_payment_requests_" in str(exc.orig):
            raise PaymentAlreadySubmitted() from exc
        raise
    return request


async def approve(
    session: AsyncSession,
    *,
    request: PaymentRequest,
    actor: User | None,
    credited: Decimal | None = None,
) -> PaymentRequest:
    """**اعتمادُ الموظّف الماليّ — أو الوسيطِ الآليّ** (`actor=None`) → قيدُ شحنٍ في المعاملة نفسِها.

    **والمبلغُ مبلغُ الموظّف** (قرارُ المالك ٢٠٢٦-٠٨-٢٩): ما قرأه في كشف الحساب؛ و`None` «بمبلغه كما هو». **ودعوى صاحبِه تبقى في
    `amount`** فيرى من راجع بعد شهرٍ ما قيل وما دخل.

    **والاشتراكُ شحنٌ ثمّ شراءٌ بالمحفظة** بالباب القائم (§٧٣-هـ/٧) — **فإن تعذّر الشراءُ بقي المالُ في محفظته** وكُتب السبب.
    """
    if request.status is not PaymentRequestStatus.PENDING:
        raise InvalidStatusTransition()
    owner = await session.get(User, request.user_id)
    if owner is None:  # pragma: no cover — مفتاحٌ أجنبيٌّ يمنعه
        raise NotFound("صاحبُ الدفعة غيرُ موجود")
    test_accounts.require_real_money(
        owner, "لا يُعتمد دفعٌ لحساب تجربة — أعطه رصيداً بـ«تصحيحِ تجربة» من المحفظة"
    )

    amount = as_money(credited) if credited is not None else request.amount
    if amount <= 0:
        raise InvalidInput("المبلغُ يجب أن يكون أكبرَ من صفر", field="credited_amount")
    rounding.require_precise(amount, request.currency, field="credited_amount")

    # **صفُّ الكبتن قبل قفل المحفظة** — ترتيبُ الأقفال (`CLAUDE.md`): الشراءُ بعد الشحن يقفل الصفَّ نفسَه وهو بيدنا
    driver: Driver | None = None
    if request.purpose is PaymentRequestPurpose.SUBSCRIPTION:
        driver = await drivers_service.lock(session, await _driver_of(session, owner))

    wallet.require_not_frozen(owner, request.owner_type)
    provider = request.provider
    entry = await wallet.record(
        session,
        owner=owner,
        owner_type=request.owner_type,
        tx_type=WalletTransactionType.TOPUP,
        amount=amount,
        reference=f"{provider.name} {request.reference or ''}".strip()[:120],
        created_by=actor.id if actor is not None else None,
        # **الطلبُ نفسُه مفتاحُ عدم التكرار** — حارسٌ ثانٍ لا الأوّل
        idempotency_key=f"payment_request:{request.id}",
    )

    request.status = PaymentRequestStatus.APPROVED
    request.credited_amount = amount
    request.reviewed_by = actor.id if actor is not None else None
    request.reviewed_at = _now()
    request.transaction_id = entry.id

    # **ودَينُ إلغاءٍ يُسدَّد لحظةَ اكتمال الشحن** — كالشحن القائم حرفاً (`CANCELLATION-FEE.md` §7)
    await cancellation.on_wallet_funded(session, user=owner)

    if request.purpose is PaymentRequestPurpose.SUBSCRIPTION and driver is not None and request.plan_id is not None:
        from app.services import subscriptions

        try:
            async with session.begin_nested():
                subscription = await subscriptions.purchase_with_wallet(
                    session,
                    driver=driver,
                    user=owner,
                    plan_id=request.plan_id,
                    # **مفتاحٌ قصير**: عمودُ الدفتر ٦٤ حرفاً، و`payment_request_subscription:` معه ٦٥ — قِيس بسقوطٍ في الاختبار
                    idempotency_key=f"payreq_sub:{request.id}",
                )
            request.subscription_id = subscription.id
        except AppError as exc:
            # **لا مالَ يضيع**: الشحنُ قائمٌ في المحفظة، والشراءُ وحدَه تراجع — ويُكتب لماذا
            request.outcome_note = f"شُحنت المحفظةُ ولم يُفعَّل الاشتراك: {exc.message}"[:500]

    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="payment_request",
        entity_id=request.id,
        details={
            "action": "approve",
            "credited": str(amount),
            "claimed": str(request.amount),
            "owner_id": str(owner.id),
            "provider": provider.code,
            "transaction_id": str(entry.id),
            "subscription_id": str(request.subscription_id) if request.subscription_id else None,
            "via": "gateway" if actor is None else "staff",
        },
    )
    return request


async def reject(
    session: AsyncSession, *, request: PaymentRequest, actor: User | None, reason: str | None
) -> PaymentRequest:
    """**رفضٌ بسببٍ مكتوب** (قرارُ المالك) — يقرؤه صاحبُ الدفعة كما كُتب، ولا مالَ يتحرّك."""
    if request.status is not PaymentRequestStatus.PENDING:
        raise InvalidStatusTransition()
    request.status = PaymentRequestStatus.REJECTED
    request.rejection_reason = _reason(reason, field="reason")
    request.reviewed_by = actor.id if actor is not None else None
    request.reviewed_at = _now()
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="payment_request",
        entity_id=request.id,
        details={"action": "reject", "reason": request.rejection_reason},
    )
    return request


async def cancel(
    session: AsyncSession,
    *,
    request: PaymentRequest,
    actor: User,
    reason: str | None,
    by_owner: bool,
) -> PaymentRequest:
    """**إلغاءُ طلبٍ معلَّق** — يلغيه صاحبُه (وسببُه افتراضاً «ألغاه صاحبُه»)، أو موظّفٌ بسببٍ يكتبه."""
    if request.status is not PaymentRequestStatus.PENDING:
        raise InvalidStatusTransition()
    if by_owner and request.user_id != actor.id:
        raise NotFound("طلبُ الدفع غيرُ موجود")
    request.status = PaymentRequestStatus.CANCELLED
    request.cancel_reason = (
        (reason or "").strip()[:500] or "ألغاه صاحبُه" if by_owner else _reason(reason, field="reason")
    )
    request.cancelled_by = actor.id
    request.cancelled_at = _now()
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="payment_request",
        entity_id=request.id,
        details={"action": "cancel", "by_owner": by_owner, "reason": request.cancel_reason},
    )
    return request


async def refund(
    session: AsyncSession, *, request: PaymentRequest, actor: User, reason: str | None
) -> PaymentRequest:
    """**ردُّ دفعةٍ معتمدة** — قيدٌ مقابلٌ يعكس ما دخل (`adjustment`)، **ولا يُكتب إن لم يكفِ الرصيد** (§٧٣-هـ/٨).

    **والمالُ نفسُه يُردّ إلى صاحبه خارجَ المنصّة** (الحسابُ الذي حوّل منه) — وهذا السجلُّ يقول إنه رُدّ ويُنقص المحفظةَ بقدره.
    """
    if request.status is not PaymentRequestStatus.APPROVED:
        raise InvalidStatusTransition()
    clean = _reason(reason, field="reason")
    owner = await session.get(User, request.user_id)
    if owner is None:  # pragma: no cover
        raise NotFound("صاحبُ الدفعة غيرُ موجود")
    amount = request.credited_amount or request.amount
    try:
        entry = await wallet.record(
            session,
            owner=owner,
            owner_type=request.owner_type,
            tx_type=WalletTransactionType.ADJUSTMENT,
            amount=-amount,
            reference=f"ردّ دفعة {request.provider.name}"[:120],
            created_by=actor.id,
            idempotency_key=f"payment_request_refund:{request.id}",
        )
    except InsufficientBalance as exc:
        raise InsufficientBalance(
            f"لا يكفي رصيدُ المحفظة لردّ هذه الدفعة ({amount_text(amount, request.currency)})"
        ) from exc
    request.status = PaymentRequestStatus.REFUNDED
    request.refund_reason = clean
    request.refunded_by = actor.id
    request.refunded_at = _now()
    request.refund_transaction_id = entry.id
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="payment_request",
        entity_id=request.id,
        details={"action": "refund", "amount": str(amount), "reason": clean, "transaction_id": str(entry.id)},
    )
    return request


# ------------------------------------------------------------------ الوسيطُ الآليّ (الـwebhook الموحّد)


async def request_for_external(
    session: AsyncSession, *, integration: str, external_id: str
) -> PaymentRequest:
    """**الطلبُ بمعرّفه عند الوسيط — مقفلاً** — والوسيطُ يُعرف باسم محوِّله لا بسوقه: طلبٌ واحدٌ لا يُشارك معرّفَه طلباً آخر."""
    stmt = (
        select(PaymentRequest)
        .join(PaymentProvider, PaymentProvider.id == PaymentRequest.provider_id)
        .where(PaymentProvider.integration == integration, PaymentRequest.external_id == external_id)
        .with_for_update(of=PaymentRequest)
        .execution_options(populate_existing=True)
    )
    request = await session.scalar(stmt)
    if request is None:
        raise NotFound("لا طلبَ بهذا المعرّف")
    return request


async def apply_gateway_outcome(
    session: AsyncSession,
    *,
    request: PaymentRequest,
    outcome: PaymentRequestStatus,
    amount: Decimal | None,
    reason: str | None,
) -> PaymentRequest:
    """**ما قاله الوسيطُ يُطبَّق بالأبواب نفسِها التي يعتمد بها الموظّف** (§٧٣-هـ/١٠) — فلا مسارَ ثانياً للمال.

    **ومكرَّرُه لا يغيّر شيئاً**: طلبٌ حُسم يعود كما هو — الوسيطُ يعيد الإشعارَ حتى يرى ٢٠٠، والقيدُ لا يُكتب ثانية.
    """
    if request.status is not PaymentRequestStatus.PENDING:
        return request
    if outcome is PaymentRequestStatus.APPROVED:
        return await approve(session, request=request, actor=None, credited=amount)
    if outcome is PaymentRequestStatus.REJECTED:
        return await reject(session, request=request, actor=None, reason=reason or "رفضه الوسيط")
    if outcome is PaymentRequestStatus.CANCELLED:
        request.status = PaymentRequestStatus.CANCELLED
        request.cancel_reason = (reason or "أُلغي عند الوسيط")[:500]
        request.cancelled_at = _now()
        return request
    raise InvalidInput("حالٌ لا يُطبَّق من الوسيط")
