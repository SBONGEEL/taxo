"""استعمالُ بطاقة شحن TAXO — للراكب والكبتن (SPEC §٧٣-هـ المرحلة ٢).

**ثلاثةٌ بترتيبها**: سقفُ التخمين يُسأل قبل قراءة الرمز · الاستعمالُ في معاملةٍ واحدة · **والخطأُ يُعدّ بعد التراجع عنها** في معاملةٍ
تخصّه — فتنبيهُ البلوغ يُكتب ولو رُدّ الطلب.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.deps import CurrentUser, DbSession, RedisDep, client_ip
from app.schemas.taxo_card import TaxoCardRedeemedOut, TaxoCardRedeemIn
from app.services import cancellation, taxo_cards

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
    return TaxoCardRedeemedOut(serial=result.card.serial, amount=result.card.amount, currency=result.card.currency)
