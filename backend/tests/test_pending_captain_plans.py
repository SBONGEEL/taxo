"""«عرضُ الباقات» للكبتن قيد المراجعة — **عرضٌ بلا شراء** (§٦٢-ج/٣٣، C32).

**عقدُ الشاشة كلُّه في اختبارٍ واحد**: من سجّل ولم يُعتمد **يقرأ** `GET /subscriptions/plans` كما يقرؤه المعتمَد — **ولا
يشتري**: «يُتاح الشراءُ بعد اعتماد طلبك» نصُّ الشاشة، **والرفضُ في الخلفية لا في الشاشة وحدَها**
(`subscriptions.require_purchasable`) — فزرٌّ يُضاف يوماً بالخطأ لا يبيع اشتراكاً يحترق في الانتظار.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import DRIVER, SUBSCRIPTION_PLAN_NAME, auth, ensure_plan, register


async def test_a_pending_captain_reads_the_plans_but_cannot_buy_yet(
    client: AsyncClient, jordan_wallet: None, session_factory
) -> None:
    plan_id = await ensure_plan(session_factory)
    # **حسابٌ مسجَّلٌ للتوّ** — قيد المراجعة كما يصل كلُّ كبتنٍ جديد، لا معتمَدٌ أُعيد إلى الانتظار
    body = await register(client, DRIVER)
    headers = auth(body)

    me = await client.get("/drivers/me", headers=headers)
    assert me.status_code == 200, me.text
    assert me.json()["driver"]["status"] == "pending"

    plans = await client.get("/subscriptions/plans", headers=headers)
    assert plans.status_code == 200, plans.text
    assert [row["name"] for row in plans.json()] == [SUBSCRIPTION_PLAN_NAME]

    bought = await client.post(
        "/subscriptions",
        json={"plan_id": str(plan_id), "idempotency_key": "pending-buy-0001"},
        headers=headers,
    )
    assert bought.status_code == 403, bought.text
    # **وسببُه الاعتمادُ لا المحفظة** — `jordan_wallet` يشعلها، فـ٤٠٣ هنا هي `require_purchasable` بعينها
    assert bought.json()["code"] == "permission_denied", bought.text
