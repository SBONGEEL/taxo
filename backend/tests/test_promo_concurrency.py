"""تزامنُ الكوبونات (المرحلة 12-ز) — وقفلُ صفِّ الرمز يملك **واحداً** لا اثنين.

`apply_to_ride` تقرأ ثم تكتب: تجمع المصروف، وتعدّ استعمالاتِ المستخدم، ثم تجمّد
القاعدةَ على الرحلة. وهي بعينها «اقرأ ثم اكتب» التي لا تكون ذرّيةً بنفسها —
فطلبان متزامنان يقرآن العدَّ نفسه ويمرّان معاً.

**والتحقق بالحذف فرّق بين اختبارَي هذا الملف، وهو فرقٌ يستحق الكتابة:**

1. **الميزانيةُ لا تُتجاوز بتطبيقاتٍ متزامنة** — ثلاثةُ ركّابٍ يطلبون معاً على
   رمزٍ ميزانيتُه تكفي واحداً. **وهذا وحده يفشل بحذف `for_update=True`**
   (`[201, 201, 404]` بدل `[201, 404, 404]`): مالٌ يُوعد به مرتين من ميزانيةٍ
   تكفي مرة.
2. **وحدُّ المستخدم لا يخترقه طلبان معاً — ويمرّ بلا القفل أيضاً**، لأن حارسَه
   شيءٌ آخر: الفهرسُ الجزئي `uq_rides_active_rider` يمنع رحلتين نشطتين لراكبٍ
   واحد، فلا يمكن أصلاً أن يتزامن تطبيقان من نفس الراكب. فالاختبارُ يبقى حرساً
   للسلوك (رحلةٌ واحدةٌ تحمل الرمز) **ولا يُنسب إلى القفل** — وقاعدةُ المشروع
   صريحة: اختبارٌ يمرّ بحذف القفل لا يُثبت شيئاً عنه، وكتابةُ ذلك أصدقُ من
   تركِه يُقرأ دليلاً.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.enums import CountryCode, PromoDiscountType
from app.models.promo import PromoCode
from app.models.ride import Ride
from tests.helpers import (
    DRIVER,
    PICKUP,
    DROPOFF,
    approved_driver,
    bring_online,
    enable_features,
    rider_session,
)

DEADLOCK_TIMEOUT = 20


async def _promo(session_factory, **overrides) -> PromoCode:
    values = dict(
        code="RACE",
        country_code=CountryCode.JO,
        discount_type=PromoDiscountType.FIXED,
        discount_value=Decimal("1.000"),
        max_discount=None,
        budget_total=Decimal("100.000"),
        per_user_limit=1,
    ) | overrides
    async with session_factory() as session:
        promo = PromoCode(**values)
        session.add(promo)
        await session.commit()
        return promo


def _request(client: AsyncClient, headers: dict, code: str = "RACE"):
    return client.post(
        "/rides",
        json={
            "pickup": PICKUP,
            "dropoff": DROPOFF,
            "vehicle_category": "economy",
            "promo_code": code,
        },
        headers=headers,
    )


async def test_two_requests_at_once_cannot_beat_the_per_user_limit(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """`per_user_limit = 1` يعني رحلةً واحدةً بالرمز — **وحارسُه ليس قفلَ الرمز**.

    القيدُ الجزئي `uq_rides_active_rider` يمنع رحلتين نشطتين لراكبٍ واحد، فطلبان
    متزامنان من نفس الراكب لا يمرّان معاً بحالٍ — بقفلٍ أو بغيره. جُرِّب بحذف
    `for_update=True` فمرّ هذا الاختبار كما هو، **فلا يُنسب إليه**؛ وهو يحرس
    السلوكَ الظاهر (رحلةٌ واحدةٌ تحمل الرمز، والخاسرُ يرتدّ 409) لا القفل.
    """
    await enable_features(session_factory, "promo_codes_enabled")
    promo = await _promo(session_factory)
    rider = await rider_session(client)

    responses = await asyncio.wait_for(
        asyncio.gather(
            _request(client, rider["headers"]),
            _request(client, rider["headers"]),
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    assert sorted(r.status_code for r in responses) == [201, 409], [
        (r.status_code, r.json().get("code")) for r in responses
    ]

    async with session_factory() as session:
        carrying = await session.scalar(
            select(func.count())
            .select_from(Ride)
            .where(Ride.promo_code_id == promo.id)
        )
        assert carrying == 1


async def test_three_requests_at_once_cannot_beat_the_budget(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**الثابتُ الثاني**: ميزانيةٌ تكفي خصماً واحداً لا تُطبَّق ثلاث مرات.

    ثلاثةُ ركّابٍ مختلفين — فحدُّ المستخدم لا يمنع شيئاً هنا — ورمزٌ ميزانيتُه
    دينارٌ وخصمُه دينار. والمصروفُ يُجمع من دفعات `promo` المؤكَّدة، وهي لم توجد
    بعد لحظةَ الطلب؛ **فالحارسُ هو أن التطبيقات تتسلسل** ويقرأ الثاني ما ثبّته
    الأول: رحلةً تحمل الرمزَ سلفاً.

    ولذلك يُفحص السقفُ على **الرحلات الحاملة** لا على المصروف وحده: بغيره تمرّ
    مئةُ رحلةٍ في ثانيةٍ واحدة قبل أن تُنشأ أولُ دفعة، فتتجاوز الحملةُ ميزانيتَها
    مئةَ ضعف — والسقفُ الذي شرطه المالك يصير رقماً في شاشة.
    """
    await enable_features(session_factory, "promo_codes_enabled")
    promo = await _promo(
        session_factory, budget_total=Decimal("1.000"), per_user_limit=5
    )

    riders = []
    for index in range(3):
        riders.append(
            await rider_session(
                client,
                {
                    "phone": f"079555000{index}",
                    "name": f"راكب {index}",
                    "password": "SuperSecret123",
                    "country_code": "JO",
                    "role": "rider",
                },
            )
        )

    responses = await asyncio.wait_for(
        asyncio.gather(*(_request(client, rider["headers"]) for rider in riders)),
        timeout=DEADLOCK_TIMEOUT,
    )

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [201, 404, 404], [
        (r.status_code, r.json().get("code")) for r in responses
    ]
    assert {
        r.json()["code"] for r in responses if r.status_code == 404
    } == {"promo_exhausted"}

    async with session_factory() as session:
        carrying = await session.scalar(
            select(func.count())
            .select_from(Ride)
            .where(Ride.promo_code_id == promo.id)
        )
        assert carrying == 1
