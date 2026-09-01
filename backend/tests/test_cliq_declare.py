"""«حوّلتُ» — **فعلٌ يُختم، لا يُشتقّ من فتح شاشة** (قرارُ المالك 2026-09-01).

## خمسٌ تُقاس هنا، ونقضُ كلٍّ منها لا يصيح

* **الختمُ مرّةً**: الضغطةُ الثانيةُ **لا تُنشئ صفّاً ولا تصيح** — من ضغط
  ثانيةً لم يخطئ، والشبكةُ بطيئةٌ أو الشاشةُ لم تتحدّث.
* **والملكيةُ تُفحص**: مرجعٌ يُخمَّن لا يفتح مطالبةَ غيره — وهو IDOR بعينه.
* **وقائمةُ المشرف تفرّق من فتح ونسي عمّن حوّل**: **والأولُ لا ينتظر شيئاً**،
  والثاني ينتظر تأكيداً لمالٍ خرج من حسابه.
* **ومن دفع يُعرف بالاسم والرقم** — وكانت القائمةُ تعرض مبلغاً ومرجعاً
  ووقتاً **ولا شيءَ يقول من**.
* **والرفضُ بسببٍ يُعرض على صاحبه** — و«مرفوض» وحدَها تُنتج مكالمةَ دعم.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import ProviderOrderStatus
from app.models.provider_order import ProviderOrder
from tests.helpers import (
    DRIVER,
    approved_driver,
    ensure_plan,
    rider_session,
)


async def _claim(client: AsyncClient, session_factory) -> tuple[dict, dict]:
    """كبتنٌ معتمدٌ فتح مطالبةَ اشتراكٍ يدويّةً بكليك."""
    # **و`payment_settings.cliq_alias` مبذورٌ في `conftest`** — «لا قناةَ بلا
    # حسابٍ يستقبل»، والسوقُ بلا alias تُخفى عنه القناةُ كلُّها
    await ensure_plan(session_factory)
    driver = await approved_driver(client, session_factory, DRIVER)
    headers = driver["headers"]

    plans = (await client.get("/subscriptions/plans", headers=headers)).json()
    opened = await client.post(
        "/subscriptions/cliq",
        json={"plan_id": plans[0]["id"]},
        headers=headers,
    )
    assert opened.status_code in (200, 201), opened.text
    return opened.json(), headers


# ═══════════════════════════════ ١) الختمُ مرّةً


async def test_declaring_stamps_once_and_a_second_press_is_quiet(
    client: AsyncClient, session_factory, jordan_wallet: None
) -> None:
    """**ضغطةٌ ثانيةٌ لا تُنشئ طلباً ثانياً ولا تصيح** — وتُعيد الوقتَ الأوّل."""
    claim, headers = await _claim(client, session_factory)

    first = await client.post(
        f"/payments/cliq/{claim['cart_id']}/declare", headers=headers
    )
    assert first.status_code == 200, first.text
    stamp = first.json()["declared_paid_at"]
    assert stamp is not None

    second = await client.post(
        f"/payments/cliq/{claim['cart_id']}/declare", headers=headers
    )
    assert second.status_code == 200, second.text
    # **الوقتُ الأوّلُ لا وقتٌ جديد** — وإلا رتّب المشرفُ قائمتَه بوقتٍ متحرّك
    assert second.json()["declared_paid_at"] == stamp

    # **ولا صفَّ ثانياً** — وصفّان لتحويلٍ واحدٍ يُقرآن دفعتين
    async with session_factory() as session:
        rows = list(
            await session.scalars(
                select(ProviderOrder).where(
                    ProviderOrder.cart_id == claim["cart_id"]
                )
            )
        )
    assert len(rows) == 1


async def test_a_stranger_may_not_declare_someone_elses_claim(
    client: AsyncClient, session_factory, rider_payload: dict, jordan_wallet: None
) -> None:
    """**مرجعٌ يُخمَّن لا يفتح مطالبةَ غيره** — و٤٠٤ لا ٤٠٣."""
    claim, _ = await _claim(client, session_factory)
    stranger = await rider_session(client, rider_payload)

    refused = await client.post(
        f"/payments/cliq/{claim['cart_id']}/declare",
        headers=stranger["headers"],
    )
    assert refused.status_code == 404


async def test_an_unknown_reference_is_not_found(
    client: AsyncClient, session_factory, rider_payload: dict, jordan_wallet: None
) -> None:
    rider = await rider_session(client, rider_payload)
    refused = await client.post(
        "/payments/cliq/mdeadbeefdeadbeefde/declare", headers=rider["headers"]
    )
    assert refused.status_code == 404


# ═══════════════════ ٢) قائمةُ المشرف — من حوّل لا من فتح


async def test_the_admin_list_separates_who_declared_from_who_only_opened(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_wallet: None
) -> None:
    """**من فتح ونسي لا ينتظر شيئاً** — وخلطُهما يُطيل القائمةَ بمن لا ينتظر."""
    claim, headers = await _claim(client, session_factory)

    before = await client.get("/admin/cliq-claims/declared", headers=admin_headers)
    assert before.status_code == 200
    assert before.json() == []

    await client.post(
        f"/payments/cliq/{claim['cart_id']}/declare", headers=headers
    )

    after = await client.get("/admin/cliq-claims/declared", headers=admin_headers)
    rows = after.json()
    assert len(rows) == 1
    assert rows[0]["cart_id"] == claim["cart_id"]
    assert rows[0]["declared_paid_at"] is not None


async def test_the_claim_says_who_paid(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_wallet: None
) -> None:
    """**بالاسم والرقم** — وكانت تعرض مبلغاً ومرجعاً ولا شيءَ يقول من."""
    claim, headers = await _claim(client, session_factory)
    await client.post(
        f"/payments/cliq/{claim['cart_id']}/declare", headers=headers
    )

    rows = (
        await client.get("/admin/cliq-claims/declared", headers=admin_headers)
    ).json()
    assert rows[0]["payer_name"]
    assert rows[0]["payer_phone"]

    # **والبابُ القديمُ يقولها أيضاً** — بانٍ واحدٌ لا اثنان
    old = (await client.get("/admin/cliq-claims", headers=admin_headers)).json()
    assert old[0]["payer_name"] == rows[0]["payer_name"]


# ═══════════════════════════════ ٣) الرفضُ بسببه


async def test_rejecting_without_a_reason_is_refused(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_wallet: None
) -> None:
    claim, headers = await _claim(client, session_factory)
    await client.post(
        f"/payments/cliq/{claim['cart_id']}/declare", headers=headers
    )
    rows = (
        await client.get("/admin/cliq-claims/declared", headers=admin_headers)
    ).json()

    refused = await client.post(
        f"/admin/cliq-claims/{rows[0]['id']}/reject",
        json={"reason": "لا"},
        headers=admin_headers,
    )
    assert refused.status_code == 422


async def test_a_rejection_reason_reaches_its_owner(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_wallet: None
) -> None:
    """**ولا رفضَ صامت** — من حوّل مالاً ورُفض يستحق أن يعرف لماذا."""
    claim, headers = await _claim(client, session_factory)
    await client.post(
        f"/payments/cliq/{claim['cart_id']}/declare", headers=headers
    )
    rows = (
        await client.get("/admin/cliq-claims/declared", headers=admin_headers)
    ).json()

    reason = "لم تصل الحوالة إلى الحساب — راجع بنكك"
    done = await client.post(
        f"/admin/cliq-claims/{rows[0]['id']}/reject",
        json={"reason": reason},
        headers=admin_headers,
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == ProviderOrderStatus.FAILED.value

    # **ويقرؤه صاحبُه في شاشته** — من قائمته هو لا من قائمة المشرف
    mine = (await client.get("/subscriptions/cliq", headers=headers)).json()
    assert mine[0]["failure_reason"] == reason


async def test_support_cannot_reject(
    client: AsyncClient,
    session_factory,
    admin_headers: dict,
    support_headers: dict,
    jordan_wallet: None,
) -> None:
    claim, headers = await _claim(client, session_factory)
    await client.post(
        f"/payments/cliq/{claim['cart_id']}/declare", headers=headers
    )
    rows = (
        await client.get("/admin/cliq-claims/declared", headers=admin_headers)
    ).json()
    refused = await client.post(
        f"/admin/cliq-claims/{rows[0]['id']}/reject",
        json={"reason": "سببٌ كافٍ للرفض"},
        headers=support_headers,
    )
    assert refused.status_code == 403


# ═══════════════════════ ٤) الإشعارُ لحظةَ الضغط


async def test_the_admin_gets_a_notice_the_moment_it_is_pressed(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_wallet: None
) -> None:
    """**وصفُّ صندوق الوارد يُكتب ولو لا عقدَ FCM ولا جهازَ مسجَّل.**

    **فالإشعارُ قائمٌ اليوم** — والدفعُ إلى الهاتف يصل يومَ يسجّل غلافُ
    المشرف جهازَه، **ولا يُنتظر الغلافُ ليُبنى الإرسال**.
    """
    from app.models.notification import UserNotification
    from app.models.user import User
    from app.models.enums import UserRole

    claim, headers = await _claim(client, session_factory)
    await client.post(
        f"/payments/cliq/{claim['cart_id']}/declare", headers=headers
    )

    async with session_factory() as session:
        admin = await session.scalar(
            select(User).where(User.role == UserRole.ADMIN).limit(1)
        )
        rows = list(
            await session.scalars(
                select(UserNotification).where(
                    UserNotification.user_id == admin.id,
                    UserNotification.kind == "cliq_claim_declared",
                )
            )
        )
    assert len(rows) == 1
    assert claim["cart_id"] in rows[0].body
