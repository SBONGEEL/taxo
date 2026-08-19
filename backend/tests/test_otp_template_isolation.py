"""عزلُ القالبين — **أخطرُ ما في الميزة، لأن خلطَهما لا يُحدث عطباً ظاهراً**.

كلا القالبين يحمل رمزاً صحيحاً: لا استثناءَ يُرفع، ولا رسالةَ ترتدّ، ولا شكوى
تصل — ويقرأ صاحبُ الرقم «استعادةُ كلمة المرور» وهو ينشئ حساباً. فلا شيءَ يمسك
هذا إلا اختبارٌ يسأل: **أيُّ نصٍّ خرج على السلك من أيِّ باب؟**

ولذلك يُقاس هنا **النصُّ المسلَّم إلى المزود**، لا استدعاءُ الدالة: مسارٌ يمرّر
الغرضَ صحيحاً ثم يقرأ القالبَ الآخر يمرّ في اختبارٍ يفحص الوسائط وحدَها.
"""

from __future__ import annotations

import pytest

from app.models.otp_template import OtpMessageTemplate, OtpTemplatePurpose
from app.core.redis_client import get_redis_client
from app.services import otp, verification

pytestmark = pytest.mark.asyncio


class _Recorder:
    """مرسِلٌ يسجّل ما وصله بالضبط — نصّاً وغرضاً."""

    provider_name = "recorder"

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_code(
        self, to: str, code: str, *, ttl_minutes: int, purpose: str, body: str
    ) -> str:
        self.sent.append(
            {"to": to, "code": code, "purpose": purpose, "body": body}
        )
        return "recorded"


async def _store_both(session) -> None:
    session.add(
        OtpMessageTemplate(
            purpose=OtpTemplatePurpose.REGISTRATION,
            body="تسجيلٌ جديد — رمزك {code}",
        )
    )
    session.add(
        OtpMessageTemplate(
            purpose=OtpTemplatePurpose.PASSWORD_RESET,
            body="استعادةُ كلمة المرور — رمزك {code}",
        )
    )
    await session.commit()


async def test_the_registration_path_sends_the_registration_template(
    session_factory,
) -> None:
    recorder = _Recorder()
    async with session_factory() as session:
        await _store_both(session)
        await otp.issue(
            session,
            get_redis_client(),
            "+962790000031",
            sender=recorder,
            purpose=OtpTemplatePurpose.REGISTRATION,
        )
    assert len(recorder.sent) == 1
    sent = recorder.sent[0]
    assert sent["purpose"] == OtpTemplatePurpose.REGISTRATION
    assert sent["body"].startswith("تسجيلٌ جديد")
    assert "استعادة" not in sent["body"]


async def test_the_reset_path_sends_the_reset_template(session_factory) -> None:
    recorder = _Recorder()
    async with session_factory() as session:
        await _store_both(session)
        await otp.issue(
            session,
            get_redis_client(),
            "+962790000032",
            sender=recorder,
            purpose=OtpTemplatePurpose.PASSWORD_RESET,
        )
    sent = recorder.sent[0]
    assert sent["purpose"] == OtpTemplatePurpose.PASSWORD_RESET
    assert sent["body"].startswith("استعادةُ كلمة المرور")
    assert "تسجيلٌ جديد" not in sent["body"]


async def test_the_code_on_the_wire_is_the_code_that_was_stored(
    session_factory,
) -> None:
    """الاستبدالُ يضع الرمزَ الحقيقيَّ لا حرفَ المتغيّر ولا رمزاً آخر."""
    recorder = _Recorder()
    async with session_factory() as session:
        await _store_both(session)
        await otp.issue(
            session,
            get_redis_client(),
            "+962790000033",
            sender=recorder,
            purpose=OtpTemplatePurpose.REGISTRATION,
        )
    sent = recorder.sent[0]
    assert "{" not in sent["body"]
    assert sent["code"] in sent["body"]


async def test_challenge_passes_the_purpose_and_never_decides_it() -> None:
    """**الطبقةُ الوسطى تمرّر ولا تقرّر** — وإلا صار للغرض مصدران."""
    import inspect

    source = inspect.getsource(verification.challenge)
    # كلُّ استدعاءٍ لـ issue داخلها يمرّر الغرضَ الذي وصلها
    assert source.count("otp.issue(") == source.count("purpose=purpose")
    assert "purpose=OtpTemplatePurpose" not in source


def _purposes_by_endpoint() -> dict[str, list[str]]:
    """أيُّ غرضٍ داخل أيِّ دالةِ باب — بالشجرة لا بالعدّ.

    **والعدُّ وحدَه لا يملك هذه القاعدة**، وقد قِيس: قلبُ الغرضين بين البابين
    يُبقي «واحدٌ لكلٍّ» صحيحاً، فيمرّ الاختبارُ والعطبُ قائم. فالسؤالُ ليس «كم
    مرة؟» بل **«أيُّهما في أيِّهما؟»**.
    """
    import ast
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "app" / "routers" / "auth.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))

    found: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        inside: list[str] = []
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Attribute)
                and isinstance(child.value, ast.Name)
                and child.value.id == "OtpTemplatePurpose"
            ):
                inside.append(child.attr)
        if inside:
            found[node.name] = inside
    return found


async def test_the_registration_route_holds_the_registration_purpose() -> None:
    """**بابٌ نُسي غرضُه يقع على الافتراضي صامتاً** — والافتراضيُّ هو التسجيل."""
    assert _purposes_by_endpoint()["start_challenge"] == ["REGISTRATION"]


async def test_the_reset_route_holds_the_reset_purpose() -> None:
    assert _purposes_by_endpoint()["start_password_reset"] == ["PASSWORD_RESET"]


async def test_no_third_route_quietly_declares_a_purpose() -> None:
    """بابٌ ثالثٌ يصرّح بغرضٍ يعني مساراً جديداً لم يفكّر فيه أحد."""
    assert set(_purposes_by_endpoint()) == {"start_challenge", "start_password_reset"}


async def test_every_challenge_call_declares_a_purpose() -> None:
    """استدعاءٌ بلا غرضٍ يقع على الافتراضي — وهو صحيحٌ لبابٍ وخاطئٌ للآخر."""
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[1] / "app" / "routers" / "auth.py"
    ).read_text(encoding="utf-8")
    assert text.count("verification.challenge(") == text.count("purpose=OtpTemplate")
