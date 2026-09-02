"""الملفُّ الشخصيُّ الكامل — **ما تقرؤه أقسامُه، ومن أين** (البند ١، SPEC §37).

**والملفُّ لا يملك باباً واحداً يجمع كلَّ شيء**، وذلك قرارٌ لا سهو: §5-ج يقول
إن شاشةَ لوحةٍ **ليست مساراً حرجاً** ولها أن تسأل عدّةَ أبوابٍ إن كان كلٌّ منها
**مصدرَ مفهومه الواحد** — والقاعدةُ هناك «الصفحةُ تقرأ ولا تحسب من جديد».
**فبابٌ جامعٌ كان سيصير مصدراً ثانياً** لأرصدةٍ وسلفٍ ورحلاتٍ لها مصادرُها.

**فما يقيسه هذا الملفّ**: أن كلَّ بابٍ يقرأ منه الملفُّ يقبل **مرشِّحاً
بمعرِّف صاحبه** ويردّ صفوفَه وحدَها — لا أن يقرأ الملفُّ بالاسم، **فاسمان
متشابهان يخلطان ملفَّي شخصين**.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from httpx import AsyncClient
from sqlalchemy import select

from app.models.advance import AdvanceSetting
from app.models.enums import (
    CountryCode,
    Currency,
    FeatureKey,
    PaymentMethod,
    SubscriptionDurationType,
    SubscriptionStatus,
)
from app.models.feature_flag import FeatureFlag
from app.models.subscription import DriverSubscription, SubscriptionPlan
from tests.helpers import (
    DRIVER,
    RIDER,
    approved_driver,
    auth,
    register,
)

pytestmark = pytest.mark.usefixtures("jordan_settings", "jordan_wallet")

async def _enable_advances(session_factory) -> None:
    """يُشعل مفتاحَ السلف، ويضع الخطّةَ اليوميةَ التي يُشتقّ منها السقف،
    **ويُنزل شرطَي الرحلات والتقييم إلى صفر**.

    **وهذا الملفُّ يقيس القائمةَ لا الأهلية** — شروطُها بيتُها
    `test_advances.py` بقراراتها الثمانية. **ولا يُستورد `_enable` منه**:
    ربطُ سقوطِ ملفٍّ بملفٍّ آخرَ يجعل عطباً واحداً يُقرأ عطبين.
    """
    async with session_factory() as session:
        session.add(
            FeatureFlag(
                country_code=CountryCode.JO,
                feature_key=FeatureKey.DRIVER_ADVANCES_ENABLED.value,
                enabled=True,
            )
        )
        plan = await session.scalar(
            select(SubscriptionPlan).where(
                SubscriptionPlan.country_code == CountryCode.JO,
                SubscriptionPlan.duration_type == SubscriptionDurationType.DAILY,
            )
        )
        if plan is None:
            session.add(
                SubscriptionPlan(
                    name="يومي",
                    duration_type=SubscriptionDurationType.DAILY,
                    price=Decimal("2.000"),
                    currency=Currency.JOD,
                    country_code=CountryCode.JO,
                )
            )
        row = await session.scalar(
            select(AdvanceSetting).where(AdvanceSetting.country_code == CountryCode.JO)
        )
        if row is None:
            row = AdvanceSetting(country_code=CountryCode.JO)
            session.add(row)
        row.min_completed_rides = 0
        row.min_rating = Decimal("0")
        await session.commit()


async def _past_subscription(session_factory, driver_id) -> None:
    """اشتراكٌ **مضى** — شرطُ السلفة الذي لا يُعطَّل (القرار ٣ في البند ١٥)."""
    async with session_factory() as session:
        plan = await session.scalar(
            select(SubscriptionPlan).where(
                SubscriptionPlan.country_code == CountryCode.JO,
                SubscriptionPlan.duration_type == SubscriptionDurationType.MONTHLY,
            )
        )
        if plan is None:
            plan = SubscriptionPlan(
                name="شهري",
                duration_type=SubscriptionDurationType.MONTHLY,
                price=Decimal("20.000"),
                currency=Currency.JOD,
                country_code=CountryCode.JO,
            )
            session.add(plan)
            await session.flush()
        started = datetime.now(UTC) - timedelta(days=45)
        session.add(
            DriverSubscription(
                driver_id=driver_id,
                plan_id=plan.id,
                starts_at=started,
                expires_at=started + timedelta(days=30),
                amount_paid=plan.price,
                payment_method=PaymentMethod.CASH,
                status=SubscriptionStatus.EXPIRED,
            )
        )
        await session.commit()


OTHER_DRIVER = {
    **DRIVER,
    "phone": "+962790000933",
    "name": "كبتنٌ آخرُ لا تخصّه هذه الصفوف",
}


# ═════════════════════════════ المركبة — بابٌ جديد للملفّ


async def test_the_profile_reads_the_vehicles_of_that_driver_alone(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**قسمُ المركبة يقرأ من `GET /admin/drivers/{id}/vehicles`**.

    ولم يكن في اللوحة قبل اليوم أيُّ بابٍ يقرأ مركبةَ كبتن: `AdminDriverRow`
    لا يحملها، **فكان المشرفُ يقرّر على وثيقةِ مركبةٍ ولا يرى لوحتَها**.
    """
    driver = await approved_driver(client, session_factory, DRIVER)
    other = await approved_driver(
        client, session_factory, OTHER_DRIVER, plate_number="AMM-9191"
    )

    mine = await client.get(
        f"/admin/drivers/{driver['driver_id']}/vehicles", headers=admin_headers
    )
    assert mine.status_code == 200, mine.text
    plates = [row["plate_number"] for row in mine.json()]
    assert plates == ["AMM-4242"]

    his = await client.get(
        f"/admin/drivers/{other['driver_id']}/vehicles", headers=admin_headers
    )
    assert his.status_code == 200
    assert [row["plate_number"] for row in his.json()] == ["AMM-9191"]


async def test_the_vehicles_door_refuses_an_unknown_driver(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**ومعرّفٌ لا كبتنَ له ٤٠٤ لا قائمةٌ فارغة**: فراغٌ يُقرأ «بلا مركبة»."""
    missing = await client.get(
        "/admin/drivers/00000000-0000-0000-0000-000000000000/vehicles",
        headers=admin_headers,
    )
    assert missing.status_code == 404, missing.text


# ═════════════════════════════ السلف — مرشِّحٌ بالمعرِّف، ومعها صاحبُها


async def test_advances_carry_the_name_and_filter_by_driver(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_wallet
) -> None:
    """**الصفُّ يحمل الاسمَ والرقمَ لا `driver_id` وحدَه**، ويُرشَّح بالمعرِّف.

    **والاسمُ ليس زينة**: كانت اللوحة تعرض ثماني خاناتٍ من UUID في عمودٍ
    عنوانُه «الكبتن» — والشكلُ الثامن بعينه، إذ الدَّينُ ينشر الاسمَ والسلفةُ
    لا تنشره وهما صفّان عن الشخص نفسِه في الشاشة نفسِها.
    """
    await _enable_advances(session_factory)
    driver = await approved_driver(client, session_factory, DRIVER)
    other = await approved_driver(
        client, session_factory, OTHER_DRIVER, plate_number="AMM-9191"
    )

    for target in (driver, other):
        await _past_subscription(session_factory, target["driver_id"])
        created = await client.post(
            "/admin/drivers/advances",
            json={"driver_id": str(target["driver_id"]), "amount": "10.000"},
            headers=admin_headers,
        )
        assert created.status_code == 201, created.text

    both = await client.get("/admin/drivers/advances", headers=admin_headers)
    assert both.status_code == 200, both.text
    assert len(both.json()) == 2
    assert {row["driver_name"] for row in both.json()} == {
        DRIVER["name"],
        OTHER_DRIVER["name"],
    }
    assert all(row["driver_phone"] for row in both.json())

    mine = await client.get(
        "/admin/drivers/advances",
        params={"driver_id": str(driver["driver_id"])},
        headers=admin_headers,
    )
    assert mine.status_code == 200
    assert [row["driver_name"] for row in mine.json()] == [DRIVER["name"]]


# ═════════════════════════════ رسومُ الإلغاء — الطرفان بمعرِّف مستخدمٍ واحد


async def test_cancellation_charges_filter_by_the_person_not_by_the_name(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**`user_id` يمسك الطرفين**: الراكبَ مباشرةً والكبتنَ عبر `drivers.user_id`.

    **ولا يُقارَن بـ`rides.driver_id`**: ذاك عمودُ `drivers.id`، ومقارنتُه
    بمعرِّف مستخدمٍ **لا تطابق شيئاً أبداً** — وهو العطبُ المقيس في هذا
    الموجّه نفسِه (2026-09-02).

    **وما يُقاس هنا أن المرشِّحَ يُقبل ولا يوسّع**: بلا رسمٍ قائمٍ الجوابُ
    فراغٌ في الحالين — **والقيمةُ في أنه لا يرمي ولا يعيد جدولاً كاملاً**،
    وحالُ «وُجد» يقيسها الشكلُ نفسُه في `test_admin_search.py` على الدفعات.
    """
    body = await register(client, RIDER)
    rider_id = body["user"]["id"]

    filtered = await client.get(
        "/admin/cancellation-charges",
        params={"country_code": "JO", "user_id": rider_id},
        headers=admin_headers,
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json() == []

    plain = await client.get(
        "/admin/cancellation-charges",
        params={"country_code": "JO"},
        headers=admin_headers,
    )
    assert plain.status_code == 200
    assert plain.json() == []
    # **الرأسُ يُثبت أن الجلسةَ صالحة** — وإلا لكان الفراغان فراغَ منع
    assert auth(body)["Authorization"].startswith("Bearer ")


# ═════════════════════════════ المستحقّات — المرشِّحُ يُقبل ولا يوسّع


async def test_debts_accept_a_driver_filter(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**`driver_id` على المستحقّات** — يقرؤه قسمُ الدَّين في الملفّ."""
    driver = await approved_driver(client, session_factory, DRIVER)
    filtered = await client.get(
        "/admin/drivers/debts",
        params={"driver_id": str(driver["driver_id"])},
        headers=admin_headers,
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json() == []
