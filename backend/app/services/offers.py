"""عروضُ الاشتراكات — الاستحقاقُ والاختيارُ والحساب (البند ٥٤).

**والخصمُ يُحسب مرةً واحدةً في مسار الشراء**، ويُمرَّر إلى `subscriptions._create`
الذي يكتب أعمدتَه الأربعة. وسببُ ألّا يُحسب داخل `_create` وحدَه ماليٌّ لا
تنظيميّ: مسارُ المحفظة **يخصم من الرصيد قبل أن يُكتب الصفّ**، فحسابٌ داخلَ
الكاتب يخصم السعرَ كاملاً ويكتب المخفَّض — وهو مالٌ من عدم.

**ولا يُخترع قفلٌ جديد**: قفلُ صفّ الكبتن (`subscriptions._locked_driver`) مأخوذٌ
سلفاً في كل مسارٍ يشتري، فعدُّ استعمالاته يقع داخله. والمُخترَعُ هنا قفلُ **صفّ
العرض** وحدَه، وهو ما تحتاجه الميزانية.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, InvalidInput, NotFound
from app.models.driver import Driver
from app.models.enums import CountryCode
from app.models.subscription import DriverSubscription, SubscriptionPlan
from app.models.subscription_offer import (
    AUDIENCE_ALL,
    AUDIENCE_LAPSED,
    AUDIENCE_MANUAL,
    AUDIENCE_NEW_DRIVER,
    DISCOUNT_MONEY_PERCENT,
    SubscriptionOffer,
    SubscriptionOfferGrant,
)
from app.services import settings_service

FEATURE_KEY = "subscription_offers_enabled"

_CENT = Decimal("0.001")


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ResolvedOffer:
    """العرضُ الفائز ومبلغُ خصمه على خطةٍ بعينها لكبتنٍ بعينه."""

    offer: SubscriptionOffer
    amount: Decimal


@dataclass(frozen=True)
class ExhaustedOffer:
    """عرضٌ **كان** ينطبق على هذا الكبتن واستنفد حدَّه.

    **وهو غيرُ «لا عرضَ له»**، ولذلك صنفٌ مستقلٌّ لا `None`: من رأى الخصمَ ثم
    اختفى يظنّ العرضَ انتهى أو أن التطبيق عطب — والصمتُ هنا يصنع سؤالاً للدعم.
    ومن لم يستحقّ قطُّ لا يُقال له شيء (الفرع و)، فالتمييزُ بينهما هو المقصود.
    """

    offer: SubscriptionOffer


def discount_on(offer: SubscriptionOffer, plan: SubscriptionPlan) -> Decimal:
    """مبلغُ الخصم — نسبةً من سعر الخطة، بسقفه إن وُجد.

    **ولا ينزل السعرُ تحت الصفر**: نسبةٌ مئةٌ تجعل الاشتراكَ مجاناً ولا تجعله
    ديناً على المنصّة.
    """
    if offer.discount_type != DISCOUNT_MONEY_PERCENT:
        return Decimal("0")
    raw = (plan.price * offer.discount_value / Decimal("100")).quantize(
        _CENT, rounding=ROUND_HALF_UP
    )
    if offer.max_discount is not None:
        raw = min(raw, offer.max_discount)
    return min(raw, plan.price)


async def _uses_by_driver(
    session: AsyncSession, *, offer_id: uuid.UUID, driver_id: uuid.UUID
) -> int:
    """كم مرةً اشترى هذا الكبتنُ بهذا العرض — **عدٌّ لا عمود**.

    والعرضُ نفسُه هو النافذة (الفرع ب): `offer_id` مختومٌ على الصفّ، فعدُّ صفوفه
    عدٌّ داخل عمر العرض — بلا حساب شهرٍ تقويميٍّ وبلا حدٍّ يقع على حافّته.
    """
    return int(
        await session.scalar(
            select(func.count())
            .select_from(DriverSubscription)
            .where(
                DriverSubscription.offer_id == offer_id,
                DriverSubscription.driver_id == driver_id,
            )
        )
        or 0
    )


async def _committed_giveaway(session: AsyncSession, offer_id: uuid.UUID) -> Decimal:
    """مجموعُ ما تُنوزل عنه فعلاً بهذا العرض.

    **وأبسطُ من سقف الكوبون**: الصفُّ لا يوجد إلا وقد وصل ماله، فلا «رحلاتٌ في
    الطريق» تُحسب كما في 12-ز.
    """
    return Decimal(
        await session.scalar(
            select(func.coalesce(func.sum(DriverSubscription.discount_amount), 0)).where(
                DriverSubscription.offer_id == offer_id
            )
        )
        or 0
    )


async def _is_eligible(
    session: AsyncSession, offer: SubscriptionOffer, driver: Driver
) -> bool:
    """جمهورُ العرض — **مقارنةٌ حيّةٌ لحظةَ الشراء** لا عمودٌ يُختم."""
    if offer.audience == AUDIENCE_ALL:
        return True

    if offer.audience == AUDIENCE_NEW_DRIVER:
        # «لا اشتراكَ له قطُّ» — وهو شرطُ الإحالة نفسُه مقلوباً، فيُقرأ من مكانٍ واحد
        return not bool(
            await session.scalar(
                select(func.count())
                .select_from(DriverSubscription)
                .where(DriverSubscription.driver_id == driver.id)
            )
        )

    if offer.audience == AUDIENCE_LAPSED:
        from app.services.subscriptions import coverage_until

        covered_until = await coverage_until(session, driver.id)
        # **ولا يُعرض لمن تغطيتُه سارية** (الفرع و): وإلا صار العرضُ إعلاناً
        # بأن الانقطاع يُكافأ
        if covered_until is None:
            return True
        days = offer.lapsed_days or 0
        return (_now() - covered_until).days >= days

    if offer.audience == AUDIENCE_MANUAL:
        return bool(
            await session.scalar(
                select(func.count())
                .select_from(SubscriptionOfferGrant)
                .where(
                    SubscriptionOfferGrant.offer_id == offer.id,
                    SubscriptionOfferGrant.driver_id == driver.id,
                )
            )
        )

    return False


async def resolve(
    session: AsyncSession,
    *,
    driver: Driver,
    plan: SubscriptionPlan,
    for_update: bool = False,
) -> ResolvedOffer | None:
    """العرضُ الذي ينطبق على هذا الشراء — أو `None`.

    **والأكبرُ وحدَه، وعند التساوي الأحدث** (الفرع د): بلا عمود أولوية، حتميٌّ،
    والكبتنُ يأخذ الأفضلَ دائماً فلا تنشأ شكوى «لماذا لم أنل الآخر».

    و`for_update` يقفل صفَّ العرض الفائز — يطلبه **مسارُ الشراء** وحدَه، ولا
    تطلبه قراءةُ الشاشة: قفلٌ في مسار عرضٍ يُسلسِل قرّاءَ قائمة الخطط بلا سبب.
    """
    if not await settings_service.is_feature_enabled(
        session, plan.country_code, FEATURE_KEY
    ):
        return None

    now = _now()
    rows = (
        await session.execute(
            select(SubscriptionOffer).where(
                SubscriptionOffer.country_code == plan.country_code,
                SubscriptionOffer.is_active.is_(True),
                SubscriptionOffer.plan_id.in_((plan.id, None))
                | SubscriptionOffer.plan_id.is_(None),
                (SubscriptionOffer.starts_at.is_(None))
                | (SubscriptionOffer.starts_at <= now),
                (SubscriptionOffer.ends_at.is_(None))
                | (SubscriptionOffer.ends_at > now),
            )
        )
    ).scalars().all()

    best: ResolvedOffer | None = None
    exhausted: list[SubscriptionOffer] = []
    for offer in rows:
        if offer.plan_id is not None and offer.plan_id != plan.id:
            continue
        if not await _is_eligible(session, offer, driver):
            continue
        if offer.max_uses_per_driver:
            used = await _uses_by_driver(
                session, offer_id=offer.id, driver_id=driver.id
            )
            if used >= offer.max_uses_per_driver:
                # **يُذكر ولا يُطبَّق**: الكبتنُ استفاد منه فعلاً، فيُقال له
                # ذلك بدل أن يختفي الخصمُ بلا كلمة
                exhausted.append(offer)
                continue

        amount = discount_on(offer, plan)
        if amount <= 0:
            continue

        if offer.total_budget is not None:
            spent = await _committed_giveaway(session, offer.id)
            if spent + amount > offer.total_budget:
                continue

        if best is None or (amount, offer.created_at) > (
            best.amount,
            best.offer.created_at,
        ):
            best = ResolvedOffer(offer=offer, amount=amount)

    if best is None or not for_update:
        return best

    # **قفلُ صفّ العرض لحظةَ الشراء وحدَه**: بغيره يمرّ ثلاثةُ مشترين متزامنين
    # على ميزانيةٍ تكفي واحداً. ويُعاد الفحصُ بعد القفل لأن ما قبله قراءةٌ قديمة.
    locked = await session.get(
        SubscriptionOffer, best.offer.id, with_for_update=True, populate_existing=True
    )
    if locked is None or not locked.is_active:
        return None
    amount = discount_on(locked, plan)
    if amount <= 0:
        return None
    if locked.total_budget is not None:
        spent = await _committed_giveaway(session, locked.id)
        if spent + amount > locked.total_budget:
            return None
    if locked.max_uses_per_driver:
        used = await _uses_by_driver(session, offer_id=locked.id, driver_id=driver.id)
        if used >= locked.max_uses_per_driver:
            return None
    return ResolvedOffer(offer=locked, amount=amount)


# ------------------------------------------------------------- الإدارة


async def list_offers(
    session: AsyncSession, country: CountryCode
) -> list[tuple[SubscriptionOffer, dict]]:
    """العروضُ ومعها جدولُ التنازل — **مجموعٌ في القاعدة لا في المتصفح** (§14).

    و«التسويةُ اليدوية» عددُ صفوفٍ خالف فيها المدفوعُ ما قرّره العرض: مقارنةٌ
    حيّةٌ بين رقمين مجمَّدين، بلا عمودٍ يُخزَّن وبلا سببٍ يُطلب من المشرف.
    """
    offers = (
        await session.execute(
            select(SubscriptionOffer)
            .where(SubscriptionOffer.country_code == country)
            .order_by(SubscriptionOffer.created_at.desc())
        )
    ).scalars().all()

    stats = {
        row.offer_id: row
        for row in (
            await session.execute(
                select(
                    DriverSubscription.offer_id,
                    func.count().label("sold"),
                    func.coalesce(func.sum(DriverSubscription.list_price), 0).label(
                        "list_total"
                    ),
                    func.coalesce(
                        func.sum(DriverSubscription.discount_amount), 0
                    ).label("given"),
                    func.count()
                    .filter(
                        DriverSubscription.discount_amount
                        != DriverSubscription.offer_discount_amount
                    )
                    .label("adjusted"),
                )
                .where(DriverSubscription.offer_id.isnot(None))
                .group_by(DriverSubscription.offer_id)
            )
        ).all()
    }

    # **المبالغُ تُكمَّم إلى ثلاث خانات** — وإلا خرج `"0"` حيث تخرج بقيةُ
    # المال `"0.000"`: عمودُ `MONEY` يُسلسَل بثلاثٍ، ومجموعٌ فارغٌ أو صفرٌ
    # مُنشأٌ في بايثون لا يُكمَّم من نفسه. وهو العطبُ نفسُه الذي وقع في
    # `rewarded_total` عند تعميم الإحالة، فأُصلح هناك ويُمنع هنا.
    def _money(value) -> Decimal:
        return Decimal(value or 0).quantize(_CENT)

    result = []
    for offer in offers:
        row = stats.get(offer.id)
        result.append(
            (
                offer,
                {
                    "subscriptions_sold": int(row.sold) if row else 0,
                    "total_list_price": _money(row.list_total if row else 0),
                    "total_given_up": _money(row.given if row else 0),
                    "manual_adjustments": int(row.adjusted) if row else 0,
                },
            )
        )
    return result


async def get_offer(session: AsyncSession, offer_id: uuid.UUID) -> SubscriptionOffer:
    offer = await session.get(SubscriptionOffer, offer_id)
    if offer is None:
        raise NotFound("العرض غير موجود")
    return offer


async def create_offer(
    session: AsyncSession, *, country: CountryCode, data: dict, actor_id: uuid.UUID
) -> SubscriptionOffer:
    offer = SubscriptionOffer(country_code=country, created_by=actor_id, **data)
    session.add(offer)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("يوجد عرضٌ بهذا الاسم في هذه الدولة") from exc
    return offer


async def update_offer(
    session: AsyncSession, *, offer_id: uuid.UUID, data: dict
) -> SubscriptionOffer:
    """تعديلٌ جزئي — **ولا يمسّ ما وقع**: الصفوفُ تحمل ما جُمِّد لحظةَ الشراء."""
    offer = await get_offer(session, offer_id)
    for key, value in data.items():
        setattr(offer, key, value)
    await session.flush()
    return offer


async def grant(
    session: AsyncSession,
    *,
    offer_id: uuid.UUID,
    driver_id: uuid.UUID,
    actor_id: uuid.UUID,
    note: str | None,
) -> SubscriptionOfferGrant:
    """منحُ عرضٍ يدويٍّ لكبتن — **ولجمهور `manual` وحدَه**.

    ومنحُ عرضٍ جمهورُه محسوبٌ يجعل صفَّ المنح لا أثرَ له، فيظنّ المشرفُ أنه
    فعل شيئاً لم يقع — وهو الشكلُ الذي يُقرأ «الميزةُ لا تعمل».
    """
    offer = await get_offer(session, offer_id)
    if offer.audience != AUDIENCE_MANUAL:
        raise InvalidInput("المنحُ اليدويُّ لعروض الجمهور اليدويِّ وحدَها")

    row = SubscriptionOfferGrant(
        offer_id=offer_id, driver_id=driver_id, granted_by=actor_id, note=note
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("هذا العرضُ ممنوحٌ لهذا الكبتن سلفاً") from exc
    return row


async def list_grants(
    session: AsyncSession, offer_id: uuid.UUID
) -> list[SubscriptionOfferGrant]:
    return list(
        (
            await session.execute(
                select(SubscriptionOfferGrant)
                .where(SubscriptionOfferGrant.offer_id == offer_id)
                .order_by(SubscriptionOfferGrant.created_at.desc())
            )
        ).scalars().all()
    )


async def exhausted_for(
    session: AsyncSession, *, driver: Driver, plan: SubscriptionPlan
) -> ExhaustedOffer | None:
    """عرضٌ استنفد هذا الكبتنُ حدَّه فيه — أو `None`.

    **ويُسأل بعد `resolve` لا بدلاً منها**: من ينطبق عليه عرضٌ آخرُ يرى خصمَه،
    ولا يُقال له عن عرضٍ استنفده — فسطرٌ عن عرضٍ منتهٍ فوق خصمٍ قائمٍ يربك.

    ولا يُفحص الجمهورُ ثانيةً هنا: من استُهلك له صفٌّ بهذا العرض كان مستحقاً
    لحظتَها بحكم وجود الصفّ.
    """
    if not await settings_service.is_feature_enabled(
        session, plan.country_code, FEATURE_KEY
    ):
        return None

    now = _now()
    rows = (
        await session.execute(
            select(SubscriptionOffer).where(
                SubscriptionOffer.country_code == plan.country_code,
                SubscriptionOffer.is_active.is_(True),
                SubscriptionOffer.max_uses_per_driver > 0,
                (SubscriptionOffer.ends_at.is_(None))
                | (SubscriptionOffer.ends_at > now),
            )
        )
    ).scalars().all()

    for offer in rows:
        if offer.plan_id is not None and offer.plan_id != plan.id:
            continue
        used = await _uses_by_driver(session, offer_id=offer.id, driver_id=driver.id)
        if used >= offer.max_uses_per_driver:
            return ExhaustedOffer(offer=offer)
    return None
