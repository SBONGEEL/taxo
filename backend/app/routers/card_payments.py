"""مسارات الدفع بالبطاقة (SPEC القسم 6.4/7/14 — المرحلة 6-ب).

أربعة مسارات وسبب كلٍّ منها:

- **`/payments/card/webhook`**: المزود يعلمنا. **بلا مصادقة عمداً** — لا توكن
  لدى Telr؛ التوقيعُ هو المصادقة (القسم 14). والحمولة تُستعمل لتحديد الطلب
  وحده، فالحالة والمبلغ يُقرآن من المزود بنداءٍ من الخلفية.
- **`/payments/card/orders/{cart_id}`**: الواجهة تعود من صفحة الدفع وتسأل. ليس
  احتياطاً للإشعار بل شريكه: أيُّهما وصل أولاً سوّى.
- **`/payments/cards`**: البطاقات المحفوظة — عرضٌ وحذفٌ وتعيين افتراضية. **لا
  رمزَ مزودٍ يخرج من هنا** (القسم 4).
- **`/payments/card/mock/...`**: «صفحة الدفع» الوهمية للتطوير والاختبار
  (القسم 15)، مغلقةٌ إلا حين يكون العقد نفسه على المزود الوهمي.

الراوتر يقرّر **من** يحق له الطلب فقط؛ كل ما عداه في `services/card_payments.py`.
"""

from __future__ import annotations

import json
import uuid
from urllib.parse import parse_qsl

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field

from app.core import rate_limit
from app.core.deps import ClientIP, CurrentUser, DbSession, RedisDep
from app.core.exceptions import FeatureNotAvailable, RateLimited
from app.schemas.payment import CardOrderOut, SavedCardOut
from app.services import card_payments as card_service
from app.services.card_gateway import get_gateway
from app.services.card_gateway.mock import OUTCOMES, MockCardGateway

router = APIRouter(tags=["payments"])

# سقف سخيّ لكل IP على مسار الإشعار: المزود يعيد الإرسال عند الفشل فلا يُخنق،
# لكن مساراً عاماً بلا مصادقة لا يُترك بلا سقف أصلاً (SPEC القسم 14)
WEBHOOK_RATE_LIMIT = 120
WEBHOOK_RATE_WINDOW_SECONDS = 60


class MockOutcomeRequest(BaseModel):
    """ما «يختاره الدافع» على الصفحة الوهمية."""

    outcome: str = Field(pattern="|".join(OUTCOMES))


# ------------------------------------------------------------------ الإشعار


async def _webhook_payload(request: Request) -> dict[str, str]:
    """حمولة الإشعار: `x-www-form-urlencoded` عادةً، وJSON إن أرسلها المزود كذلك.

    الترميز يُفكّ بـ `parse_qsl` لا بـ `request.form()`: الأخير يجرّ محلّل
    multipart كاملاً إلى **مسار عام بلا مصادقة**، والإشعار ليس رفعَ ملف. أقلُّ
    ما يكفي لقراءته هو أقلُّ ما يمكن مهاجمته.

    و`keep_blank_values=True` شرطٌ لا تحسين: حقولٌ فارغة مثل `tran_prevref`
    داخلةٌ في التوقيع، فإسقاطُها يجعل كل إشعارٍ صحيحٍ يُقرأ فاسداً.

    القراءة نصّيةٌ كلها: التوقيع يُحسب على النصوص كما وصلت، وأيُّ تحويل نوعٍ
    قبله (رقمٍ إلى رقم، مبلغٍ إلى Decimal) يغيّر ما نوقّع عليه فيكسر التحقق.
    """
    raw = await request.body()
    content_type = request.headers.get("content-type", "")

    if "json" in content_type:
        try:
            data = json.loads(raw or b"{}")
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
    else:
        data = dict(
            parse_qsl(raw.decode("utf-8", "replace"), keep_blank_values=True)
        )

    return {str(key): str(value) for key, value in data.items()}


@router.post("/payments/card/webhook", status_code=status.HTTP_200_OK)
async def card_webhook(
    request: Request, session: DbSession, redis: RedisDep, ip: ClientIP
) -> dict[str, str]:
    """إشعار المزود — يُتحقق من توقيعه ثم يُسأل المزود عن الحال.

    يعود 200 على الإشعار المُعاد كما على الأول: المزودون يعيدون الإرسال حتى
    يرَوا نجاحاً، وطلبٌ محسومٌ سلفاً ليس فشلاً.
    """
    limit = await rate_limit.hit(
        redis,
        f"card:webhook:{ip}",
        limit=WEBHOOK_RATE_LIMIT,
        window_seconds=WEBHOOK_RATE_WINDOW_SECONDS,
    )
    if not limit.allowed:
        raise RateLimited(retry_after=limit.retry_after)

    payload = await _webhook_payload(request)
    order = await card_service.handle_webhook(session, payload)
    await session.commit()
    return {"cart_id": order.cart_id, "status": order.status.value}


# ----------------------------------------------------------------- الاستعلام


@router.get("/payments/card/orders/{cart_id}", response_model=CardOrderOut)
async def get_card_order(
    cart_id: str, user: CurrentUser, session: DbSession
) -> CardOrderOut:
    """حال طلب الدفع بعد عودة المتصفح — يسأل المزود ثم يسوّي إن حُسم."""
    order = await card_service.order_for_user(session, cart_id, user)
    order = await card_service.reconcile(session, order)
    await session.commit()
    return CardOrderOut.model_validate(order)


# ----------------------------------------------------------- البطاقات المحفوظة


@router.get("/payments/cards", response_model=list[SavedCardOut])
async def list_saved_cards(
    user: CurrentUser, session: DbSession
) -> list[SavedCardOut]:
    cards = await card_service.list_cards(session, user)
    return [SavedCardOut.model_validate(card) for card in cards]


@router.post("/payments/cards/{card_id}/default", response_model=SavedCardOut)
async def set_default_card(
    card_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> SavedCardOut:
    card = await card_service.set_default_card(session, card_id, user)
    await session.commit()
    return SavedCardOut.model_validate(card)


@router.delete("/payments/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_card(
    card_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> None:
    await card_service.delete_card(session, card_id, user)
    await session.commit()


# ------------------------------------------------------- الصفحة الوهمية


@router.post("/payments/card/mock/{cart_id}", response_model=CardOrderOut)
async def simulate_mock_payment(
    cart_id: str,
    payload: MockOutcomeRequest,
    user: CurrentUser,
    session: DbSession,
) -> CardOrderOut:
    """يحاكي ضغطة الدافع على صفحة المزود الوهمي (SPEC القسم 15).

    مشروطٌ بأمرين معاً: أن يكون عقد الدولة نفسه على المزود الوهمي (وهو ممنوع
    في الإنتاج أصلاً)، وأن يكون الطالب صاحبَ الطلب. فلا يفتح هذا المسار باباً
    لا يفتحه العقدُ من صفحة العقود.
    """
    order = await card_service.get_order(session, cart_id)
    card_service.require_owner(order, user)

    gateway = await get_gateway(session, order.country_code)
    if not isinstance(gateway, MockCardGateway):
        raise FeatureNotAvailable("محاكاة الدفع متاحة على المزود الوهمي وحده")

    await gateway.set_outcome(cart_id, payload.outcome)
    order = await card_service.reconcile(session, order)
    await session.commit()
    return CardOrderOut.model_validate(order)
