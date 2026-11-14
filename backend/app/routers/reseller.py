"""بابُ بائع البطاقات (SPEC §١٠٠-ب/٥) — صفحةُ البيع في اللوحة، على الهاتف أو الحاسوب.

**ثلاثةُ أبوابٍ لا غير**: ما يراه البائع، والبيع، ومبيعاتُه. **والمحلُّ من ربط الحساب لا من الطلب**، فلا يبيع أحدٌ باسم غيره.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.core.currency import currency_for_country
from app.core.deps import CardSeller, DbSession
from app.schemas.taxo_card import (
    ResellerDenominationOut,
    ResellerMeOut,
    ResellerSaleOut,
    ResellerSaleRowOut,
    ResellerSellIn,
)
from app.services import audit, card_sellers, taxo_cards
from app.models.enums import AuditAction

router = APIRouter(prefix="/reseller", tags=["reseller"])


@router.get("/me", response_model=ResellerMeOut)
async def me(seller: CardSeller, session: DbSession) -> ResellerMeOut:
    staff = await card_sellers.binding(session, seller)
    country = staff.shop.country_code
    settings = await card_sellers.pos_settings(session, country)
    currency = currency_for_country(country)
    return ResellerMeOut(
        name=seller.name, shop_name=staff.shop.name, country_code=country, currency=currency, enabled=settings.enabled,
        sold_today=await card_sellers.sold_today(session, seller), daily_cap=settings.daily_cap,
        validity_days=settings.validity_days,
        denominations=[
            ResellerDenominationOut(id=d.id, amount=d.amount, currency=currency)
            for d in await taxo_cards.denominations(session, country)
            if d.is_active
        ],
    )


@router.post("/sell", response_model=ResellerSaleOut, status_code=status.HTTP_201_CREATED)
async def sell(payload: ResellerSellIn, seller: CardSeller, session: DbSession) -> ResellerSaleOut:
    """**بطاقةٌ تُولَّد لحظةَ البيع** — والرمزُ في هذا الردِّ وحدَه. **ولا رمزَ في التدقيق**: الرقمُ التسلسليُّ وحدَه."""
    sale = await card_sellers.sell(session, seller=seller, denomination_id=payload.denomination_id)
    await audit.record(
        session, actor=seller, action=AuditAction.CREATE, entity_type="card_batch", entity_id=sale.batch.id,
        details={"action": "pos_sale", "serial": sale.serial, "shop_id": str(sale.batch.shop_id)},
    )
    await session.commit()
    await session.refresh(sale.batch)
    return ResellerSaleOut(
        serial=sale.serial, code=sale.code, amount=sale.batch.amount, currency=sale.batch.currency,
        shop_name=sale.batch.shop.name if sale.batch.shop else "", sold_at=sale.batch.created_at,
        expires_at=sale.batch.expires_at,
    )


@router.get("/sales", response_model=list[ResellerSaleRowOut])
async def sales(seller: CardSeller, session: DbSession) -> list[ResellerSaleRowOut]:
    await card_sellers.binding(session, seller)
    return [
        ResellerSaleRowOut(
            serial=card.serial, amount=card.amount, currency=card.currency, state=state, sold_at=card.batch.created_at,
            redeemed_at=card.redeemed_at,
        )
        for card, state in await card_sellers.my_sales(session, seller)
    ]
