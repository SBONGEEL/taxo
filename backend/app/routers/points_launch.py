"""**نقاطُ الالتزام وحملةُ الإطلاق وعروضُ الركاب** — أبوابُ التطبيقين (§١١٤، أمرُ المالك ٢٠٢٦-١١-٢٤ السادس)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import APIRouter, Query

from app.core.deps import CurrentDriver, CurrentUser, DbSession, RedisDep, RiderUser
from app.schemas.points_launch import (
    AckOut,
    CaptainDiscountsOut,
    ConvertIn,
    ConvertOut,
    CreditPurchaseIn,
    LaunchCampaignOut,
    MyCommitmentOut,
    RiderOffersOut,
)
from app.schemas.subscription import SubscriptionOut
from app.services import commitment, launch_campaign, rider_offers

router = APIRouter(tags=["points-launch"])


@router.get("/drivers/me/commitment", response_model=MyCommitmentOut)
async def my_commitment(driver: CurrentDriver, user: CurrentUser, session: DbSession, redis: RedisDep) -> MyCommitmentOut:
    """**بطاقةُ «نقاط الالتزام» في الرئيسيّة** — ساعاتُ اليوم والاستراحات والمتبقّي والرصيدان، وآخرُ أربعة عشر يوماً بأسبابها."""
    view = await commitment.driver_view(session, redis, driver=driver, user=user)
    await session.commit()
    return MyCommitmentOut.model_validate(view, from_attributes=True)


@router.post("/drivers/me/commitment/convert", response_model=ConvertOut)
async def convert_points(payload: ConvertIn, driver: CurrentDriver, user: CurrentUser, session: DbSession) -> ConvertOut:
    """**نقاطٌ ⇐ رصيدُ اشتراك** — لا يُسحب ولا يُحوَّل ولا يُصرف إلا اشتراكاً."""
    result = await commitment.convert(session, driver=driver, user=user, points=payload.points)
    await session.commit()
    return ConvertOut(points=result.points, amount=result.amount, currency=result.currency, credit_balance=result.credit_balance)


@router.post("/subscriptions/credit", response_model=SubscriptionOut)
async def buy_with_credit(
    payload: CreditPurchaseIn, driver: CurrentDriver, user: CurrentUser, session: DbSession
) -> SubscriptionOut:
    """**اشتراكٌ من رصيد الاشتراك** — كاملاً، بالثمن الذي تعرضه الشاشة."""
    subscription = await commitment.purchase_with_credit(
        session, driver=driver, user=user, plan_id=payload.plan_id, idempotency_key=payload.idempotency_key
    )
    await session.commit()
    return SubscriptionOut.from_subscription(subscription)


@router.get("/drivers/me/launch-campaign", response_model=LaunchCampaignOut)
async def my_launch_campaign(driver: CurrentDriver, user: CurrentUser, session: DbSession) -> LaunchCampaignOut:
    """**لافتةُ الحملة والعدُّ التنازليّ وحالُ هذا الكبتن** — وإشعارُ «شريك الإطلاق» إن لم يُقرّ به."""
    view = await launch_campaign.view(session, user.country_code, driver)
    await session.commit()
    return LaunchCampaignOut.model_validate(view, from_attributes=True)


@router.post("/drivers/me/launch-campaign/ack", response_model=AckOut)
async def acknowledge_partner(driver: CurrentDriver, session: DbSession) -> AckOut:
    """**إقرارُ «شريك الإطلاق»** مرّةً واحدة — بقيد تدقيق."""
    at = await launch_campaign.acknowledge(session, driver)
    await session.commit()
    return AckOut(acknowledged_at=at)


@router.get("/drivers/me/offer-discounts", response_model=CaptainDiscountsOut)
async def my_offer_discounts(
    driver: CurrentDriver, session: DbSession, month: date | None = Query(default=None)
) -> CaptainDiscountsOut:
    """**تقريرُ خصوم العروض التي تحمّلها الكبتن** — رحلةً رحلةً ومجموعُ الشهر."""
    target = month or datetime.now(UTC).date()
    return CaptainDiscountsOut.model_validate(
        await rider_offers.captain_discounts(session, driver_id=driver.id, month=target)
    )


@router.get("/rider-offers", response_model=RiderOffersOut)
async def my_rider_offers(rider: RiderUser, session: DbSession) -> RiderOffersOut:
    """**صفحةُ «العروض» للراكب** — ما يُطبَّق عليه، وقسائمُ المتاجر، والمزايا."""
    view = await rider_offers.rider_view(session, rider)
    await session.commit()
    return RiderOffersOut.model_validate(view, from_attributes=True)
