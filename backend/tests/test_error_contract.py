"""عقدُ الأخطاء — SPEC القسم ١٧.

**ما يحرسه هذا الملف ليس نصوصَ الرسائل بل شكلَ الجسم وعدمَ تسرُّب الداخل.**
النصُّ يُعدَّل في السجل المركزي وحدَه؛ والذي يجب ألّا يتغيّر أبداً هو أن يخرج
**شكلٌ واحد** من كل باب، وألّا تصل المستخدمَ جملةٌ إنجليزيةٌ من مكتبة.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.helpers import DRIVER, auth, register

pytestmark = pytest.mark.asyncio

VEHICLE = {
    "make": "Toyota",
    "model": "Corolla",
    "year": 2020,
    "color": "أبيض",
    "plate_number": "12-34567",
    "category": "economy",
}

# **ما لا يجوز أن يصل المستخدم أبداً** (القسم ١٧.٤). والفحصُ على النصِّ الخارج
# كلِّه لا على حقلٍ بعينه: تسريبُ نصِّ مكتبةٍ يقع من أيِّ حقلٍ يُضاف لاحقاً.
LEAKS = (
    "Input should be",
    "Field required",
    "value is not a valid",
    "Not Found",
    "Traceback",
    "asyncpg",
    "sqlalchemy",
    "/app/",
)


def assert_contract(body: dict) -> None:
    """الشكلُ الواحد: `code` و`message` عربيةٌ، و`field` إن وُجد."""
    assert set(body) >= {"code", "message"}, body
    assert isinstance(body["code"], str) and body["code"]
    assert isinstance(body["message"], str) and body["message"]
    assert "detail" not in body, "الاسمُ القديم عاد — العقدُ يُحرَس بالكسر"
    if "field" in body:
        assert isinstance(body["field"], str)
    for leak in LEAKS:
        assert leak not in str(body), f"تسرَّب «{leak}» إلى المستخدم"
    # نصٌّ عربيٌّ فعلاً، لا اسمُ حقلٍ ولا رمز
    assert any("؀" <= ch <= "ۿ" for ch in body["message"]), body["message"]


# ------------------------------------------------------- الشكل من كل باب


async def test_app_error_carries_code_and_message(client: AsyncClient) -> None:
    """خطأُ أعمال — البابُ الأول."""
    response = await client.post(
        "/auth/login",
        json={"phone": "0790000009", "password": "whatever1", "country_code": "JO"},
    )
    assert response.status_code == 401
    assert_contract(response.json())


async def test_validation_error_names_the_field(client: AsyncClient) -> None:
    """٤٢٢ — البابُ الثاني، وهو الذي لم يكن له معالجٌ أصلاً."""
    response = await client.post("/auth/register", json={})
    assert response.status_code == 422
    body = response.json()
    assert_contract(body)
    assert body["code"] == "validation_error"
    assert body["field"] == "phone"
    # وبقيةُ الحقول تُرسل معاً ليُعلَّم كلُّها في دفعةٍ واحدة
    assert {item["field"] for item in body["errors"]} >= {
        "name",
        "password",
        "country_code",
    }


async def test_unknown_route_is_arabic_and_shaped(client: AsyncClient) -> None:
    """ما ترفعه Starlette نفسُها — البابُ الثالث.

    ويُفحص لأن معالجاً على `fastapi.HTTPException` **لا يلتقطه**: راوترُ
    Starlette يرفع الصنفَ الأمّ، فيخرج `{"detail": "Not Found"}` بالإنجليزية.
    وقع ذلك فعلاً في هذه الجلسة وصُحِّح.
    """
    response = await client.get("/definitely-not-a-route")
    assert response.status_code == 404
    assert_contract(response.json())


# ------------------------------------------------- كلمة المرور: شرطٌ شرطاً


@pytest.mark.parametrize(
    ("password", "expect_ok"),
    [
        ("", False),
        ("a", False),
        ("Short7", False),
        ("SuperSecret123", True),
        ("x" * 129, False),
    ],
)
async def test_each_password_rule_on_its_own(
    client: AsyncClient, password: str, expect_ok: bool
) -> None:
    """**شروطُ كلمة المرور اليوم شرطٌ واحد: الطولُ ٨–١٢٨** (`schemas/auth.py`).

    ولا يُضاف شرطٌ هنا: القسمُ ٧ من الطلب يمنع تغييرَ منطقِ عملٍ قائمٍ بحجة
    توحيد الرسائل، وإضافةُ «رقمٌ وحرفٌ كبير» تمنع كلماتِ مرورٍ يقبلها النظامُ
    اليوم — وهو قرارُ منتَجٍ لا تنسيقُ رسالة.
    """
    from app.core.phone import normalize_phone
    from app.services.firebase_auth import mock_token

    phone = "0795550001"
    payload = DRIVER | {
        "phone": phone,
        "password": password,
        "verification_token": mock_token(normalize_phone(phone, "JO")),
    }
    response = await client.post("/auth/register", json=payload)
    if expect_ok:
        assert response.status_code == 201, response.text
        return
    assert response.status_code == 422
    body = response.json()
    assert_contract(body)
    assert body["field"] == "password"


# ------------------------------------------------------------- المركبة


async def test_a_correct_vehicle_request_is_accepted(client: AsyncClient) -> None:
    driver = await register(client, DRIVER)
    response = await client.post(
        "/drivers/me/vehicles", json=VEHICLE, headers=auth(driver)
    )
    assert response.status_code == 201, response.text


@pytest.mark.parametrize("field", sorted(VEHICLE))
async def test_each_missing_required_vehicle_field_is_named(
    client: AsyncClient, field: str
) -> None:
    """حقلٌ ناقص — **ويُسمّى بعينه**.

    و`category` وحدَها لها قيمةٌ افتراضية في المخطط، فغيابُها ليس خطأً — وذلك
    فرقٌ يجب أن يبقى مرئياً في الاختبار لا أن يُخفى بحذف الحالة.
    """
    driver = await register(client, DRIVER)
    body = {key: value for key, value in VEHICLE.items() if key != field}
    response = await client.post(
        "/drivers/me/vehicles", json=body, headers=auth(driver)
    )
    if field == "category":
        assert response.status_code == 201, response.text
        return
    assert response.status_code == 422
    payload = response.json()
    assert_contract(payload)
    assert payload["field"] == field


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("year", None),  # Number("٢٠٢٠") = NaN ⇒ null
        ("year", "٢٠٢٠"),  # نصٌّ بأرقامٍ عربية
        ("year", 5),  # يمرّ حارسَ التطبيق «غيرُ فارغ» ويُرفض هنا
        ("year", 3000),
        ("plate_number", "7"),  # يمرّ الحارسَ نفسَه
        ("category", "suv"),
        ("make", ""),
    ],
)
async def test_a_wrong_typed_vehicle_field_is_named_in_arabic(
    client: AsyncClient, field: str, value: object
) -> None:
    driver = await register(client, DRIVER)
    response = await client.post(
        "/drivers/me/vehicles", json=VEHICLE | {field: value}, headers=auth(driver)
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert_contract(body)
    assert body["field"] == field


# ------------------------------------------------- الاستثناء الأمني (١٧.٥)


async def test_login_does_not_distinguish_unknown_phone_from_wrong_password(
    client: AsyncClient,
) -> None:
    """**رسالةٌ واحدةٌ ورمزٌ واحد**، وإلا مُنح المخمّنُ نصفَ الجواب مجاناً.

    والفحصُ على الرمز أيضاً لا على النصّ وحدَه: رمزان مختلفان بنصٍّ واحدٍ
    يفرّقان بينهما لمن يقرأ الجسم — وهو ما يفعله المخمّن، لا الإنسان.
    """
    await register(client, DRIVER)

    unknown = await client.post(
        "/auth/login",
        json={
            "phone": "0799999999",
            "password": "SuperSecret123",
            "country_code": "JO",
        },
    )
    wrong = await client.post(
        "/auth/login",
        json={
            "phone": DRIVER["phone"],
            "password": "WrongPassword9",
            "country_code": "JO",
        },
    )

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["message"] == wrong.json()["message"]
    assert unknown.json()["code"] == wrong.json()["code"]
    assert_contract(unknown.json())


# --------------------------------------------------------- حجبُ الأسرار


async def test_secrets_never_reach_the_log() -> None:
    """السجلُّ يأخذ الجسمَ كاملاً — فبغير الحجب تُكتب كلمةُ المرور صريحةً.

    **والمفتاحُ يبقى والقيمةُ تُحجب**: «أرسله فارغاً» و«لم يرسله» خطآن
    مختلفان في شاشةِ تسجيل، وحذفُ المفتاح يجعلهما واحداً.
    """
    from app.core.validation_errors import REDACTED, redact

    cleaned = redact(
        {
            "phone": "0791234567",
            "password": "SuperSecret123",
            "new_password": "x",
            "verification_token": "ey.J",
            "nested": {"recovery_code": "123456"},
            "items": [{"cvv": "999"}],
        }
    )
    assert cleaned["phone"] == "0791234567"
    assert cleaned["password"] == REDACTED
    assert cleaned["new_password"] == REDACTED
    assert cleaned["verification_token"] == REDACTED
    assert cleaned["nested"]["recovery_code"] == REDACTED
    assert cleaned["items"][0]["cvv"] == REDACTED
    assert "SuperSecret123" not in str(cleaned)
