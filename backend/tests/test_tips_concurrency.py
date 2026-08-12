"""تزامنُ البقشيش (المرحلة 12-و) — وحارسان مختلفان لا حارسٌ واحد.

قاعدةُ المشروع: «مرحلةٌ تمسّ المال ليست منتهيةً بلا اختبار تزامن»، **واختبِرِ
الثابتَ الذي يملكه القفلُ نفسُه** لا ثابتاً يحرسه غيرُه.

وهنا ثابتان يملكهما حارسان مختلفان، فلكلٍّ اختبارُه:

1. **بقشيشٌ واحدٌ لكل رحلة** — يملكه `UNIQUE (ride_id)` في القاعدة. ضغطتان
   متزامنتان تنتجان صفاً واحداً وقيدين لا أربعة.
2. **رصيدٌ لا يُقرأ مرتين** — يملكه القفلُ الاستشاري على المحفظة. راكبٌ برصيدٍ
   يكفي بقشيشاً واحداً يعطي بقشيشين لرحلتين مختلفتين في اللحظة نفسها: بلا القفل
   يقرأ النداءان الرصيدَ نفسَه فيمرّان معاً و**ينتهي الرصيد سالباً** — وهو
   العطبُ الذي شحن في المرحلة 5 ولم يكتشفه إلا اختبارُ تزامن.

**والتحقق بالحذف كشف تفصيلاً يستحق الكتابة**: حذفُ أحد القفلين وحده **لا
يُفشل شيئاً** — لأن كلاً منهما يُسلسِل النداءين بنفسه (`wallet.record` يقفل
محفظةَ صاحبه قبل أن يجمع رصيده، والقفلُ المسبق في `tips.create` يقفل الاثنين
مرتَّبين). فما يملكه القفلُ المسبق ليس منعَ القراءة المزدوجة بل **ترتيبَ
القفل** أي منعَ الجمود — تماماً كما أن قفلَ صفِّ الكبتن زائدٌ على مسار شراء
الاشتراك بالمحفظة ووحيدٌ على المسار اليدوي (`CLAUDE.md`).

وبحذف **الاثنين** يخرج الجواب `[201, 201]`: بقشيشان بدينارٍ ونصف على رصيدٍ
مقداره ديناران — مالٌ خُلق من لا شيء. وهذا ما يجعل هذا الاختبار مالكاً لثابته.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.enums import WalletTransactionType
from app.models.tip import Tip
from app.models.wallet import WalletTransaction
from tests.helpers import (
    DRIVER,
    approved_driver,
    bring_online,
    completed_ride,
    enable_features,
    rider_session,
    topup_wallet,
)

DEADLOCK_TIMEOUT = 20
PRESETS = {
    "tip_preset_small": "0.500",
    "tip_preset_medium": "1.000",
    "tip_max": "5.000",
}


async def _prepare(
    client: AsyncClient, admin_headers: dict, session_factory, *, balance: str
) -> dict:
    await enable_features(session_factory, "wallet_enabled", "tips_enabled")
    settings = await client.patch(
        "/admin/settings/payments/JO", json=PRESETS, headers=admin_headers
    )
    assert settings.status_code == 200, settings.text

    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], balance)
    return {"rider": rider, "driver": driver}


async def test_two_taps_on_one_ride_leave_one_tip(
    client: AsyncClient, jordan_settings: None, admin_headers: dict, session_factory
) -> None:
    """الثابتُ الأول: صفٌّ واحدٌ وقيدان — لا صفّان وأربعة قيود."""
    ready = await _prepare(client, admin_headers, session_factory, balance="20.000")
    ride = await completed_ride(client, ready["rider"]["headers"], ready["driver"])

    responses = await asyncio.wait_for(
        asyncio.gather(
            *(
                client.post(
                    f"/rides/{ride['id']}/tip",
                    json={"amount": "1.000"},
                    headers=ready["rider"]["headers"],
                )
                for _ in range(3)
            )
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [201, 409, 409], statuses
    assert {r.json()["code"] for r in responses if r.status_code == 409} == {
        "tip_already_given"
    }

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Tip)) == 1
        entries = await session.scalar(
            select(func.count())
            .select_from(WalletTransaction)
            .where(
                WalletTransaction.type.in_(
                    [WalletTransactionType.TIP, WalletTransactionType.TIP_PAYMENT]
                )
            )
        )
        assert entries == 2


async def test_two_tips_on_a_thin_balance_never_go_negative(
    client: AsyncClient, jordan_settings: None, admin_headers: dict, session_factory
) -> None:
    """**الثابتُ الذي يملكه القفل**: رصيدٌ يكفي واحداً لا يدفع اثنين.

    رحلتان مختلفتان — فالقيدُ الفريد لا يمنع شيئاً هنا — ورصيدٌ مقداره ديناران
    وبقشيشان بدينارٍ ونصف. والقفلُ الاستشاري هو ما يجعل النداء الثاني يقرأ رصيداً
    نقص، فيُرفض بـ409 بدل أن يمرّ.

    **وحذفُ قفلٍ واحدٍ لا يُفشله** (الآخر يُسلسِل)، وحذفُ الاثنين يخرج
    `[201, 201]` — وهو نفسُ العطب الذي شحن في المرحلة 5 ولم يكتشفه إلا اختبارُ
    تزامن.
    """
    ready = await _prepare(client, admin_headers, session_factory, balance="2.000")
    rider, driver = ready["rider"], ready["driver"]

    first = await completed_ride(client, rider["headers"], driver)
    second = await completed_ride(client, rider["headers"], driver)

    responses = await asyncio.wait_for(
        asyncio.gather(
            client.post(
                f"/rides/{first['id']}/tip",
                json={"amount": "1.500"},
                headers=rider["headers"],
            ),
            client.post(
                f"/rides/{second['id']}/tip",
                json={"amount": "1.500"},
                headers=rider["headers"],
            ),
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [201, 409], statuses
    assert [r.json()["code"] for r in responses if r.status_code == 409] == [
        "insufficient_balance"
    ]

    async with session_factory() as session:
        # الرصيدُ من الدفتر لا من ردٍّ سابق — ولا قيدَ برصيدٍ سالب
        rows = (
            await session.scalars(
                select(WalletTransaction).order_by(WalletTransaction.created_at)
            )
        ).all()
        rider_rows = [
            row for row in rows if str(row.owner_id) == rider["user"]["id"]
        ]
        assert sum(row.amount for row in rider_rows) == Decimal("0.500")
        assert all(row.balance_after >= 0 for row in rows)
        # وبقشيشٌ واحدٌ فقط استقر
        assert await session.scalar(select(func.count()).select_from(Tip)) == 1
