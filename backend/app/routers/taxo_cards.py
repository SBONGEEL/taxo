"""استعمالُ بطاقة شحن TAXO — للراكب والكبتن (SPEC §٧٣-هـ المرحلة ٢).

**ثلاثةٌ بترتيبها**: سقفُ التخمين يُسأل قبل قراءة الرمز · الاستعمالُ في معاملةٍ واحدة · **والخطأُ يُعدّ بعد التراجع عنها** في معاملةٍ
تخصّه — فتنبيهُ البلوغ يُكتب ولو رُدّ الطلب.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from app.core.currency import currency_for_country, money_text
from app.core.deps import CurrentDriver, CurrentUser, DbSession, RedisDep, client_ip
from app.core.exceptions import InvalidInput
from app.models.enums import WalletOwnerType
from app.schemas.taxo_card import (
    CaptainCardCodeOut,
    CaptainCardOut,
    CaptainDenominationOut,
    CaptainPurchaseIn,
    CaptainPurchaseOut,
    CaptainQuoteIn,
    CaptainQuoteOut,
    CaptainSalesOut,
    TaxoCardRedeemedOut,
    TaxoCardRedeemIn,
)
from app.services import cancellation, captain_cards, card_exports, notifications, taxo_cards, wallet

router = APIRouter(prefix="/taxo-cards", tags=["taxo-cards"])


@router.post("/redeem", response_model=TaxoCardRedeemedOut)
async def redeem_card(
    payload: TaxoCardRedeemIn, user: CurrentUser, session: DbSession, redis: RedisDep, request: Request
) -> TaxoCardRedeemedOut:
    """**رمزٌ يشحن المحفظةَ مرّةً واحدة** — ويُقرأ في سجلّها «شحن ببطاقة TAXO»."""
    ip = client_ip(request)
    # **قيمٌ تُقرأ قبل المحاولة** — التراجعُ عنها يُنهي كلَّ صفٍّ في الجلسة، والعدُّ بعده يحتاج من حاول وأين
    user_id, country = user.id, user.country_code
    limits = await taxo_cards.limits_for(session, country)
    await taxo_cards.require_not_locked(redis, limits, user_id=user_id, ip=ip)
    try:
        result = await taxo_cards.redeem(session, user=user, code_raw=payload.code, declared=payload.wallet)
        await session.commit()
    except taxo_cards.CardCodeRejected:
        await session.rollback()
        await taxo_cards.record_wrong(session, redis, user_id=user_id, country=country, ip=ip, limits=limits)
        await session.commit()
        raise
    # شحنٌ اكتمل قد يكون سدّد رسمَ إلغاءٍ معلّقاً — **بعد الـcommit** كبقية البثّ
    await cancellation.announce_settled_for_debtor(session, redis, user=user)
    serial, amount, currency = result.card.serial, result.card.amount, result.card.currency
    # **إشعارٌ بعد الـcommit** (صندوقُ الوارد ثمّ Push) — المبلغُ رقمٌ خامٌ في `data`، والجملةُ يرسمها النظام
    await notifications.publish_taxo_card_topup(session, redis, user_id=user_id, amount=money_text(amount, currency), currency=currency.value)
    return TaxoCardRedeemedOut(serial=serial, amount=amount, currency=currency, balance_after=result.balance_after)


# ------------------------------------------------------------------ بيعُ الكباتن (أمرُ المالك ٢٠٢٦-١١-٢٣، الترحيلة `0189`)


@router.get("/captain", response_model=CaptainSalesOut)
async def captain_sales(driver: CurrentDriver, user: CurrentUser, session: DbSession) -> CaptainSalesOut:
    """**صفحةُ «بيع بطاقات TAXO»** — مفتوحٌ أم لا، والفئاتُ بكلفتها على الكبتن، وما بقي من سقف اليوم ورصيدُه. **مغلقاً لا فئات**."""
    country = user.country_code
    currency = currency_for_country(country)
    sales = await captain_cards.state(session, country)
    balance = await wallet.balance(session, user.id, WalletOwnerType.DRIVER)
    remaining = max(0, sales.daily_cap - await captain_cards.bought_today(session, driver.id))
    rows = []
    if sales.open and sales.discount_percent is not None:
        rows = [
            CaptainDenominationOut(
                id=row.id, amount=row.amount, currency=currency,
                unit_cost_amount=captain_cards.unit_cost(row.amount, sales.discount_percent, country),
            )
            for row in await captain_cards.denominations(session, country)
        ]
    return CaptainSalesOut(
        open=sales.open, currency=currency, discount_percent=sales.discount_percent if sales.open else None,
        daily_cap=sales.daily_cap, remaining_today=remaining, balance_amount=balance, denominations=rows,
    )


@router.post("/captain/quote", response_model=CaptainQuoteOut)
async def captain_quote(payload: CaptainQuoteIn, driver: CurrentDriver, user: CurrentUser, session: DbSession) -> CaptainQuoteOut:
    """**ما يُخصم من المحفظة قبل التأكيد** — محسوبٌ هنا لا في الواجهة (§14)."""
    country = user.country_code
    sales = await captain_cards.state(session, country)
    if not sales.open or sales.discount_percent is None:
        raise captain_cards.CaptainSalesClosed()
    row = next((d for d in await captain_cards.denominations(session, country) if d.id == payload.denomination_id), None)
    if row is None:
        raise InvalidInput("الفئةُ غيرُ متاحةٍ في هذا السوق", field="denomination_id")
    return CaptainQuoteOut(
        quantity=payload.quantity, face_amount=row.amount * payload.quantity, currency=currency_for_country(country),
        cost_amount=captain_cards.total_cost(row.amount, payload.quantity, sales.discount_percent, country),
    )


@router.post("/captain/purchase", response_model=CaptainPurchaseOut)
async def captain_purchase(
    payload: CaptainPurchaseIn, driver: CurrentDriver, user: CurrentUser, session: DbSession
) -> CaptainPurchaseOut:
    """**دفعةٌ من محفظة الكبتن** — قيدُ «شراء بطاقات TAXO» والبطاقاتُ في معاملةٍ واحدة، **والإعادةُ بالمفتاح نفسِه تجد دفعتَها**."""
    bought = await captain_cards.purchase(
        session, driver=driver, user=user, denomination_id=payload.denomination_id, quantity=payload.quantity,
        idempotency_key=payload.idempotency_key,
    )
    await session.commit()
    batch = bought.batch
    return CaptainPurchaseOut(
        batch_id=batch.id, quantity=batch.quantity, face_amount=batch.amount * batch.quantity, cost_amount=bought.cost,
        balance_amount=bought.balance_after, currency=batch.currency, replayed=bought.replayed,
    )


@router.get("/captain/cards", response_model=list[CaptainCardOut])
async def captain_cards_list(driver: CurrentDriver, session: DbSession) -> list[CaptainCardOut]:
    """**بطاقاتُ هذا الكبتن وحدَه** — بحالها، **بلا رمز**."""
    return [
        CaptainCardOut(
            id=card.id, serial=card.serial, amount=card.amount, currency=card.currency, state=state,
            expires_at=card.batch.expires_at, created_at=card.created_at,
        )
        for card, state in await captain_cards.my_cards(session, driver)
    ]


@router.get("/captain/cards/{card_id}/code", response_model=CaptainCardCodeOut)
async def captain_card_code(card_id: uuid.UUID, driver: CurrentDriver, session: DbSession) -> CaptainCardCodeOut:
    """**الرمزُ وQR لبائعه وحدَه** حين يبيع — بطاقةٌ تعمل لم تُستعمل."""
    card, code = await captain_cards.reveal(session, driver=driver, card_id=card_id)
    url = card_exports.REDEEM_URL.format(code=code.replace("-", "").replace(" ", ""))
    return CaptainCardCodeOut(
        id=card.id, serial=card.serial, code=code, amount=card.amount, currency=card.currency, redeem_url=url,
        qr_svg=card_exports.qr_svg_uri(url),
    )
