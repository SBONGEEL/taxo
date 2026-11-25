"""**عروضُ الركاب** (أمرُ المالك ٢٠٢٦-١١-٢٤ السادس، الجزء د؛ SPEC §١١٤-د) — **مسوّداتٌ مطفأةٌ حتى يضع المالكُ القيمَ ويعتمد.**

## من يتحمّل الخصم — قاعدةُ المالك

* **خلال فترة الكبتن المجّانيّة** (`launch_campaign.in_free_period`): **الكبتنُ إلزاماً**، شريكاً لـTAXO في الإطلاق.
* **بعدها**: دافعُ كلِّ عرضٍ من اللوحة (`promo_codes.bearer_after_free`) — `company` كما كان كلُّ كوبونٍ قبل اليوم، أو `captain`.
* **ويُجمَّد عند قبول الكبتن** (`rides.discount_bearer`) — فما رآه في بطاقة العرض قبل القبول هو ما يقع.

**ومتى تحمّله الكبتن** فالخصمُ **سطرٌ سالبٌ في الأجرة** (`offer_discount`) لا دفعةُ `promo` — كخصم اشتراك الراكب الذي يتحمّله الكبتن (§٩٧/١٣):
الأجرةُ تنقص به فيقبض الكبتنُ الباقي **وتُحسب العمولةُ على ما بقي**، **ولا مالَ يخرج من TAXO**. **ومتى تحمّلته TAXO** فهو دفعةُ `promo` كما كان.

## العروض

* `launch` «خصم الافتتاح» — لكلِّ راكبٍ في سوقه، **ونقاطُ التزامٍ إضافيّةٌ للكبتن** (`points_per_ride`، لا مال).
* `first_ride` «أول رحلة» — لراكبٍ بلا رحلةٍ مكتملة.
* `invite` «ادعُ صديقك» — استحقاقٌ للصديق عند ربط الإحالة، وللداعي عند أوّل رحلةٍ مكتملةٍ للصديق؛ **رحلةٌ واحدةٌ لكلٍّ**.
* **بلا تراكب**: عرضٌ واحدٌ للرحلة، والرمزُ الذي يكتبه الراكبُ يسبقها؛ **وسقوفُ الميزانية والحدُّ الأقصى للخصم** حقولُ الرمز نفسِه (يضعها المالك).
* **قسائمُ المتاجر الشريكة** — نصٌّ يعرضه التطبيق، والخصمُ على المتجر لا على TAXO.
* **المزايا غيرُ النقديّة** — إلغاءٌ مجّانيٌّ خلال ثوانٍ من القبول، وشارةُ «راكب مميز» بعد عددِ رحلات.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, InvalidInput, NotFound
from app.models.driver import Driver
from app.models.enums import AuditAction, CountryCode, RideStatus
from app.models.promo import PromoCode
from app.models.ride import Ride
from app.models.rider_offer import (
    ENTITLEMENT_FRIEND,
    ENTITLEMENT_INVITER,
    PartnerCoupon,
    RiderOfferEntitlement,
    RiderPerks,
)
from app.models.user import User

KIND_CODE = "code"
KIND_LAUNCH = "launch"
KIND_FIRST_RIDE = "first_ride"
KIND_INVITE = "invite"
AUTO_KINDS = (KIND_FIRST_RIDE, KIND_INVITE, KIND_LAUNCH)
BEARER_COMPANY = "company"
BEARER_CAPTAIN = "captain"

KIND_LABEL = {
    KIND_CODE: "كوبون",
    KIND_LAUNCH: "خصم الافتتاح",
    KIND_FIRST_RIDE: "أول رحلة",
    KIND_INVITE: "ادعُ صديقك",
}


def _now() -> datetime:
    return datetime.now(UTC)


async def _active(session: AsyncSession, country: CountryCode, kind: str) -> PromoCode | None:
    """**قراءةٌ بلا قفل** — والحدودُ والميزانيةُ يقفلها `promo.freeze` على صفِّ الرمز نفسِه."""
    now = _now()
    stmt = (
        select(PromoCode)
        .where(
            PromoCode.country_code == country,
            PromoCode.kind == kind,
            PromoCode.is_active.is_(True),
            or_(PromoCode.valid_from.is_(None), PromoCode.valid_from <= now),
            or_(PromoCode.valid_until.is_(None), PromoCode.valid_until >= now),
        )
        .order_by(PromoCode.created_at.desc())
        .limit(1)
    )
    return await session.scalar(stmt)


async def _completed_rides(session: AsyncSession, rider_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(Ride).where(Ride.rider_id == rider_id, Ride.status == RideStatus.COMPLETED)
        )
        or 0
    )


# ===================================================================== التطبيقُ الآليّ عند الطلب


async def auto_apply(session: AsyncSession, *, ride: Ride, rider: User) -> PromoCode | None:
    """**عرضٌ واحدٌ بلا رمز** — أوّلُ رحلة، ثمّ استحقاقُ الدعوة، ثمّ خصمُ الافتتاح. **ولا شيءَ لرحلةٍ تحمل رمزاً** (لا تراكب).

    والتجميدُ من بابِ الرمز نفسِه (`promo.freeze`) بحدوده وقفلِ صفّه — **ورفضُه يُبتلع**: عرضٌ نفدت ميزانيتُه لا يُسقط طلبَ رحلة.
    """
    from app.services import promo as promo_service

    if ride.promo_code_id is not None or rider.is_test:
        return None
    if not await promo_service.enabled_in(session, ride.country_code):
        return None
    candidates: list[tuple[PromoCode, RiderOfferEntitlement | None]] = []
    first = await _active(session, ride.country_code, KIND_FIRST_RIDE)
    if first is not None and await _completed_rides(session, rider.id) == 0:
        candidates.append((first, None))
    entitlement = await session.scalar(
        select(RiderOfferEntitlement)
        .join(PromoCode, PromoCode.id == RiderOfferEntitlement.promo_code_id)
        .where(
            RiderOfferEntitlement.rider_id == rider.id,
            RiderOfferEntitlement.used_ride_id.is_(None),
            PromoCode.is_active.is_(True),
        )
        .order_by(RiderOfferEntitlement.created_at)
        .limit(1)
    )
    if entitlement is not None:
        invite = await session.get(PromoCode, entitlement.promo_code_id)
        if invite is not None:
            candidates.append((invite, entitlement))
    launch = await _active(session, ride.country_code, KIND_LAUNCH)
    if launch is not None:
        candidates.append((launch, None))
    for promo, held in candidates:
        try:
            async with session.begin_nested():
                await promo_service.freeze(session, ride=ride, rider=rider, promo=promo)
                if held is not None:
                    held.used_ride_id = ride.id
                await session.flush()
            return promo
        except AppError:
            continue
    return None


# ===================================================================== من يتحمّل — عند العرض والقبول


async def bearer_for(session: AsyncSession, *, ride: Ride, driver: Driver) -> str | None:
    from app.models.enums import FeatureKey
    from app.services import launch_campaign, settings_service

    if ride.promo_code_id is None:
        return None
    # **الكبتنُ يتحمّل في فترته المجّانية بمفتاحها وحدَه** (أمرُ المالك الحادي عشر ٢٠٢٦-١١-٢٥): الحملةُ مشتعلةٌ والقاعدةُ مطفأةٌ حتى
    # ينشر المالكُ شروطها — **فإشعالُ الحملة لا يُحمِّل كبتناً خصماً**، ويبقى الدافعُ ما اختاره العرضُ كما قبلها
    if await launch_campaign.in_free_period(session, driver) and await settings_service.is_feature_enabled(
        session, ride.country_code, FeatureKey.LAUNCH_CAPTAIN_BEARS_DISCOUNTS
    ):
        return BEARER_CAPTAIN
    promo = await session.get(PromoCode, ride.promo_code_id)
    return promo.bearer_after_free if promo is not None else BEARER_COMPANY


async def freeze_bearer(session: AsyncSession, *, ride: Ride, driver: Driver) -> None:
    """**يُجمَّد عند القبول تحت قفل صفِّ الرحلة** (`rides._take`)."""
    ride.discount_bearer = await bearer_for(session, ride=ride, driver=driver)


async def offer_card(session: AsyncSession, *, ride: Ride, driver_id: uuid.UUID) -> dict | None:
    """**ما يراه الكبتنُ في بطاقة العرض قبل القبول**: أنّ في الطلب خصماً، ومقدارَه التقديريّ، ومن يتحمّله، **وصافيَه**."""
    from app.services import pricing
    from app.services import promo as promo_service

    if ride.promo_code_id is None:
        return None
    driver = await session.get(Driver, driver_id)
    if driver is None:
        return None
    promo = await session.get(PromoCode, ride.promo_code_id)
    base = pricing.discountable(ride.estimated_fare, ride.captain_fees_at_ride)
    discount = promo_service.discount_on_ride(ride, base)
    if discount <= 0:
        return None
    bearer = await bearer_for(session, ride=ride, driver=driver)
    net = ride.estimated_fare - discount if bearer == BEARER_CAPTAIN else ride.estimated_fare
    return {
        "label": KIND_LABEL.get(promo.kind if promo is not None else KIND_CODE, "عرض"),
        "discount": str(discount),
        "captain_bears": bearer == BEARER_CAPTAIN,
        "net_estimate": str(pricing.round_money(net, ride.currency)),
    }


async def offer_card_for_user(session: AsyncSession, *, ride: Ride, user_id: uuid.UUID) -> dict | None:
    if ride.promo_code_id is None:
        return None
    driver_id = await session.scalar(select(Driver.id).where(Driver.user_id == user_id))
    return await offer_card(session, ride=ride, driver_id=driver_id) if driver_id is not None else None


# ===================================================================== بعد الإنهاء


async def on_completed(session: AsyncSession, ride: Ride) -> None:
    """**نقاطُ خصم الافتتاح للكبتن، واستحقاقُ الداعي عند أوّل رحلةٍ للصديق** — لا مال."""
    from app.models.referral import Referral

    from app.services import commitment

    if ride.promo_code_id is not None:
        promo = await session.get(PromoCode, ride.promo_code_id)
        if promo is not None and promo.kind == KIND_LAUNCH and promo.points_per_ride:
            await commitment.award_discounted_ride(session, ride, promo.points_per_ride)
    invite = await _active(session, ride.country_code, KIND_INVITE)
    if invite is None or await _completed_rides(session, ride.rider_id) != 1:
        return
    referral = await session.scalar(select(Referral).where(Referral.referred_user_id == ride.rider_id))
    if referral is None:
        return
    await _entitle(session, rider_id=referral.referrer_user_id, promo=invite, source=ENTITLEMENT_INVITER, referral=referral.id)


async def on_referral(session: AsyncSession, *, referred: User, referral_id: uuid.UUID) -> None:
    """**الصديقُ المدعوّ يستحقّ رحلةً بخصم** لحظةَ ربط الإحالة — إن كان العرضُ مفعَّلاً في سوقه."""
    invite = await _active(session, referred.country_code, KIND_INVITE)
    if invite is not None and not referred.is_test:
        await _entitle(session, rider_id=referred.id, promo=invite, source=ENTITLEMENT_FRIEND, referral=referral_id)


async def _entitle(
    session: AsyncSession, *, rider_id: uuid.UUID, promo: PromoCode, source: str, referral: uuid.UUID
) -> None:
    from sqlalchemy.exc import IntegrityError

    row = RiderOfferEntitlement(rider_id=rider_id, promo_code_id=promo.id, source=source, referral_id=referral)
    session.add(row)
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError:
        return


# ===================================================================== تقريرُ خصم الكبتن


def _offer_discount_of(ride: Ride) -> Decimal:
    total = Decimal("0")
    for line in ride.fare_lines or []:
        if isinstance(line, dict) and line.get("kind") == "offer_discount":
            total += -Decimal(str(line.get("amount", "0")))
    return total


async def captain_discounts(session: AsyncSession, *, driver_id: uuid.UUID, month: date) -> dict:
    """**كلُّ رحلةٍ تحمّل الكبتنُ خصمَها في الشهر، ومجموعُها** — من سطر الأجرة نفسِه."""
    start = datetime(month.year, month.month, 1, tzinfo=UTC)
    end = (start + timedelta(days=32)).replace(day=1)
    rides = (
        await session.execute(
            select(Ride)
            .where(
                Ride.driver_id == driver_id,
                Ride.discount_bearer == BEARER_CAPTAIN,
                Ride.status == RideStatus.COMPLETED,
                Ride.completed_at >= start,
                Ride.completed_at < end,
            )
            .order_by(Ride.completed_at.desc())
        )
    ).scalars().all()
    rows = []
    total = Decimal("0")
    for ride in rides:
        amount = _offer_discount_of(ride)
        total += amount
        promo = await session.get(PromoCode, ride.promo_code_id) if ride.promo_code_id else None
        rows.append(
            {
                "ride_id": str(ride.id),
                "completed_at": ride.completed_at.isoformat() if ride.completed_at else None,
                "label": KIND_LABEL.get(promo.kind if promo is not None else KIND_CODE, "عرض"),
                "discount": str(amount),
                "fare": str(ride.final_fare) if ride.final_fare is not None else None,
                "currency": ride.currency.value,
            }
        )
    return {"month": f"{month:%Y-%m}", "rides": rows, "total": str(total), "count": len(rows)}


# ===================================================================== المزايا غيرُ النقديّة


async def perks(session: AsyncSession, country: CountryCode) -> RiderPerks:
    from sqlalchemy.exc import IntegrityError

    row = await session.scalar(select(RiderPerks).where(RiderPerks.country_code == country))
    if row is None:
        # **الصفُّ يُضاف داخل نقطة الحفظ لا قبلها**: `begin_nested` يدفع المعلَّقَ قبل أن يفتحها، فيسقط تكرارُ مسحين متزامنين
        # خارجها ويُفسد المعاملةَ كلَّها (قِيس: `PendingRollbackError` في `test_two_concurrent_sweeps_grant_once`)
        try:
            async with session.begin_nested():
                row = RiderPerks(country_code=country)
                session.add(row)
                await session.flush()
        except IntegrityError:
            row = await session.scalar(select(RiderPerks).where(RiderPerks.country_code == country))
            assert row is not None
    return row


async def free_cancel_applies(session: AsyncSession, ride: Ride, now: datetime | None = None) -> bool:
    """**إلغاءٌ مجّانيٌّ خلال ثوانٍ من قبول الكبتن** — فارغٌ = مطفأ."""
    if ride.accepted_at is None:
        return False
    row = await perks(session, ride.country_code)
    if row.free_cancel_seconds is None:
        return False
    return ((now or _now()) - ride.accepted_at).total_seconds() <= row.free_cancel_seconds


async def is_premium(session: AsyncSession, rider: User) -> bool:
    """**«راكب مميز»** بعد عددِ رحلاتٍ مكتملةٍ يضعه المالك — فارغٌ = مطفأ."""
    row = await perks(session, rider.country_code)
    if row.premium_after_rides is None:
        return False
    return await _completed_rides(session, rider.id) >= row.premium_after_rides


async def priority_for(session: AsyncSession, rider: User) -> bool:
    row = await perks(session, rider.country_code)
    return bool(row.premium_priority) and await is_premium(session, rider)


PERK_FIELDS = ("free_cancel_seconds", "premium_after_rides", "premium_priority")


async def update_perks(session: AsyncSession, *, country: CountryCode, changes: dict, actor: User) -> RiderPerks:
    from app.services import audit

    row = await perks(session, country)
    diff: dict[str, dict] = {}
    for key in PERK_FIELDS:
        if key in changes and getattr(row, key) != changes[key]:
            diff[key] = {"from": getattr(row, key), "to": changes[key]}
            setattr(row, key, changes[key])
    if row.free_cancel_seconds is not None and not (30 <= row.free_cancel_seconds <= 900):
        raise InvalidInput("بين ٣٠ و٩٠٠ ثانية", field="free_cancel_seconds")
    if row.premium_after_rides is not None and not (1 <= row.premium_after_rides <= 1000):
        raise InvalidInput("بين ١ و١٠٠٠ رحلة", field="premium_after_rides")
    if diff:
        await audit.record(
            session, actor=actor, action=AuditAction.UPDATE, entity_type="rider_perks", entity_id=row.id,
            details={"country_code": country.value}, changes=diff,
        )
    await session.flush()
    return row


# ===================================================================== قسائمُ المتاجر


COUPON_FIELDS = ("shop_name", "shop_area", "title", "details", "coupon_code", "valid_from", "valid_until", "is_active", "sort_order")


async def list_coupons(session: AsyncSession, country: CountryCode, *, live_only: bool) -> list[PartnerCoupon]:
    stmt = select(PartnerCoupon).where(PartnerCoupon.country_code == country)
    if live_only:
        now = _now()
        stmt = stmt.where(
            PartnerCoupon.is_active.is_(True),
            or_(PartnerCoupon.valid_from.is_(None), PartnerCoupon.valid_from <= now),
            or_(PartnerCoupon.valid_until.is_(None), PartnerCoupon.valid_until >= now),
        )
    return list((await session.execute(stmt.order_by(PartnerCoupon.sort_order, PartnerCoupon.created_at))).scalars())


async def save_coupon(
    session: AsyncSession, *, country: CountryCode, data: dict, actor: User, coupon_id: uuid.UUID | None = None
) -> PartnerCoupon:
    from app.services import audit

    if coupon_id is None:
        row = PartnerCoupon(country_code=country, created_by=actor.id)
        session.add(row)
        action = AuditAction.CREATE
    else:
        row = await session.get(PartnerCoupon, coupon_id)
        if row is None or row.country_code != country:
            raise NotFound("القسيمة غير موجودة")
        action = AuditAction.UPDATE
    for key in COUPON_FIELDS:
        if key in data:
            setattr(row, key, data[key])
    if not (row.shop_name or "").strip() or not (row.title or "").strip():
        raise InvalidInput("اسمُ المتجر والعنوانُ مطلوبان", field="title")
    await session.flush()
    await audit.record(
        session, actor=actor, action=action, entity_type="partner_coupon", entity_id=row.id,
        details={"country_code": country.value, "fields": sorted(k for k in data if k in COUPON_FIELDS)},
    )
    return row


@dataclass(frozen=True, slots=True)
class RiderOffersView:
    premium: bool
    premium_after_rides: int | None
    completed_rides: int
    free_cancel_seconds: int | None
    offers: list[dict]
    coupons: list[dict]


async def rider_view(session: AsyncSession, rider: User) -> RiderOffersView:
    """**صفحةُ «العروض» للراكب** — ما يُطبَّق عليه الآن بلا أرقامٍ لم تُضبط، والقسائمُ، والمزايا."""
    perk = await perks(session, rider.country_code)
    completed = await _completed_rides(session, rider.id)
    offers = []
    for kind in AUTO_KINDS:
        promo = await _active(session, rider.country_code, kind)
        if promo is None:
            continue
        if kind == KIND_FIRST_RIDE and completed > 0:
            continue
        offers.append(
            {
                "kind": kind,
                "label": KIND_LABEL[kind],
                "discount_type": promo.discount_type.value,
                "discount_value": str(promo.discount_value),
                "max_discount": str(promo.max_discount) if promo.max_discount is not None else None,
            }
        )
    coupons = [
        {
            "id": str(row.id),
            "shop_name": row.shop_name,
            "shop_area": row.shop_area,
            "title": row.title,
            "details": row.details,
            "coupon_code": row.coupon_code,
            "valid_until": row.valid_until.isoformat() if row.valid_until else None,
        }
        for row in await list_coupons(session, rider.country_code, live_only=True)
    ]
    return RiderOffersView(
        premium=perk.premium_after_rides is not None and completed >= perk.premium_after_rides,
        premium_after_rides=perk.premium_after_rides,
        completed_rides=completed,
        free_cancel_seconds=perk.free_cancel_seconds,
        offers=offers,
        coupons=coupons,
    )
