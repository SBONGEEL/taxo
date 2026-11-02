"""فحصُ الرقم قبل رمز التسجيل (قرارُ المالك ٢٠٢٦-١١-٠٢، SPEC §٢٣.٢-أ).

**وما يُقاس هنا شيئان**: أن الجوابَ يقود صاحبَ الحساب إلى الدخول بلا رمز، **وأن الحدَّ يُعدّ الأرقامَ المختلفة لا
الطلبات** — من أعاد رقمَه لا يُحاسَب، ومن مسح أرقاماً يُوقَف عند سقفه.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.enums import UserRole
from app.models.user_role_grant import UserRoleGrant
from app.services import phone_check

pytestmark = pytest.mark.asyncio


def _body(phone: str, app: str = "driver", device: str | None = "dev-a") -> dict:
    return {"phone": phone, "country_code": "JO", "app": app, "device_id": device}


async def test_a_new_number_goes_on_to_the_code(client) -> None:
    answer = await client.post("/auth/phone-check", json=_body("0797000001"))
    assert answer.status_code == 200, answer.text
    assert answer.json() == {"status": "new"}


async def test_a_rider_number_in_the_captain_app_is_led_to_add_the_profile(client) -> None:
    from tests.helpers import RIDER, rider_session

    await rider_session(client)
    from_driver = await client.post("/auth/phone-check", json=_body(RIDER["phone"], "driver"))
    assert from_driver.json() == {"status": "other_role"}
    # **ومن تطبيقه نفسِه «مسجَّل»**: طريقُه الدخولُ لا الإضافة
    from_rider = await client.post("/auth/phone-check", json=_body(RIDER["phone"], "rider", "dev-b"))
    assert from_rider.json() == {"status": "registered"}


async def test_a_dual_role_number_is_registered_in_both(client, session_factory) -> None:
    from tests.helpers import RIDER, rider_session

    rider = await rider_session(client)
    async with session_factory() as session:
        session.add(UserRoleGrant(user_id=uuid.UUID(rider["user"]["id"]), role=UserRole.DRIVER))
        await session.commit()
    for app in ("rider", "driver"):
        answer = await client.post("/auth/phone-check", json=_body(RIDER["phone"], app))
        assert answer.json() == {"status": "registered"}


async def test_the_device_cap_counts_distinct_numbers_not_requests(client) -> None:
    cap = phone_check.DEVICE_LIMITS[0][0]
    numbers = [f"079700{index:04d}" for index in range(cap + 1)]
    for number in numbers[:cap]:
        # **ومن مصادرَ مختلفةٍ** فلا يسبق سقفُ الـIP سقفَ الجهاز
        answer = await client.post(
            "/auth/phone-check", json=_body(number), headers={"x-forwarded-for": f"10.0.0.{number[-2:]}"}
        )
        assert answer.status_code == 200, answer.text
    # **الرقمُ نفسُه ثانيةً لا يُحاسَب**
    again = await client.post("/auth/phone-check", json=_body(numbers[0]), headers={"x-forwarded-for": "10.0.1.1"})
    assert again.status_code == 200, again.text
    refused = await client.post("/auth/phone-check", json=_body(numbers[cap]), headers={"x-forwarded-for": "10.0.1.2"})
    assert refused.status_code == 429, refused.text


async def test_the_ip_cap_holds_when_the_device_id_rotates(client) -> None:
    cap = phone_check.IP_LIMITS[0][0]
    headers = {"x-forwarded-for": "203.0.113.9"}
    for index in range(cap):
        answer = await client.post(
            "/auth/phone-check", json=_body(f"079710{index:04d}", device=f"dev-{index}"), headers=headers
        )
        assert answer.status_code == 200, answer.text
    refused = await client.post(
        "/auth/phone-check", json=_body("0797199999", device="dev-fresh"), headers=headers
    )
    assert refused.status_code == 429, refused.text


async def test_a_closed_market_is_not_asked(client, session_factory) -> None:
    """**لا يُسأل عن رقمٍ في سوقٍ لا يُسجَّل فيه** — والإغلاقُ قبل الحدِّ وقبل القاعدة."""
    from app.models.enums import CountryCode, FeatureKey
    from app.services import settings_service

    async with session_factory() as session:
        await settings_service.set_flag(
            session, country_code=CountryCode.LY, feature_key=FeatureKey.COUNTRY_VISIBLE, enabled=False
        )
        await session.commit()
    answer = await client.post(
        "/auth/phone-check", json={"phone": "0912345678", "country_code": "LY", "app": "driver"}
    )
    assert answer.status_code == 403, answer.text
    assert answer.json()["code"] == "signup_closed"
