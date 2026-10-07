"""الاسترداد الأسبوعي للراكب (SPEC §٦٣-ج/٨) — **ما تعرضه الشاشةُ بجانب النار**، ودورةُ التذكير."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.currency import currency_for_country
from app.core.deps import DbSession, RiderUser
from app.models.enums import Currency
from app.services import cashback

router = APIRouter(prefix="/me/cashback", tags=["cashback"])


class CashbackOut(BaseModel):
    """**`enabled: false` حيث الخدمةُ مطفأةٌ أو مبلغُها صفر** — فلا نارَ تُرسم بلا وعد."""

    enabled: bool
    days_required: int | None = None
    days_done: int | None = None
    days_left: int | None = None
    #: **المبلغُ المنتظَر** — محسوبٌ في الخلفية مجمَّداً على السلسلة
    amount: Decimal | None = None
    currency: Currency | None = None
    rode_today: bool = False
    friday: bool = False


@router.get("", response_model=CashbackOut)
async def my_cashback(rider: RiderUser, session: DbSession) -> CashbackOut:
    view = await cashback.view(session, rider)
    if not view.get("enabled"):
        return CashbackOut(enabled=False)
    return CashbackOut(**view, currency=currency_for_country(rider.country_code))
