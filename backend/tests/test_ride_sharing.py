"""مشاركةُ الرحلة: المفتاحُ والخصمُ والسلامة (المرحلة 12-ي، SPEC §5.12).

وحارسُ الكبتن تحت التزامن في ملفٍ مستقل (`test_ride_sharing_index.py`) لأنه
كُتب قبل هذا كلِّه بأمر قرار المالك الثاني.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import CountryCode, FeatureKey, PaymentMethod, PaymentStatus
from app.models.payment import Payment
from app.models.ride import Ride
from app.models.sharing import RideSharingSetting
from tests.helpers import (
    approved_driver,
    bring_online,
    enable_features,
    rider_session,
    wait_for_offer,
)

DISCOUNT = Decimal("25.00")


async def _set_discount(session_factory, percent: Decimal = DISCOUNT) -> None:
    async with session_factory() as session:
        row = await session.scalar(
            select(RideSharingSetting).where(
                RideSharingSetting.country_code == CountryCode.JO
            )
        )
        if row is None:
            row = RideSharingSetting(country_code=CountryCode.JO)
            session.add(row)
        row.discount_percent = percent
        await session.commit()


@pytest.fixture
async def sharing_on(session_factory) -> None:
    await enable_features(session_factory, FeatureKey.RIDE_SHARING_ENABLED)
    await _set_discount(session_factory)


async def _drive_to_completion(
    client: AsyncClient, driver: dict, ride_id: str
) -> None:
    """قبولٌ ثم وصولٌ ثم بدءٌ ثم إنهاء — بنفس خطوات `helpers.completed_ride`."""
    await wait_for_offer(ride_id, driver["driver_id"])
    for step in ("accept", "arrive", "start", "complete"):
        response = await client.post(
            f"/rides/{ride_id}/{step}", headers=driver["headers"]
        )
        assert response.status_code == 200, response.text


async def _request(client: AsyncClient, headers: dict, **extra) -> dict:
    response = await client.post(
        "/rides",
        json={
            "pickup": {"lat": 31.95, "lng": 35.91},
            "dropoff": {"lat": 31.98, "lng": 35.86},
            "vehicle_category": "economy",
            **extra,
        },
        headers=headers,
    )
    return {"status": response.status_code, "body": response.json(), "raw": response}


async def test_sharing_is_refused_where_the_flag_is_off(
    client: AsyncClient, session_factory, jordan_settings
):
    """**المفتاحُ يحكم ما يُقبل كما يحكم ما يُرسم**: طلبٌ مصنوعٌ بيدٍ يرتدّ."""
    rider = await rider_session(client)
    result = await _request(client, rider["headers"], share=True)
    assert result["status"] == 422
    assert result["body"]["code"] == "ride_sharing_unavailable"


async def test_a_zero_discount_hides_the_feature_even_with_the_flag_on(
    client: AsyncClient, session_factory, jordan_settings
):
    """**شرطان لا واحد**: نسبةٌ صفريةٌ تُقرأ «لم تُقرَّر» فتبقى الميزةُ مغلقة.

    ومشاركةٌ بخصمٍ صفريٍّ تَعِد بتوفيرٍ ثم تعطي رحلةً بسعرها كاملاً ومعها
    راكبٌ لم يُختَر — أسوأُ من غياب الميزة لا نصفُها.
    """
    await enable_features(session_factory, FeatureKey.RIDE_SHARING_ENABLED)
    await _set_discount(session_factory, Decimal("0.00"))
    rider = await rider_session(client)

    result = await _request(client, rider["headers"], share=True)
    assert result["status"] == 422
    assert result["body"]["code"] == "ride_sharing_unavailable"


async def test_the_percent_is_frozen_on_the_ride(
    client: AsyncClient, session_factory, jordan_settings, sharing_on
):
    """النسبةُ تُجمَّد كالعمولة: تعديلُها لاحقاً لا يمسّ رحلةً قائمة."""
    rider = await rider_session(client)
    result = await _request(client, rider["headers"], share=True)
    assert result["status"] == 201, result["body"]
    assert Decimal(result["body"]["share_discount_percent"]) == DISCOUNT

    await _set_discount(session_factory, Decimal("50.00"))

    async with session_factory() as session:
        ride = await session.get(Ride, result["body"]["id"])
        assert ride.share_discount_percent_at_ride == DISCOUNT


async def test_a_plain_ride_carries_no_share_percent(
    client: AsyncClient, session_factory, jordan_settings, sharing_on
):
    """صفرٌ يعني «غيرُ مشتركة» — ولا عمودَ ثانٍ يمكن أن يخالفه."""
    rider = await rider_session(client)
    result = await _request(client, rider["headers"])
    assert result["status"] == 201
    assert Decimal(result["body"]["share_discount_percent"]) == 0
    assert result["body"]["share_group_id"] is None
    assert result["body"]["share_seat"] == 1


async def test_a_gendered_request_needs_an_explicit_choice(
    client: AsyncClient, session_factory, jordan_settings, sharing_on
):
    """**قرارُ المالك الرابع**: القبولُ الصامتُ لا يكفي في مسألة أمان.

    ولا يُبتلع الطلبُ صامتاً بتنفيذه بلا مشاركة: **يُرفض ليُرى** — نفسُ قاعدةِ
    `gender` على مسار الكبتن.
    """
    await enable_features(session_factory, FeatureKey.WOMEN_SERVICE_ENABLED)
    rider = await rider_session(client)

    refused = await _request(
        client, rider["headers"], share=True, gender_preference="female"
    )
    assert refused["status"] == 422
    assert refused["body"]["code"] == "ride_sharing_gender_choice_required"

    allowed = await _request(
        client,
        rider["headers"],
        share=True,
        gender_preference="female",
        share_gender_confirmed=True,
    )
    assert allowed["status"] == 201, allowed["body"]
    assert Decimal(allowed["body"]["share_discount_percent"]) == DISCOUNT


async def test_sharing_does_not_combine_with_stops(
    client: AsyncClient, session_factory, jordan_settings, sharing_on
):
    """القطعُ الأولُ بلا محطاتٍ وسيطة (SPEC §5.12)."""
    await enable_features(session_factory, FeatureKey.MULTI_STOP_ENABLED)
    rider = await rider_session(client)

    result = await _request(
        client,
        rider["headers"],
        share=True,
        stops=[{"lat": 31.96, "lng": 35.89}],
    )
    assert result["status"] == 422


async def test_the_company_bears_the_discount_and_the_driver_is_paid_in_full(
    client: AsyncClient, session_factory, jordan_settings, sharing_on
):
    """**قرارُ المالك الثالث، وهو قلبُ الميزة كلِّها.**

    الخصمُ صفُّ دفعةٍ بقناة `share` تُنشئها المنصةُ وتؤكّدها — فلا يَنقص ما
    يقبضه الكبتن بخصمٍ لم يقرّره، ولا يُخصم من محفظة الراكب شيءٌ مقابله.
    **والوعدُ يُحترم ولو لم يوجد شريك**: هذه الرحلةُ لم تُشارَك أحداً وبقي
    الخصمُ كاملاً.
    """
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)

    result = await _request(client, rider["headers"], share=True)
    assert result["status"] == 201, result["body"]
    ride_id = result["body"]["id"]

    await _drive_to_completion(client, driver, ride_id)

    async with session_factory() as session:
        ride = await session.get(Ride, ride_id)
        rows = list(
            await session.scalars(
                select(Payment).where(Payment.ride_id == ride.id)
            )
        )

    share_rows = [row for row in rows if row.method is PaymentMethod.SHARE]
    assert len(share_rows) == 1, rows
    discount = share_rows[0]
    assert discount.status is PaymentStatus.CONFIRMED
    # الخصمُ محسوبٌ على الأجرة النهائية بالنسبة المجمَّدة
    expected = (ride.final_fare * DISCOUNT / Decimal("100")).quantize(
        Decimal("0.001")
    )
    assert discount.amount == expected
    # **ولا يُخصم من محفظة الراكب**: `share` ليست في `WALLET_FUNDED_METHODS`
    assert discount.method not in (PaymentMethod.WALLET,)


async def test_the_share_discount_is_not_counted_as_coupon_spend(
    client: AsyncClient, session_factory, jordan_settings, sharing_on
):
    """**سببُ وجود قناةٍ مستقلة، لا التسمية.**

    `promo.spent()` يقيس مصروفَ الكوبون بجمع دفعات `promo`؛ فلو كُتب خصمُ
    المشاركة بالقناة نفسِها لاستُهلكت **ميزانيةُ الكوبون** بما لا يخصّها —
    سقفٌ ماليٌّ يُؤكل بصمت.
    """
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)

    result = await _request(client, rider["headers"], share=True)
    ride_id = result["body"]["id"]
    await _drive_to_completion(client, driver, ride_id)

    async with session_factory() as session:
        promo_rows = list(
            await session.scalars(
                select(Payment).where(
                    Payment.ride_id == ride_id,
                    Payment.method == PaymentMethod.PROMO,
                )
            )
        )
    assert promo_rows == []
