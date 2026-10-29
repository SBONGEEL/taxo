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
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
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
from app.models.payment_request import PayMethod, PaymentRequest
from app.models.user import User
from app.services import (
    admin_search,
    audit,
    cancellation,
    payment_reasons,
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


#: **مرجعُ قيدِ شحنٍ من وسيطٍ في وضع التجربة** (§٧٤-ط/٥) — كعلامة مال التجربة (`test_markets`): يُقرأ في الكشف أنه ليس مالاً
TEST_MONEY_MARK = "رصيد تجريبي"

#: **سببُ إلغاء صفحةٍ لم تُدفع في مهلتها** (§٧٤-ي/٥) — وChargily لا حالَ «انتهى» عنده؛ فالمهلةُ مهلتُنا
EXPIRED_REASON = payment_reasons.EXPIRED
#: **صفحةٌ قال وسيطُها «قيد المعالجة» حين انتهت المهلة** (§٧٦-ع/٢، المشكلة ١٧) — «لم يُدفع شيء» كان يقول ما لا نعرفه؛ **ودفعٌ يكتمل
#: بعدها يُقيَّد بإشعاره الموقَّع** (`settle_from_gateway`)
EXPIRED_PROCESSING_REASON = payment_reasons.EXPIRED_PROCESSING

#: **مهلةُ صفحة الوسيط** — بعدها يُسأل الوسيط: لم يُدفع ⇒ تُلغى بسببها، ودفعٌ يصل بعدها يُقيَّد ولا يضيع
CHECKOUT_TTL_HOURS = 24

#: **«دُفع» ينتظر إشعارَه الموقَّعَ هذه المدّة** ثمّ تقيِّده التسويةُ من جواب الوسيط المباشر (SPEC §٨٢-أ/٥) — الإشعارُ أوّلُ الشاهدين لا وحيدُهما
WEBHOOK_GRACE_SECONDS = 60
#: **دفعةٌ «قيد المعالجة» بعد هذه المدّة يُشعَر بها المالك** (§٨٢-أ/٢: «after N minutes») — مرّةً واحدة
REVIEW_ALERT_MINUTES = 15
#: **نقرتان سريعتان على «ادفع» صفحةٌ واحدة** (§٨٢-أ/٤) — القفلُ ما دامت الأولى تُفتح (وسقفُه هذا)، ثمّ يبقى معرّفُها
#: `DOUBLE_TAP_SECONDS` لنقرةٍ تأخّرت. **ولا أطولَ من ذلك**: من عاد بعد دقيقةٍ ليدفع ثانيةً يفتح صفحةً جديدة كما كان
CHECKOUT_LOCK_SECONDS = 30
DOUBLE_TAP_SECONDS = 5
#: **ما أُلغي عندنا بلا جوابٍ نهائيٍّ من الوسيط** — تراجعه التسويةُ في مهلة الصفحة، فدفعٌ اكتمل بعده يُقيَّد ولا يضيع
RECHECK_CANCELLED = frozenset({payment_reasons.NOT_COMPLETED, payment_reasons.EXPIRED})
#: **ومراجعتُه أطولُ من مهلة الصفحة** (تدقيقُ ٢٠٢٦-١٠-٢٨): المهلةُ تُلغي ما تجاوز `CHECKOUT_TTL_HOURS`، **فلو رُوجع في المهلة نفسِها
#: لما رُوجع ملغًى بها أبداً** — ودفعٌ اكتمل بعدها كان ينتظر إشعارَه الموقَّعَ أو تقريرَ المطابقة اليوميّ وحدَهما
RECHECK_LATE_HOURS = 2 * CHECKOUT_TTL_HOURS


class TestModeOnly(AppError):
    """**عقدُ الوسيط في وضع التجربة** — لحسابات التجربة وحدَها (§٧٤-ط/٥)، والطريقةُ لا تُعرض لغيرها أصلاً (`403`)."""

    status_code = 403
    code = "payment_test_mode_only"
    message = "هذه الطريقةُ في وضع التجربة — لحسابات التجربة وحدَها"


class EmailRequired(AppError):
    """**وسيطٌ يشترط البريد وحسابُ الدافع بلا بريد** (SofizPay، §٨٥/٦) — `422` باسمه فيعرض التطبيقُ الجديدُ حقلَ البريد مرّةً، **ولا طلبَ يُكتب**.
    **والنصُّ للتطبيق القديم وحدَه** (لا حقلَ فيه — يعرض الرسالةَ كما هي): يقول ما يفعله صاحبُها — يحدّث التطبيق."""

    status_code = 422
    code = "payment_email_required"
    message = "لتدفع بالبطاقة أضف بريدك الإلكترونيّ — حدّث التطبيق من المتجر ليظهر لك حقلُه"


def require_test_account(owner: User) -> None:
    if not owner.is_test:
        raise TestModeOnly()


async def topup_choices(session: AsyncSession, country: CountryCode) -> list[Decimal]:
    """**خياراتُ الشحن عند الوسيط** لسوقٍ (§٧٤-ط/٥) — قراءةً بلا إنشاء صفّ؛ وفارغةٌ «لا خيارات»."""
    from app.models.wallet_setting import WalletSetting

    values = await session.scalar(select(WalletSetting.topup_choices).where(WalletSetting.country_code == country))
    return sorted(as_money(value) for value in (values or []))


class PaymentAlreadySubmitted(Conflict):
    """**هذا التحويلُ قُدِّم من قبل** — مرجعُه أو صورةُ إيصاله في طلبٍ معلَّقٍ أو معتمدٍ للطريقة نفسِها (§٧٣-هـ/٦)."""

    code = "payment_already_submitted"
    message = "هذا التحويلُ قُدِّم من قبل — مرجعُه أو إيصالُه في طلبٍ آخر"


def _now() -> datetime:
    return datetime.now(UTC)


def requires_receipt(provider: PayMethod) -> bool:
    """**التحويلُ اليدويُّ إيصالُه إجباريّ** — والوسيطُ الآليُّ يشهد له الـwebhook لا الصورة."""
    return provider.integration is None and provider.kind in TRANSFER_KINDS


def reference_key(reference: str | None) -> str | None:
    """**المرجعُ مطبَّعاً للفهرس الفريد** — بلا مسافاتٍ وبحروفٍ صغيرة: «AB 12» و«ab12» تحويلٌ واحد."""
    if reference is None:
        return None
    key = "".join(reference.split()).casefold()
    return key or None


def written_reason(text: str | None, *, field: str) -> str:
    """**سببٌ مكتوبٌ يقرؤه صاحبُ الدفعة أو البطاقة** — ثلاثةُ أحرفٍ على الأقل، وخمسُمئةٍ على الأكثر (بيتٌ واحدٌ لنظام الدفع وبطاقاته)."""
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
) -> list[PayMethod]:
    """طرقُ الدفع **المفعَّلة** لسوقٍ ولغرضٍ — بترتيب اللوحة."""
    stmt = select(PayMethod).where(
        PayMethod.country_code == country, PayMethod.enabled.is_(True)
    )
    if purpose is PaymentRequestPurpose.WALLET_TOPUP:
        stmt = stmt.where(PayMethod.for_topup.is_(True))
    elif purpose is PaymentRequestPurpose.SUBSCRIPTION:
        stmt = stmt.where(PayMethod.for_subscription.is_(True))
    stmt = stmt.order_by(PayMethod.sort_order, PayMethod.name)
    return list((await session.scalars(stmt)).all())


async def all_providers(session: AsyncSession, country: CountryCode | None) -> list[PayMethod]:
    """كلُّ الطرق — للّوحة، مفعَّلةً وموقوفة."""
    stmt = select(PayMethod).order_by(
        PayMethod.country_code, PayMethod.sort_order, PayMethod.name
    )
    if country is not None:
        stmt = stmt.where(PayMethod.country_code == country)
    return list((await session.scalars(stmt)).all())


async def get_provider(
    session: AsyncSession, provider_id: uuid.UUID, *, for_update: bool = False
) -> PayMethod:
    stmt = select(PayMethod).where(PayMethod.id == provider_id)
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    provider = await session.scalar(stmt)
    if provider is None:
        raise NotFound("طريقةُ الدفع غيرُ موجودة")
    return provider


async def available_provider(session: AsyncSession, provider_id: uuid.UUID, country: CountryCode) -> PayMethod:
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


@dataclass(frozen=True, slots=True)
class Prepared:
    provider: PayMethod
    owner_type: WalletOwnerType
    amount: Decimal
    plan_id: uuid.UUID | None


async def _prepare(
    session: AsyncSession,
    *,
    owner: User,
    provider_id: uuid.UUID,
    purpose: PaymentRequestPurpose,
    amount: Decimal | None,
    plan_id: uuid.UUID | None,
    declared: WalletOwnerType | None,
    gateway: bool,
    test_money: bool = False,
) -> Prepared:
    """**حرّاسُ كلِّ طلبٍ قبل أن يُكتب** — يدويّاً كان أو عند وسيط: بابٌ واحدٌ فلا يفترق الطريقان أوّلَ شرطٍ يُضاف.

    **و`test_money`**: صفحةُ وسيطٍ بعقدٍ في وضع التجربة (§٧٤-ط/٥) — **لحسابات التجربة وحدَها**، ومالُها «تجريبيّ» لا يغادر المنصّة.
    **وعقدٌ حيٌّ لا يفتحه حسابُ تجربة** كما كان. **وفي الاشتراك عند الوسيط المبلغُ ثمنُ الخطّة من الخادم** لا ما أرسله التطبيق.
    """
    if test_money:
        require_test_account(owner)
    else:
        test_accounts.require_real_money(
            owner, "حسابُ التجربة لا يُشحن بدفعٍ حقيقيّ — رصيدُه من «تصحيحِ تجربة» في اللوحة وحدَه"
        )
    await require_enabled(session, owner.country_code)
    provider = await available_provider(session, provider_id, owner.country_code)

    if gateway and provider.integration is None:
        raise InvalidInput("هذه الطريقةُ تُدفع بطلبٍ يُعتمد لا من صفحة وسيط", field="provider_id")
    if not gateway and provider.integration is not None:
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

    if gateway and purpose is PaymentRequestPurpose.SUBSCRIPTION:
        amount = Decimal("0")  # يُكتب أدناه ثمنَ الخطّة من الخادم — ولا يُقرأ ما أرسله التطبيق
    else:
        if amount is None:
            raise InvalidInput("اكتب المبلغ", field="amount")
        amount = as_money(amount)
        if amount <= 0:
            raise InvalidInput("المبلغُ يجب أن يكون أكبرَ من صفر", field="amount")
        await rounding.require_multiple_in(session, owner.country_code, amount)
    if gateway and purpose is PaymentRequestPurpose.WALLET_TOPUP:
        # **خياراتٌ ثابتةٌ إن ضبطها السوق** (§٧٤-ط/٥) — والمبلغُ واحدٌ منها وإلا رُدّ؛ وسوقٌ بلا خياراتٍ كما كان
        choices = await topup_choices(session, owner.country_code)
        if choices and amount not in choices:
            raise InvalidInput("اختر مبلغَ الشحن من الخيارات", field="amount")

    if purpose is PaymentRequestPurpose.SUBSCRIPTION:
        if plan_id is None:
            raise InvalidInput("اختر خطةَ الاشتراك", field="plan_id")
        from app.services import offers, subscriptions

        driver = await _driver_of(session, owner)
        subscriptions.require_purchasable(driver)
        plan = await subscriptions.get_plan(session, plan_id, owner.country_code, held_ok=bool(owner.is_test))
        offer = await offers.resolve(session, driver=driver, plan=plan, for_update=False)
        price = await subscriptions.price_to_pay(session, plan, offer)
        if gateway:
            # **ثمنُ الخطّة من الخادم** (§٧٤-ط/٥: «never trust the app for the amount») — والعرضُ القائمُ محسوبٌ فيه
            amount = as_money(price.payable)
            if amount <= 0:
                raise InvalidInput("لا شيءَ يُدفع لهذه الخطّة الآن", field="plan_id")
            rounding.require_precise(amount, currency_for_country(owner.country_code), field="plan_id")
        # **أقلُّ من الثمن لا يفعّل اشتراكاً** — وأكثرُ منه يبقى فرقُه في المحفظة (§٧٣-هـ/٧)
        elif amount < price.payable:
            raise InvalidInput(
                f"المبلغُ أقلُّ من ثمن الاشتراك ({amount_text(price.payable, plan.currency)})", field="amount"
            )
    else:
        plan_id = None
    require_within_bounds(provider, amount, currency_for_country(owner.country_code))
    return Prepared(provider=provider, owner_type=owner_type, amount=amount, plan_id=plan_id)


def require_within_bounds(provider: PayMethod, amount: Decimal, currency) -> None:
    """**حدّا الطريقة** (SPEC §٨٢-ب/٦) — مبلغٌ خارجهما يُردّ قبل أن يُكتب الطلب؛ وطريقةٌ بلا حدّين كما كانت."""
    if provider.min_amount is not None and amount < provider.min_amount:
        raise InvalidInput(f"أقلُّ مبلغٍ بهذه الطريقة {amount_text(provider.min_amount, currency)}", field="amount")
    if provider.max_amount is not None and amount > provider.max_amount:
        raise InvalidInput(f"أكثرُ مبلغٍ بهذه الطريقة {amount_text(provider.max_amount, currency)}", field="amount")


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
    transfer_date: date | None = None,
) -> PaymentRequest:
    """**طلبٌ يفتحه صاحبُه** بعد أن يدفع — معلَّقاً حتى يعتمده موظّفٌ ماليّ.

    **وكلُّ حارسٍ في الشحن اليدويّ القائم هنا بترتيبه** (`topups.create_request`): حسابُ التجربة لا يُدخل مالاً حقيقيّاً، والحسابُ
    المحدود لا يشحن، والمحفظةُ مفعَّلةٌ وغيرُ مجمَّدة، **والمبلغُ بخانات عملته ومضاعفٌ لوحدة §٧٠** — وكسرُ الدينار الجزائريّ يُردّ.
    """
    prepared = await _prepare(
        session, owner=owner, provider_id=provider_id, purpose=purpose, amount=amount, plan_id=plan_id,
        declared=declared, gateway=False,
    )
    provider, owner_type, amount, plan_id = prepared.provider, prepared.owner_type, prepared.amount, prepared.plan_id
    clean_reference = (reference or "").strip()[:120] or None
    if requires_receipt(provider):
        if receipt_path is None:
            raise InvalidInput("صورةُ الإيصال مطلوبة", field="receipt")
        # **والمرجعُ كذلك** (§٧٣-هـ/٦): صورتان مختلفتان للإيصال نفسِه تُفلتان من بصمة الصورة، ولا تُفلتان من رقمه
        if clean_reference is None:
            raise InvalidInput("رقمُ التحويل كما في الإيصال مطلوب", field="reference")
    # **وتاريخُه في BaridiMob** (SPEC §٨٢-ب/٣) — يقارنه المراجعُ بما وصل؛ لا في الغد ولا قبل تسعين يوماً. **والطرقُ الأخرى كما كانت**
    from app.services import transfers

    if provider.code == transfers.CODE:
        if transfer_date is None:
            raise InvalidInput("تاريخُ التحويل كما في الإيصال مطلوب", field="transfer_date")
        today = _now().date()
        if transfer_date > today + timedelta(days=1) or transfer_date < today - timedelta(days=90):
            raise InvalidInput("تاريخُ التحويل غيرُ صحيح", field="transfer_date")
    elif not requires_receipt(provider):
        transfer_date = None

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
        transfer_date=transfer_date,
    )
    try:
        async with session.begin_nested():
            session.add(request)
            await session.flush()
    except IntegrityError as exc:
        # **الفهرسان الفريدان هما الحارس** — لا قراءةٌ قبل الكتابة تسبقها كتابةٌ متزامنة
        if "uq_payment_requests_" in str(exc.orig):
            # **ويُشعَر المالكُ بالمكرَّر** (§٨٢-ب/٦: «block and flag duplicates») — بعد الالتزام لا قبله، فلا يُكتب ما رُجع عنه
            _flag("transfer_duplicate", country=owner.country_code, provider=provider.code)
            raise PaymentAlreadySubmitted() from exc
        raise
    return request


async def approve(
    session: AsyncSession,
    *,
    request: PaymentRequest,
    actor: User | None,
    credited: Decimal | None = None,
    test_money: bool = False,
    subscribe: bool = True,
) -> PaymentRequest:
    """**اعتمادُ الموظّف الماليّ — أو الوسيطِ الآليّ** (`actor=None`) → قيدُ شحنٍ في المعاملة نفسِها.

    **و`test_money`** (§٧٤-ط/٥): الوسيطُ في وضع التجربة — **يُقيَّد لحساب تجربةٍ وحدَه** ومرجعُه موسومٌ «رصيد تجريبي»؛ وحسابٌ حقيقيٌّ
    لا يُقيَّد له مالٌ لا وجودَ له، **وحسابُ التجربة لا يُقيَّد له مالٌ حقيقيّ** كما كان.

    **والمبلغُ مبلغُ الموظّف** (قرارُ المالك ٢٠٢٦-٠٨-٢٩): ما قرأه في كشف الحساب؛ و`None` «بمبلغه كما هو». **ودعوى صاحبِه تبقى في
    `amount`** فيرى من راجع بعد شهرٍ ما قيل وما دخل.

    **والاشتراكُ شحنٌ ثمّ شراءٌ بالمحفظة** بالباب القائم (§٧٣-هـ/٧) — **فإن تعذّر الشراءُ بقي المالُ في محفظته** وكُتب السبب.
    """
    if request.status is not PaymentRequestStatus.PENDING:
        raise InvalidStatusTransition()
    owner = await session.get(User, request.user_id)
    if owner is None:  # pragma: no cover — مفتاحٌ أجنبيٌّ يمنعه
        raise NotFound("صاحبُ الدفعة غيرُ موجود")
    if test_money and actor is None:
        require_test_account(owner)
    else:
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
        reference=((f"{TEST_MONEY_MARK} — " if test_money else "") + f"{provider.name} {request.reference or ''}".strip())[:120],
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

    if subscribe and request.purpose is PaymentRequestPurpose.SUBSCRIPTION and driver is not None and request.plan_id is not None:
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
            "test_money": test_money,
        },
    )
    if actor is not None and provider.integration is None:
        _flag("transfer_approved", session=session, request=request, by=decided_by(actor))
    return request


async def reject(
    session: AsyncSession, *, request: PaymentRequest, actor: User | None, reason: str | None
) -> PaymentRequest:
    """**رفضٌ بسببٍ مكتوب** (قرارُ المالك) — يقرؤه صاحبُ الدفعة كما كُتب، ولا مالَ يتحرّك."""
    if request.status is not PaymentRequestStatus.PENDING:
        raise InvalidStatusTransition()
    request.status = PaymentRequestStatus.REJECTED
    request.rejection_reason = written_reason(reason, field="reason")
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
    if actor is not None and request.provider.integration is None:
        _flag("transfer_rejected", session=session, request=request, by=decided_by(actor))
    return request


def decided_by(actor: User) -> str:
    """**من حسم التحويل** — المراجعُ أو المالكُ أو موظّفُ الماليّة؛ يقرؤه المالكُ في إشعاره."""
    from app.models.enums import UserRole

    if actor.has_role(UserRole.OWNER):
        return "owner"
    if actor.has_role(UserRole.PAYMENT_REVIEWER):
        return "reviewer"
    return "staff"


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
    # **«قيد المعالجة» لا يلغيه صاحبُه** (SPEC §٨٢-أ/٢): المالُ وصل، والتسويةُ تقيِّده — وإلغاؤه يُسقط ما دُفع من شاشته
    if by_owner and request.gateway_paid_at is not None:
        raise InvalidStatusTransition("وصل دفعُك ويُعالَج — لا يُلغى")
    request.status = PaymentRequestStatus.CANCELLED
    request.cancel_reason = (
        (reason or "").strip()[:500] or payment_reasons.BY_OWNER if by_owner else written_reason(reason, field="reason")
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
    clean = written_reason(reason, field="reason")
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


# ------------------------------------------------------------------ الوسيطُ الآليّ (المرحلة ٣)


async def start_checkout(
    session: AsyncSession,
    *,
    owner: User,
    provider_id: uuid.UUID,
    purpose: PaymentRequestPurpose,
    amount: Decimal | None,
    plan_id: uuid.UUID | None,
    declared: WalletOwnerType | None,
    opened_from: str,
) -> tuple[PaymentRequest, str]:
    """**صفحةُ دفعٍ عند الوسيط** — طلبٌ معلَّقٌ بمعرّفه عنده، ويُحسم بجوابه المباشر (الـwebhook يوقظ، و`refresh` يسأل).

    **والحرّاسُ حرّاسُ الطلب اليدويّ نفسُها** (`_prepare`)؛ **ونداءُ الوسيط بلا قفلِ صفّ** — لا صفَّ مقفولاً هنا أصلاً، والطلبُ يُكتب
    ويُختم معرّفُه في معاملةٍ واحدة: فشلُ الوسيط لا يترك طلباً بلا صفحة.
    """
    from app.services import payment_gateways

    # **العقدُ أوّلاً — فوضعُه يقرّر من يفتح الصفحة** (§٧٤-ط/٥): وضعُ التجربة لحسابات التجربة وحدَها، والحيُّ لغيرها
    await require_enabled(session, owner.country_code)
    chosen = await available_provider(session, provider_id, owner.country_code)
    if chosen.integration is None:
        raise InvalidInput("هذه الطريقةُ تُدفع بطلبٍ يُعتمد لا من صفحة وسيط", field="provider_id")
    from app.core.i18n import current_language
    from app.services import gateway_customers

    gateway = await payment_gateways.gateway_for(session, chosen.integration, owner.country_code)
    if not payment_gateways.allowed_for(gateway, owner.phone):
        # **ما لا يُعرض لا يُفتح** — كعقدٍ غائب
        raise payment_gateways.GatewayUnavailable()
    if getattr(gateway, "requires_email", False) and not owner.email:
        raise EmailRequired("لتدفع بالبطاقة أضف بريدك الإلكترونيّ — حدّث التطبيق من المتجر ليظهر لك حقلُه", field="email")
    prepared = await _prepare(
        session, owner=owner, provider_id=provider_id, purpose=purpose, amount=amount, plan_id=plan_id,
        declared=declared, gateway=True, test_money=bool(getattr(gateway, "test_mode", False)),
    )
    provider = prepared.provider
    # **فحصُ الصحّة قبل أن يُرسل الدافعُ إلى صفحة** (SPEC §٨٢-أ/١) — متوقّفٌ أو بطيءٌ جدّاً ⇐ `GatewayDown` بلغته، ولا صفحةَ معطوبة
    from app.services import gateway_health

    await gateway_health.require_up(gateway, provider.integration or "", owner.country_code)
    request = PaymentRequest(
        user_id=owner.id,
        owner_type=prepared.owner_type,
        country_code=owner.country_code,
        currency=currency_for_country(owner.country_code),
        provider_id=provider.id,
        kind=provider.kind,
        purpose=purpose,
        plan_id=prepared.plan_id,
        amount=prepared.amount,
        status=PaymentRequestStatus.PENDING,
    )
    session.add(request)
    await session.flush()
    # **عميلُ الدافع عند الوسيط** (§٧٦-ع/٢) — فلا تسأله صفحتُه بياناتِه؛ **ولغةُ الصفحة لغةُ التطبيق** (كانت «ar» ثابتة)
    customer = await gateway_customers.customer_for(session, gateway, owner)
    opened = dict(
        amount=prepared.amount,
        description=f"TAXO {'اشتراك' if purpose is PaymentRequestPurpose.SUBSCRIPTION else 'شحن رصيد'}",
        return_url=payment_gateways.return_url(str(request.id), opened_from=opened_from),
        webhook_url=payment_gateways.webhook_url(provider.integration or ""),
        fee_bearer=provider.fee_bearer,
        locale=current_language(),
    )
    try:
        checkout = await gateway.checkout(customer=customer, **opened)
    except payment_gateways.GatewayDown:
        await gateway_health.note(provider.integration or "", owner.country_code, up=False)
        raise
    except payment_gateways.GatewayError:
        if customer.gateway_id is None:
            raise
        # **عميلٌ محفوظٌ رفضه الوسيط** (حُذف عنده أو تبدّل المفتاح) — يُنسى، **وتُفتح الصفحةُ بلا عميل** فلا يقف الدفعُ عليه
        await gateway_customers.forget(session, gateway, owner)
        bare = payment_gateways.CheckoutCustomer(customer.full_name, customer.phone, customer.email)
        checkout = await gateway.checkout(customer=bare, **opened)
    request.external_id = checkout.external_id
    request.reference = checkout.external_id[:120]
    # **الرسومُ كما قالها الوسيطُ عند الفتح** (§٧٤-ك/١) — ومن يحملها من إعداد الطريقة الآن؛ وتُصحَّح عند التأكيد
    request.fee_payer = provider.fee_bearer
    request.fee_amount = _fee_of(provider.fee_bearer, checkout.fee_on_customer, checkout.fee_on_merchant)
    await session.flush()
    return request, checkout.checkout_url


async def resume_checkout(session: AsyncSession, *, owner: User, request_id: uuid.UUID) -> tuple[PaymentRequest, str]:
    """**«أكمل الدفع»** (§٧٦-ع/٢، المشكلتان ٣ و١٣) — صفحةُ الوسيط نفسُها لطلبٍ معلَّقٍ لم يُدفع بعد، **لا صفحةٌ ثانيةٌ وطلبٌ ثانٍ**.

    **والوسيطُ يُسأل بلا قفل** (لا صفَّ يُقفل هنا ولا يُكتب شيء)؛ وصفحةٌ لم تعد تنتظر — حُسمت أو بدأت معالجتُها — **لا تُفتح** ويُقال ذلك
    لصاحبها، **والتطبيقُ يسأل عن حالها بـ`refresh`**.
    """
    from app.services import payment_gateways

    row = await get_request(session, request_id)
    if row.user_id != owner.id:
        raise NotFound("طلبُ الدفع غيرُ موجود")
    integration = row.provider.integration
    if integration is None or row.external_id is None:
        raise InvalidInput("هذه الدفعةُ لا تُدفع من صفحة وسيط", field="request_id")
    if row.status is not PaymentRequestStatus.PENDING:
        raise InvalidStatusTransition("حُسمت هذه الدفعة — لا صفحةَ تُستأنف")
    gateway = await payment_gateways.gateway_for(session, integration, row.country_code)
    resume = getattr(gateway, "resume_url", None)
    url = await resume(row.external_id) if resume is not None else None
    if url is None:
        raise InvalidStatusTransition("صفحةُ هذه الدفعة لم تعد تنتظر — انظر حالَها في طلباتك")
    return row, url


def _fee_of(payer: str | None, on_customer: Decimal | None, on_merchant: Decimal | None) -> Decimal | None:
    """**رسمُ الطلب الواحد** — ما على الدافع إن حملها، وما على TAXO إن حملتها؛ و`None` حين لا يذكره الوسيط."""
    value = on_customer if payer == "user" else on_merchant
    return as_money(value) if value is not None else None


#: ما يُحسم بعد أن حُسم الطلب: **دفعٌ وصل بعد إلغاءٍ أو فشل** — المالُ دخل، فيُقيَّد ولا يضيع (§٧٤-ي/٥)
_LATE_STATUSES = frozenset({PaymentRequestStatus.CANCELLED, PaymentRequestStatus.REJECTED})


async def settle_from_gateway(
    session: AsyncSession, *, request_id: uuid.UUID, signed: bool = False
) -> tuple[PaymentRequest, bool]:
    """**السؤالُ قبل القفل** (لا قفلَ عبر نداء شبكة)، والتطبيقُ بعده بالباب نفسِه الذي يطبّق به الإشعار — **و«أحَسمَه هذا النداء؟»
    يُحكم تحت القفل**: ثلاثةُ إشعاراتٍ متزامنةٍ يقرأ كلٌّ منها «معلَّق» قبل القفل، **وواحدٌ وحدَه يجده معلَّقاً بعده** (قِيس: عدُّ ما
    قبل القفل قال «حُسم» ثلاثاً لقيدٍ واحد).

    **و`signed`**: النداءُ من إشعارٍ تحقّق توقيعُه (§٧٤-ط/٥). **عند وسيطٍ يوقّع إشعارَه (Chargily) لا يُقيَّد «دُفع» بغيره** — وما عداه
    (فشلٌ · إلغاء) يُحسم من أيِّ سؤال. **ودفعٌ يصل بعد أن أُلغي الطلبُ أو فشل** يُقيَّد (المالُ دخل) بسطرٍ يقول ذلك.
    """
    from app.services import payment_gateways

    row = await get_request(session, request_id)
    provider = row.provider
    if provider.integration is None or row.external_id is None:
        return row, False
    if row.status is not PaymentRequestStatus.PENDING and not (signed and row.status in _LATE_STATUSES):
        return row, False
    gateway = await payment_gateways.gateway_for(session, provider.integration, row.country_code)
    event = await gateway.check(row.external_id)
    if event is None:
        return row, False
    may_credit = signed or not getattr(gateway, "confirms_by_webhook", False)
    if event.outcome is PaymentRequestStatus.APPROVED and not may_credit:
        return row, False  # **«دُفع» ينتظر إشعارَه الموقَّع** — لا يُقيَّد من عودة التطبيق
    locked = await get_request(session, request_id, for_update=True)
    late = locked.status in _LATE_STATUSES and event.outcome is PaymentRequestStatus.APPROVED and may_credit
    if locked.status is not PaymentRequestStatus.PENDING and not late:
        return locked, False
    if late:
        _reopen_for_late_payment(locked)
    if event.outcome is PaymentRequestStatus.APPROVED:
        # **الرسومُ كما قالها الوسيطُ عند الدفع** (§٧٤-ك/١) — أصدقُ من قولها عند الفتح
        paid_fee = _fee_of(locked.fee_payer, event.fee_on_customer, event.fee_on_merchant)
        if paid_fee is not None:
            locked.fee_amount = paid_fee
    settled = await apply_gateway_outcome(
        session, request=locked, outcome=event.outcome, amount=event.amount, reason=event.reason,
        test_money=bool(getattr(gateway, "test_mode", False)),
    )
    return settled, settled.status is not PaymentRequestStatus.PENDING


def _reopen_for_late_payment(request: PaymentRequest) -> None:
    """**دفعٌ وصل بعد أن حُسم الطلب** (أُلغي بمهلته أو بصاحبه، أو فشل ثمّ دُفع) — يُعاد معلَّقاً ليُعتمد بالباب نفسِه، **وما كان
    يُكتب في `outcome_note`** فيقرأ من راجعه لمَ اعتُمد طلبٌ كان ملغًى."""
    was = request.cancel_reason or request.rejection_reason or request.status.value
    request.outcome_note = f"وصل الدفعُ بعد أن حُسم الطلب («{was}») — قُيِّد بإشعار الوسيط"[:500]
    request.status = PaymentRequestStatus.PENDING


async def expire_stale(session: AsyncSession, *, now: datetime | None = None) -> int:
    """**صفحاتٌ لم تُدفع في مهلتها تُلغى بسببها** (§٧٤-ي/٥) — بعد سؤال الوسيط، **قبل القفل** ثمّ تحت القفل.

    Chargily لا حالَ «انتهى» عنده (حالاتُه في وثائقه: معلَّق · قيد المعالجة · مدفوع · فاشل · ملغى)، **فالمهلةُ مهلتُنا**
    (`CHECKOUT_TTL_HOURS`). **وما قال «دُفع» لا يُلغى** — ينتظر إشعارَه؛ **وما يصل بعد الإلغاء يُقيَّد** (`settle_from_gateway`).
    **ولكلِّ طلبٍ معاملتُه**: يُودَع بعد كلِّ واحد، فوسيطٌ بطيءٌ لا يُبقي أقفالاً.
    """
    from app.services import payment_gateways

    moment = now or _now()
    stale = (
        await session.scalars(
            select(PaymentRequest.id)
            .join(PayMethod, PayMethod.id == PaymentRequest.provider_id)
            .where(
                PaymentRequest.status == PaymentRequestStatus.PENDING,
                PaymentRequest.external_id.is_not(None),
                PayMethod.integration.is_not(None),
                PaymentRequest.gateway_paid_at.is_(None),
                PaymentRequest.created_at < moment - timedelta(hours=CHECKOUT_TTL_HOURS),
            )
            .order_by(PaymentRequest.created_at)
            .limit(200)
        )
    ).all()
    expired = 0
    for request_id in stale:
        row = await get_request(session, request_id)
        try:
            gateway = await payment_gateways.gateway_for(session, row.provider.integration or "", row.country_code)
            event = await gateway.check(row.external_id or "")
        except (payment_gateways.GatewayUnavailable, payment_gateways.GatewayError):
            continue  # **لا يُلغى ما لم يُسأل عنه** — يُعاد في الدورة التالية
        if event is not None and event.outcome is PaymentRequestStatus.APPROVED:
            continue
        locked = await get_request(session, request_id, for_update=True)
        if locked.status is not PaymentRequestStatus.PENDING:
            await session.commit()
            continue
        if event is not None:
            await apply_gateway_outcome(
                session, request=locked, outcome=event.outcome, amount=event.amount, reason=event.reason,
                test_money=bool(getattr(gateway, "test_mode", False)),
            )
        else:
            processing = getattr(gateway, "last_status", None) == "processing"
            reason = (
                EXPIRED_PROCESSING_REASON.format(payment_gateways.DISPLAY_NAMES.get(gateway.name, gateway.name))
                if processing
                else EXPIRED_REASON
            )
            locked.status = PaymentRequestStatus.CANCELLED
            locked.cancel_reason = reason
            locked.cancelled_at = moment
            await audit.record(
                session, actor=None, action=AuditAction.UPDATE, entity_type="payment_request", entity_id=locked.id,
                details={"action": "expire", "reason": reason},
            )
        await session.commit()
        expired += 1
    return expired


# ------------------------------------------------------------------ الوسيطُ الآليّ (الـwebhook الموحّد)


async def find_external(session: AsyncSession, *, integration: str, external_id: str) -> PaymentRequest | None:
    """**الطلبُ بمعرّفه عند الوسيط بلا قفل** — يُقرأ ليُسأل الوسيطُ عنه **قبل** أن يُقفل (`refresh`)."""
    return await session.scalar(
        select(PaymentRequest)
        .join(PayMethod, PayMethod.id == PaymentRequest.provider_id)
        .where(PayMethod.integration == integration, PaymentRequest.external_id == external_id)
    )


async def request_for_external(
    session: AsyncSession, *, integration: str, external_id: str
) -> PaymentRequest:
    """**الطلبُ بمعرّفه عند الوسيط — مقفلاً** — والوسيطُ يُعرف باسم محوِّله لا بسوقه: طلبٌ واحدٌ لا يُشارك معرّفَه طلباً آخر."""
    stmt = (
        select(PaymentRequest)
        .join(PayMethod, PayMethod.id == PaymentRequest.provider_id)
        .where(PayMethod.integration == integration, PaymentRequest.external_id == external_id)
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
    test_money: bool = False,
) -> PaymentRequest:
    """**ما قاله الوسيطُ يُطبَّق بالأبواب نفسِها التي يعتمد بها الموظّف** (§٧٣-هـ/١٠) — فلا مسارَ ثانياً للمال.

    **ومكرَّرُه لا يغيّر شيئاً**: طلبٌ حُسم يعود كما هو — الوسيطُ يعيد الإشعارَ حتى يرى ٢٠٠، والقيدُ لا يُكتب ثانية.
    """
    if request.status is not PaymentRequestStatus.PENDING:
        return request
    if outcome is PaymentRequestStatus.APPROVED:
        # **دُفع ⇐ لا يُرفض أبداً** (SPEC §٨٢-أ/٢): المالُ دخل. **ومبلغٌ مختلفٌ لا يُقيَّد بتخمين** — يبقى «قيد المعالجة» بسببه،
        # ولا يُطلب من صاحبه أن يدفع ثانية، **والمالكُ يُشعَر به إن لم يُحسم** (`reconcile_gateway`)
        if request.gateway_paid_at is None:
            request.gateway_paid_at = _now()
        if amount is not None and as_money(amount) != request.amount:
            request.outcome_note = payment_reasons.AMOUNT_MISMATCH.format(
                amount_text(amount, request.currency), amount_text(request.amount, request.currency)
            )[:500]
            return request
        extra = await paid_again_since(session, request)
        # **«دُفع» يُكتب خارجَ نقطة الحفظ** — فتراجعُ التفعيل أدناه لا يمحو أنّ المالَ وصل
        await session.flush()
        try:
            async with session.begin_nested():
                await approve(
                    session, request=request, actor=None, credited=request.amount, test_money=test_money,
                    subscribe=not extra,
                )
        except AppError as exc:
            # **دُفع ولم يُفعَّل** — يبقى «قيد المعالجة» بسببه، والتسويةُ تعيد المحاولة، والمالكُ يُشعَر بعد مهلته.
            # **ونقطةُ الحفظ المتراجعةُ تُسقط ما في الذاكرة** — فيُقرأ الصفُّ من القاعدة قبل أن يُكتب عليه
            await session.refresh(request)
            request.outcome_note = payment_reasons.NOT_ACTIVATED.format(exc.message)[:500]
            return request
        if extra:
            request.outcome_note = payment_reasons.PAID_TWICE
            _flag("payment_extra", session=session, request=request)
        return request
    if outcome is PaymentRequestStatus.REJECTED:
        rejected = await reject(session, request=request, actor=None, reason=reason or "رفضه الوسيط")
        # **قاطعُ الدائرة** (SPEC §٨٧/١) — ثلاثُ إخفاقاتٍ متتاليةٍ تُخفي الطريقةَ آليّاً ويُشعَر المالك
        from app.services import payment_breaker

        await payment_breaker.after_failure(session, rejected, test_money=test_money)
        return rejected
    if outcome is PaymentRequestStatus.CANCELLED:
        request.status = PaymentRequestStatus.CANCELLED
        request.cancel_reason = (reason or "أُلغي عند الوسيط")[:500]
        request.cancelled_at = _now()
        return request
    raise InvalidInput("حالٌ لا يُطبَّق من الوسيط")


# ------------------------------------------------------------------ دفعُ الجزائر بأمان (SPEC §٨٢-أ)


def _flag(
    kind: str, *, session: AsyncSession | None = None, request: PaymentRequest | None = None,
    country: CountryCode | None = None, **data: object,
) -> None:
    """**إشعارُ المالك بما لا يلتقطه مستمعُ الصفوف** (دفعٌ مكرَّر · «قيد المعالجة» طالت · رقمُ تحويلٍ مكرَّر) — بعد الالتزام إن
    مُرّرت المعاملة، **وفي الحال بدونها** (المكرَّرُ يُرَدّ فتُلغى معاملتُه، والإشعارُ به لا يُلغى معها)."""
    from app.services import alert_capture

    if request is not None:
        alert_capture.ship_after_commit(session, kind, "payment_request", request.id, **data)
    else:
        alert_capture.ship_after_commit(session, kind, "signal", uuid.uuid4(), country=country.value if country else None, **data)


async def paid_again_since(session: AsyncSession, request: PaymentRequest) -> bool:
    """**دفع صاحبُها ثانيةً للغرض نفسِه بعد أن بدأها** (SPEC §٨٢-أ/٢) — طلبٌ آخرُ معتمدٌ للغرض نفسِه (والخطّةِ نفسِها) اعتُمد بعد
    أن فُتح هذا. **فهذا الزائدُ** يذهب إلى المحفظة ولا يُفعِّل شيئاً ثانية. والشحنُ المتتابعُ العاديُّ لا يمسّه: ما اعتُمد قبل أن يُفتح
    هذا ليس «دفعاً ثانياً»."""
    stmt = select(PaymentRequest.id).where(
        PaymentRequest.user_id == request.user_id,
        PaymentRequest.purpose == request.purpose,
        PaymentRequest.id != request.id,
        PaymentRequest.status == PaymentRequestStatus.APPROVED,
        PaymentRequest.reviewed_at >= request.created_at,
    )
    if request.purpose is PaymentRequestPurpose.SUBSCRIPTION:
        stmt = stmt.where(PaymentRequest.plan_id == request.plan_id)
    return await session.scalar(stmt.limit(1)) is not None


def phase_of(request: PaymentRequest) -> str:
    """**ما يراه صاحبُ الدفعة** (SPEC §٨٢-أ/٢) — من الحال ومن «قال الوسيطُ دُفع»:

    - `processing` — **دُفع ولم يُقيَّد بعد**: «وصل دفعُك ويُعالَج»، ولا يُسأل أن يدفع ثانية.
    - `unconfirmed` — صفحةُ وسيطٍ لا نعرف حالَها: **لا تحجب** — يدفع ثانيةً إن شاء، وإن ظهر أنها دُفعت قُيِّدت مرّةً وذهب الزائدُ لمحفظته.
    - `in_review` — تحويلٌ يدويٌّ ينتظر المراجعة.
    - وما عداها حالُ الطلب نفسُها.
    """
    if request.status is not PaymentRequestStatus.PENDING:
        return request.status.value
    if request.provider.integration is None:
        return "in_review"
    return "processing" if request.gateway_paid_at is not None else "unconfirmed"


def public_ref(request_id: uuid.UUID) -> str:
    """**مرجعُ TAXO للطلب** (SPEC §٨٢-ب/٣) — يكتبه الدافعُ في ملاحظة BaridiMob، ويقرؤه المراجعُ؛ مشتقٌّ من المعرّف فلا عمودَ له."""
    return "TX-" + request_id.hex[:6].upper()


async def refresh(session: AsyncSession, *, request_id: uuid.UUID) -> PaymentRequest:
    """**يسأل الوسيطَ عن طلبٍ عاد إليه صاحبُه بلا نتيجةٍ واضحة** (SPEC §٨٢-أ/٣) — والجوابُ أحدُ أطوار §٨٢-أ/٢:

    - **«معلّقة» عند الوسيط** — عاد ولم يُكمل: تُلغى بسببها فيدفع من جديد فوراً (`NOT_COMPLETED`).
    - **«دُفع»** — يُختم «قيد المعالجة» (`gateway_paid_at`) **ولا يُقيَّد من عودة التطبيق** (§٧٤-ط/٥): الإشعارُ الموقَّعُ أو التسويةُ يقيِّده.
    - **فشلٌ أو إلغاء** — يُحسم كما كان.
    - **الوسيطُ لا يجيب، أو «قيد المعالجة» عنده** — لا نعرف: يبقى بلا حجب، والتسويةُ تسأل في الخلفية.
    """
    from app.services import payment_gateways

    row = await get_request(session, request_id)
    if row.provider.integration is None or row.external_id is None or row.status is not PaymentRequestStatus.PENDING:
        return row
    try:
        gateway = await payment_gateways.gateway_for(session, row.provider.integration, row.country_code)
        event = await gateway.check(row.external_id)
    except (payment_gateways.GatewayUnavailable, payment_gateways.GatewayError):
        return row
    raw = getattr(gateway, "last_status", None)
    locked = await get_request(session, request_id, for_update=True)
    if locked.status is not PaymentRequestStatus.PENDING:
        return locked
    if event is None:
        if raw == "pending" and locked.gateway_paid_at is None:
            _cancel_unpaid(locked, payment_reasons.NOT_COMPLETED)
        return locked
    if event.outcome is PaymentRequestStatus.APPROVED and getattr(gateway, "confirms_by_webhook", False):
        if locked.gateway_paid_at is None:
            locked.gateway_paid_at = _now()
        return locked
    await _apply_event(session, locked, event, gateway)
    return locked


def _cancel_unpaid(request: PaymentRequest, reason: str) -> None:
    request.status = PaymentRequestStatus.CANCELLED
    request.cancel_reason = reason
    request.cancelled_at = _now()


async def _apply_event(session: AsyncSession, locked: PaymentRequest, event, gateway) -> None:
    if event.outcome is PaymentRequestStatus.APPROVED:
        paid_fee = _fee_of(locked.fee_payer, event.fee_on_customer, event.fee_on_merchant)
        if paid_fee is not None:
            locked.fee_amount = paid_fee
    await apply_gateway_outcome(
        session, request=locked, outcome=event.outcome, amount=event.amount, reason=event.reason,
        test_money=bool(getattr(gateway, "test_mode", False)),
    )


async def reconcile_gateway(session: AsyncSession, *, now: datetime | None = None) -> int:
    """**التسويةُ الدوريّة** (SPEC §٨٢-أ/٥) — كلَّ دقيقتين: **كلُّ دفعةٍ عند وسيطٍ بلا حالٍ نهائيّ** يُسأل عنها الوسيطُ ويُطبَّق جوابُه.

    - **«دُفع»** ⇐ يُختم «قيد المعالجة» ثمّ يُقيَّد **مرّةً واحدة** بعد `WEBHOOK_GRACE_SECONDS` إن لم يسبقه الإشعارُ الموقَّع — **من
      جواب الوسيط المباشر** (`GET /checkouts/{id}` بمفتاحنا السرّيّ، الخلفيةُ إليه لا التطبيق)؛ وقيدُ الدفتر بمفتاح الطلب فلا يُكتب مرّتين.
    - **ما أُلغي عندنا بلا جوابٍ نهائيّ** (عاد ولم يُكمل · مهلتُنا) يُراجع في مهلة الصفحة — **ودفعٌ اكتمل بعده يُقيَّد ولا يضيع**.
    - **«قيد المعالجة» أطولَ من `REVIEW_ALERT_MINUTES`** ⇐ يُشعَر المالكُ مرّةً واحدة.
    - **ولكلِّ طلبٍ معاملتُه**، والوسيطُ يُسأل قبل القفل لا تحته.
    """
    from app.core.redis_client import get_redis_client
    from app.services import payment_gateways

    moment = now or _now()
    window = moment - timedelta(hours=CHECKOUT_TTL_HOURS)
    late_window = moment - timedelta(hours=RECHECK_LATE_HOURS)
    # **وما ألغته المهلةُ وقال وسيطُه «قيد المعالجة»** يُراجَع أيضاً — سببُه مكتوبٌ باسم الوسيط
    recheck = RECHECK_CANCELLED | {
        payment_reasons.EXPIRED_PROCESSING.format(name) for name in payment_gateways.DISPLAY_NAMES.values()
    }
    ids = (
        await session.scalars(
            select(PaymentRequest.id)
            .join(PayMethod, PayMethod.id == PaymentRequest.provider_id)
            .where(
                PayMethod.integration.is_not(None),
                PaymentRequest.external_id.is_not(None),
                or_(
                    (PaymentRequest.status == PaymentRequestStatus.PENDING)
                    & ((PaymentRequest.created_at > window) | PaymentRequest.gateway_paid_at.is_not(None)),
                    (PaymentRequest.status == PaymentRequestStatus.CANCELLED)
                    & PaymentRequest.cancelled_by.is_(None)
                    & PaymentRequest.cancel_reason.in_(recheck)
                    & (PaymentRequest.created_at > late_window),
                ),
            )
            .order_by(PaymentRequest.created_at)
            .limit(200)
        )
    ).all()
    settled = 0
    redis = get_redis_client()
    for request_id in ids:
        row = await get_request(session, request_id)
        try:
            gateway = await payment_gateways.gateway_for(session, row.provider.integration or "", row.country_code)
            event = await gateway.check(row.external_id or "")
        except (payment_gateways.GatewayUnavailable, payment_gateways.GatewayError):
            await session.rollback()
            continue
        locked = await get_request(session, request_id, for_update=True)
        paid = event is not None and event.outcome is PaymentRequestStatus.APPROVED
        if locked.status is PaymentRequestStatus.CANCELLED:
            if not paid:
                await session.commit()
                continue
            _reopen_for_late_payment(locked)
        elif locked.status is not PaymentRequestStatus.PENDING:
            await session.commit()
            continue
        if paid:
            if locked.gateway_paid_at is None:
                locked.gateway_paid_at = moment
            if (moment - locked.gateway_paid_at).total_seconds() >= WEBHOOK_GRACE_SECONDS:
                await _apply_event(session, locked, event, gateway)
        elif event is not None:
            await _apply_event(session, locked, event, gateway)
        if (
            locked.status is PaymentRequestStatus.PENDING
            and locked.gateway_paid_at is not None
            and moment - locked.gateway_paid_at >= timedelta(minutes=REVIEW_ALERT_MINUTES)
            and await redis.set(f"payreq:stuck:{locked.id}", "1", nx=True, ex=7 * 86400)
        ):
            _flag("payment_stuck", session=session, request=locked)
        if locked.status is not PaymentRequestStatus.PENDING:
            settled += 1
        await session.commit()
    return settled


async def open_checkout_once(
    session: AsyncSession,
    *,
    owner: User,
    provider_id: uuid.UUID,
    purpose: PaymentRequestPurpose,
    amount: Decimal | None,
    plan_id: uuid.UUID | None,
    declared: WalletOwnerType | None,
    opened_from: str,
) -> tuple[PaymentRequest, str]:
    """**نقرتان سريعتان على «ادفع» صفحةٌ واحدة** (SPEC §٨٢-أ/٤) — قفلٌ في Redis للدافع والغرض والمبلغ والخطّة:

    الأولى تفتح الصفحةَ وتكتب معرّفَها في القفل؛ **والثانيةُ تنتظرها ثمّ تعيد الصفحةَ نفسَها** — لا طلبَ ثانياً ولا صفحةَ ثانية.
    """
    import asyncio

    from app.core.redis_client import get_redis_client

    redis = get_redis_client()
    key = f"checkout:open:{owner.id}:{purpose.value}:{amount}:{plan_id}"
    if not await redis.set(key, "opening", nx=True, ex=CHECKOUT_LOCK_SECONDS):
        for _ in range(40):
            value = await redis.get(key)
            text = value.decode() if isinstance(value, bytes) else value
            if text and "|" in text:
                request_id, url = text.split("|", 1)
                for _ in range(20):
                    row = await session.scalar(
                        select(PaymentRequest).where(PaymentRequest.id == uuid.UUID(request_id)).execution_options(populate_existing=True)
                    )
                    if row is not None:
                        return row, url
                    await asyncio.sleep(0.15)
                break
            if text is None:
                break
            await asyncio.sleep(0.25)
        raise Conflict("صفحةُ الدفع تُفتح الآن — انتظر لحظة")
    try:
        request, url = await start_checkout(
            session, owner=owner, provider_id=provider_id, purpose=purpose, amount=amount, plan_id=plan_id,
            declared=declared, opened_from=opened_from,
        )
    except BaseException:
        await redis.delete(key)
        raise
    if DOUBLE_TAP_SECONDS > 0:
        await redis.set(key, f"{request.id}|{url}", ex=DOUBLE_TAP_SECONDS)
    else:
        await redis.delete(key)
    return request, url

