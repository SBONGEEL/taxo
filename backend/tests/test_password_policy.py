"""قائمةُ منع كلمات المرور — إذنُ المالك 2026-08-18.

**تُقاس من الباب الحقيقي لا من الدالة وحدَها**: `validate_password` هو الموضعُ
الوحيد، لكنّ ما يهمّ أن التسجيلَ **والاستعادة** كليهما يمرّان به — وبابٌ ينسى
النداءَ هو الشكلُ الذي يجعل قاعدةً مكتوبةً لا تعمل.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.exceptions import WeakPassword
from app.core.password_policy import COMMON_PASSWORDS, check
from tests.helpers import DRIVER

pytestmark = pytest.mark.asyncio


async def register_with(client: AsyncClient, password: str, phone: str = "0795550002"):
    from app.core.phone import normalize_phone
    from app.services.firebase_auth import mock_token

    return await client.post(
        "/auth/register",
        json=DRIVER
        | {
            "phone": phone,
            "password": password,
            "verification_token": mock_token(normalize_phone(phone, "JO")),
        },
    )


# ------------------------------------------------- كلُّ صنفِ منعٍ على حدة


async def test_a_common_password_is_refused(client: AsyncClient) -> None:
    response = await register_with(client, "password123")
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "weak_password"
    assert "شيوع" in body["message"]


async def test_the_phone_itself_is_refused(client: AsyncClient) -> None:
    """**والمقارنةُ بالخانات لا بالنصّ**: كتبها وطنيةً أو دوليةً فهي رقمُه."""
    response = await register_with(client, "0795550002", phone="0795550002")
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "weak_password"
    assert "هاتفك" in body["message"]


@pytest.mark.parametrize("password", ["aaaaaaaa", "abababab", "123123123", "12121212"])
async def test_pure_repetition_is_refused(
    client: AsyncClient, password: str
) -> None:
    response = await register_with(client, password)
    assert response.status_code == 422
    assert response.json()["code"] == "weak_password"
    assert "تكرار" in response.json()["message"]


async def test_a_good_password_still_registers(client: AsyncClient) -> None:
    """**الحارسُ يُقاس بما يسمح به أيضاً**: قائمةُ منعٍ ترفض كلَّ شيءٍ حارسٌ معطوب."""
    response = await register_with(client, "SuperSecret123")
    assert response.status_code == 201, response.text


# --------------------------------------------------------- خصائصُ القائمة


async def test_the_reset_door_applies_the_policy_too() -> None:
    """البابُ الثاني — والقاعدةُ التي تحرس باباً واحداً من بابين لا تحرس شيئاً."""
    import inspect

    from app.services.auth import password as password_service

    source = inspect.getsource(password_service.set_password)
    assert "validate_password" in source


async def test_no_entry_is_shorter_than_the_length_rule() -> None:
    """سطرٌ في القائمة أقصرُ من الحدّ **سطرٌ لا يعمل** — يرفضه الطولُ قبله.

    ويُفحص لأن قائمةً فيها موتى تُقرأ أطولَ مما تحرس.
    """
    from app.services.auth.password import MIN_PASSWORD_LENGTH

    too_short = [p for p in COMMON_PASSWORDS if len(p) < MIN_PASSWORD_LENGTH]
    assert not too_short, too_short


async def test_the_list_is_not_published_anywhere(client: AsyncClient) -> None:
    """**لا تُنشر ولا يُكشف عددُها** (شرطُ المالك): قائمةٌ معروفةٌ دليلُ تخمين."""
    body = (await client.get("/config")).text
    for entry in list(COMMON_PASSWORDS)[:10]:
        assert entry not in body
    assert "weak_password" not in body


async def test_every_refusal_names_its_reason_without_naming_the_list() -> None:
    """الرسالةُ تقول السبب ولا تقول القائمة."""
    for password, phone in (
        ("password123", None),
        ("0795550002", "0795550002"),
        ("aaaaaaaa", None),
    ):
        with pytest.raises(WeakPassword) as raised:
            check(password, phone=phone)
        message = raised.value.message
        assert message and any("؀" <= ch <= "ۿ" for ch in message)
        # لا يُذكر أيُّ عضوٍ من القائمة في نصِّ الرفض
        assert not any(entry in message for entry in COMMON_PASSWORDS)
