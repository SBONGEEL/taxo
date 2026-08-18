"""قواعدُ التحقق المنشورة — SPEC القسم ١٧.٣.

**ما يحرسه هذا الملف: ألّا يفترق حدٌّ منشورٌ عن حدِّ المخطط.** والاشتقاقُ
برمجيٌّ فيبدو الفحصُ تحصيلَ حاصل — وليس كذلك: ما يُمسك هنا هو أن **يُكتب حدٌّ
بيدٍ في النشر** (فيثبت بينما يتحرك المخطط)، أو أن **يُسقِط المشتقُّ حقلاً**
بصمت فيتحقق التطبيقُ من خمسةٍ من ستة ويُفاجأ بالسادس من الخادم.

والدرسُ من هذا المشروع نفسِه: حدُّ الرسائل رُفع من ٣ إلى ٢٠ في الخدمة وبقي ٣
في اختبارٍ ينسخه، فظلَّت المجموعةُ حمراءَ على master بلا أن ينتبه أحد.
"""

from __future__ import annotations

import pytest
from annotated_types import Ge, Le, MaxLen, MinLen
from httpx import AsyncClient

from app.core import validation_rules

pytestmark = pytest.mark.asyncio


# حدودُ المخطط ← أسماؤها في الجسم المنشور
CONSTRAINTS = (
    (MinLen, "min_length", lambda c: c.min_length),
    (MaxLen, "max_length", lambda c: c.max_length),
    (Ge, "min", lambda c: c.ge),
    (Le, "max", lambda c: c.le),
)


@pytest.mark.parametrize("form", sorted(validation_rules.FORMS))
async def test_every_published_limit_equals_the_schema_limit(form: str) -> None:
    """لكل حقلٍ في كل نموذج: الحدُّ المنشور == حدُّ المخطط، ولا حقلَ يسقط."""
    model = validation_rules.FORMS[form]
    published = validation_rules.rules_for(model)

    assert set(published) == set(model.model_fields), (
        "حقلٌ سقط من النشر — التطبيقُ يتحقق مما يعرف ويُفاجأ بما لا يعرف"
    )

    for name, field in model.model_fields.items():
        rule = published[name]
        assert rule["required"] is field.is_required()
        for kind, key, read in CONSTRAINTS:
            expected = next(
                (read(c) for c in field.metadata if isinstance(c, kind)), None
            )
            assert rule.get(key) == expected, f"{form}.{name}.{key}"


async def test_the_published_rules_reach_the_apps(client: AsyncClient) -> None:
    """وتصل فعلاً في `GET /config` — وإلا فهي قواعدُ لا بابَ لها.

    وهو الشكلُ الذي كرّره هذا المشروع: مسارٌ يُبنى ولا يستدعيه أحد، وحقلٌ
    يُنشر ولا يقرؤه أحد.
    """
    response = await client.get("/config")
    assert response.status_code == 200
    published = response.json()["validation"]

    assert set(published) == set(validation_rules.FORMS)
    year = published["vehicle_create"]["year"]
    assert (year["min"], year["max"]) == (1990, 2100)
    assert year["messages"]["min"].startswith("سنة الصنع")
    # نصُّ القاعدة من السجل المركزي نفسِه، لا صياغةٌ ثانية
    assert "1990" in year["messages"]["min"]


async def test_the_published_message_is_the_same_text_the_backend_answers_with(
    client: AsyncClient,
) -> None:
    """**النصُّ واحدٌ في الطرفين** (القسم ١٧.٣) — وهذا ما يُثبته حرفياً.

    يُقارَن النصُّ المنشورُ للقاعدة بالنصِّ الذي يردّ به ٤٢٢ فعلاً على كسرها.
    ونصّان لشرطٍ واحد يجعلان المستخدمَ يظنّهما خطأين.
    """
    from tests.helpers import DRIVER, auth, register

    published = (await client.get("/config")).json()["validation"]
    expected = published["vehicle_create"]["year"]["messages"]["min"]

    driver = await register(client, DRIVER)
    response = await client.post(
        "/drivers/me/vehicles",
        json={
            "make": "Toyota",
            "model": "Corolla",
            "year": 5,
            "color": "أبيض",
            "plate_number": "12-34567",
            "category": "economy",
        },
        headers=auth(driver),
    )
    assert response.status_code == 422
    assert response.json()["message"] == expected


async def test_login_does_not_publish_the_password_policy() -> None:
    """**الاستثناء الأمني يمتدّ إلى القواعد المنشورة** (القسم ١٧.٥).

    مخططُ الدخول يقبل كلمةَ مرورٍ بأيِّ طول عمداً — فلو نشر الدخولُ سياسةَ
    التسجيل (٨ محارف) لأعطى المخمّنَ حدَّ البحث مجاناً. والفحصُ هنا يحرس أن
    يبقى المخططان مختلفين، لا أن «يُوحَّدا تنظيفاً».
    """
    login = validation_rules.rules_for(validation_rules.FORMS["login"])
    register = validation_rules.rules_for(validation_rules.FORMS["register"])
    assert login["password"]["min_length"] == 1
    assert register["password"]["min_length"] == 8
