"""**صفحةُ بطاقة الهدية** (SPEC §١٠٠-أ/٣): الفتحُ والكشطُ بلا حساب، من `https://taxo.tajora.ly/gift#<الرابط>`.

**الرابطُ في جسم الطلب لا في المسار**، فلا يقع في سجلِّ وصولٍ ولا في حافّة. **والبابان مسقوفان لكلِّ عنوان**، فلا تُجرَّب روابطُ عشوائيّة.
**والرمزُ يخرج من الكشط وحدَه، مرّةً واحدة**.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core import rate_limit
from app.core.deps import DbSession, RedisDep, client_ip
from app.core.exceptions import RateLimited
from app.schemas.taxo_card import GiftPublicOut, GiftScratchedOut, GiftTokenIn
from app.services import card_gifts

router = APIRouter(prefix="/public/gift", tags=["public"])

#: **سقفُ الفتح والكشط لكلِّ عنوانٍ في عشر دقائق**: يكفي من يفتح هديّته مرّاتٍ، ويوقف من يجرّب روابطَ عشوائيّة
OPEN_LIMIT = 60
SCRATCH_LIMIT = 10
WINDOW_SECONDS = 600


async def _limit(redis, request: Request, what: str, limit: int) -> None:
    result = await rate_limit.hit(redis, f"gift:{what}:{client_ip(request)}", limit=limit, window_seconds=WINDOW_SECONDS)
    if not result.allowed:
        raise RateLimited(retry_after=result.retry_after)


@router.post("/open", response_model=GiftPublicOut)
async def open_gift(payload: GiftTokenIn, session: DbSession, redis: RedisDep, request: Request) -> GiftPublicOut:
    """**ما يُرسم قبل الكشط**: القيمةُ والتصميمُ والاسمُ والرسالةُ والحال، **بلا رمز**."""
    await _limit(redis, request, "open", OPEN_LIMIT)
    link, current = await card_gifts.open_link(session, payload.token)
    await session.commit()
    card = link.card
    return GiftPublicOut(
        amount=card.amount, currency=card.currency, country_code=card.country_code, design=link.design,
        recipient_name=link.recipient_name, message=link.message, state=current, expires_at=card.batch.expires_at,
    )


@router.post("/scratch", response_model=GiftScratchedOut)
async def scratch_gift(payload: GiftTokenIn, session: DbSession, redis: RedisDep, request: Request) -> GiftScratchedOut:
    """**الكشطُ مرّةً واحدة**: يعود الرمزُ هنا ويُمحى معمّاه من القاعدة في المعاملة نفسِها."""
    await _limit(redis, request, "scratch", SCRATCH_LIMIT)
    link, code = await card_gifts.scratch(session, payload.token)
    await session.commit()
    return GiftScratchedOut(code=code, amount=link.card.amount, currency=link.card.currency)
