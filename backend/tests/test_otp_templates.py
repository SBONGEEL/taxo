"""قوالبُ رسالة الرمز (2026-08-19).

**وأخطرُ اختبارٍ هنا هو عزلُ القالبين**: خلطُهما يمرّ صامتاً لأن كليهما يحمل
رمزاً صحيحاً — لا استثناءَ يُرفع ولا شكوى تصل، ويقرأ صاحبُ الرقم «استعادةُ
كلمة المرور» وهو يسجّل حساباً جديداً.
"""

from __future__ import annotations

import pytest

from app.models.otp_template import OtpMessageTemplate, OtpTemplatePurpose
from app.services import otp_templates

pytestmark = pytest.mark.asyncio


# --------------------------------------------------------------- الشروط


def test_a_template_with_no_code_is_refused() -> None:
    bad = otp_templates.validate(
        "أهلاً بك في تاكسو", purpose=OtpTemplatePurpose.REGISTRATION
    )
    codes = [v.code for v in bad]
    assert "template_missing_variable" in codes
    # **الرسالةُ تسمّي القالبَ والمتغيّر معاً** — والحقلان على شاشةٍ واحدة
    message = next(v.message for v in bad if v.code == "template_missing_variable")
    assert "قالب التسجيل" in message and "code" in message


def test_the_message_names_the_other_template_when_it_is_the_other_one() -> None:
    bad = otp_templates.validate("بلا رمز", purpose=OtpTemplatePurpose.PASSWORD_RESET)
    assert "قالب استعادة كلمة المرور" in bad[0].message


def test_an_unknown_variable_is_refused_not_passed_through() -> None:
    bad = otp_templates.validate(
        "رمزك {code} يا {name}", purpose=OtpTemplatePurpose.REGISTRATION
    )
    codes = [v.code for v in bad]
    assert "template_unknown_variable" in codes
    assert "name" in next(
        v.message for v in bad if v.code == "template_unknown_variable"
    )


def test_a_link_is_refused() -> None:
    for text in (
        "رمزك {code} https://taxo.example",
        "رمزك {code} www.taxo.example",
        "رمزك {code} taxo.online",
    ):
        codes = [v.code for v in otp_templates.validate(text, purpose="registration")]
        assert "template_has_link" in codes, text


def test_a_template_over_the_measured_cap_is_refused() -> None:
    cap = otp_templates.max_bytes()
    body = "{code} " + "ب" * cap  # حرفان بايت، فالتجاوزُ مضمون
    codes = [v.code for v in otp_templates.validate(body, purpose="registration")]
    assert "template_too_long" in codes


def test_an_empty_template_is_refused() -> None:
    bad = otp_templates.validate("   ", purpose="registration")
    assert [v.code for v in bad] == ["template_empty"]


def test_a_correct_template_passes() -> None:
    assert (
        otp_templates.validate(
            "رمز تأكيد رقمك في {app_name}: {code} صالح {minutes} دقيقة.",
            purpose="registration",
        )
        == []
    )


# --------------------------------------------------------------- الاستبدال


def test_rendering_replaces_every_known_variable_and_leaves_nothing() -> None:
    # **واسمُ التطبيق من إعداده** — لا ثابتاً هنا ولا في دالّة الصياغة
    from app.core.config import settings

    out = otp_templates.render(
        "{app_name}: {code} — {minutes} دقيقة", code="4321", minutes=7
    )
    assert out == f"{settings.app_name}: 4321 — 7 دقيقة"
    assert "{" not in out


def test_a_lone_brace_in_arabic_text_does_not_raise() -> None:
    """str.format كانت سترفع KeyError وقتَ الإرسال — في مسارِ رمزٍ ينتظره إنسان."""
    assert otp_templates.render("رمزك {code} } {", code="1", minutes=2) == "رمزك 1 } {"


# --------------------------------------------------------------- القراءة


async def test_a_missing_row_reads_the_built_in_default(session_factory) -> None:
    async with session_factory() as session:
        body = await otp_templates.body_for(session, OtpTemplatePurpose.REGISTRATION)
    assert body == otp_templates.DEFAULTS[OtpTemplatePurpose.REGISTRATION]
    assert "{code}" in body


async def test_a_stored_but_violating_row_falls_back_to_the_default(
    session_factory,
) -> None:
    """**لا تسقط قناةُ التسجيل بنصٍّ محرَّرٍ خطأً** — ولو كان مكتوباً في الجدول."""
    async with session_factory() as session:
        session.add(
            OtpMessageTemplate(purpose=OtpTemplatePurpose.REGISTRATION, body="بلا رمز")
        )
        await session.commit()
        body = await otp_templates.body_for(session, OtpTemplatePurpose.REGISTRATION)
    assert body == otp_templates.DEFAULTS[OtpTemplatePurpose.REGISTRATION]


# --------------------------------------------------------------- اللوحة


async def test_saving_one_template_does_not_touch_the_other(
    client, admin_headers
) -> None:
    first = await client.put(
        "/admin/otp-templates/registration",
        json={"body": "تسجيل: {code}"},
        headers=admin_headers,
    )
    assert first.status_code == 200, first.text

    listed = (await client.get("/admin/otp-templates", headers=admin_headers)).json()
    by = {t["purpose"]: t for t in listed["templates"]}
    assert by["registration"]["body"] == "تسجيل: {code}"
    assert by["registration"]["is_default"] is False
    # والآخرُ لم يُمسّ — ما زال افتراضياً
    assert by["password_reset"]["is_default"] is True


async def test_the_panel_refuses_what_the_gateway_would_refuse(
    client, admin_headers
) -> None:
    response = await client.put(
        "/admin/otp-templates/password_reset",
        json={"body": "بلا رمز https://x.com"},
        headers=admin_headers,
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_otp_template"
    assert "قالب استعادة كلمة المرور" in body["message"]


async def test_the_preview_is_the_wire_text_not_an_approximation(
    client, admin_headers
) -> None:
    await client.put(
        "/admin/otp-templates/registration",
        json={"body": "{app_name}: {code} / {minutes}"},
        headers=admin_headers,
    )
    listed = (await client.get("/admin/otp-templates", headers=admin_headers)).json()
    row = next(t for t in listed["templates"] if t["purpose"] == "registration")
    from app.services import otp

    assert row["preview"] == otp_templates.render(
        row["body"],
        code=row["preview_sample_code"],
        minutes=otp.CODE_TTL_SECONDS // 60,
    )
    assert "{" not in row["preview"]


async def test_the_panel_publishes_the_measured_cap_and_the_variables(
    client, admin_headers
) -> None:
    listed = (await client.get("/admin/otp-templates", headers=admin_headers)).json()
    assert listed["max_body_bytes"] == otp_templates.max_bytes()
    assert listed["required_variables"] == ["code"]
    assert set(listed["optional_variables"]) == {"app_name", "minutes"}


async def test_every_edit_records_the_text_before_and_after(
    client, admin_headers, session_factory
) -> None:
    from sqlalchemy import select

    from app.models.audit import AdminAuditLog

    await client.put(
        "/admin/otp-templates/registration",
        json={"body": "أول: {code}"},
        headers=admin_headers,
    )
    await client.put(
        "/admin/otp-templates/registration",
        json={"body": "ثانٍ: {code}"},
        headers=admin_headers,
    )
    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(AdminAuditLog)
                .where(AdminAuditLog.entity_type == "otp_message_template")
                .order_by(AdminAuditLog.created_at)
            )
        ).all()
    assert len(rows) == 2
    assert rows[0].details["before"] == otp_templates.DEFAULTS["registration"]
    assert rows[0].details["after"] == "أول: {code}"
    assert rows[1].details["before"] == "أول: {code}"
    assert rows[1].details["after"] == "ثانٍ: {code}"
    assert rows[0].actor_id is not None


async def test_a_rejected_template_says_so_on_its_own_screen(
    client, admin_headers, session_factory
) -> None:
    """**لا يكفي السجل**: من حرّر نصّاً مخالفاً يظنّه يعمل حتى يقرأ الشاشة."""
    async with session_factory() as session:
        session.add(
            OtpMessageTemplate(purpose=OtpTemplatePurpose.PASSWORD_RESET, body="بلا رمز")
        )
        await session.commit()

    listed = (await client.get("/admin/otp-templates", headers=admin_headers)).json()
    row = next(t for t in listed["templates"] if t["purpose"] == "password_reset")
    assert row["rejected_at_send"] is True
    assert any(v["code"] == "template_missing_variable" for v in row["violations"])


# ------------------------------------------- المعاينة بالقيم الحقيقية (§19.8)


async def test_the_preview_uses_the_real_ttl_not_a_sample_number(
    client, admin_headers
) -> None:
    """**المعاينةُ تقرأ المهلةَ من مصدرها** — لا رقماً مكتوباً كعيّنة.

    كانت تعرض «10 دقيقة» والمهلةُ الحقيقيةُ خمس، فيحرّر المشرفُ على أساسٍ كاذب.
    والاختبارُ يقارن بالثابت نفسِه لا برقمٍ منسوخ: تغييرُ `CODE_TTL_SECONDS`
    يجب أن يحرّك المعاينةَ معه، لا أن يترك رقمين يفترقان.
    """
    from app.services import otp

    await client.put(
        "/admin/otp-templates/registration",
        json={"body": "رمزك {code} صالح {minutes} دقيقة"},
        headers=admin_headers,
    )
    listed = (await client.get("/admin/otp-templates", headers=admin_headers)).json()
    row = next(t for t in listed["templates"] if t["purpose"] == "registration")
    assert f"صالح {otp.CODE_TTL_SECONDS // 60} دقيقة" in row["preview"]


async def test_the_preview_uses_the_configured_app_name(
    client, admin_headers
) -> None:
    """واسمُ التطبيق من إعداده — لا ثابتاً في دالّة الصياغة."""
    from app.core.config import settings

    await client.put(
        "/admin/otp-templates/password_reset",
        json={"body": "{app_name}: {code}"},
        headers=admin_headers,
    )
    listed = (await client.get("/admin/otp-templates", headers=admin_headers)).json()
    row = next(t for t in listed["templates"] if t["purpose"] == "password_reset")
    assert row["preview"].startswith(f"{settings.app_name}: ")


async def test_only_the_code_is_a_sample_and_it_says_so(
    client, admin_headers
) -> None:
    """**الرمزُ وحدَه عيّنة**، ويُنشر كذلك — فلا تُقرأ المعاينةُ رمزاً حقيقياً.

    ولا مفرَّ منه: لا رمزَ قبل الإرسال، وتوليدُ واحدٍ للمعاينة رمزٌ حيٌّ لم
    يطلبه أحد.
    """
    listed = (await client.get("/admin/otp-templates", headers=admin_headers)).json()
    for row in listed["templates"]:
        assert row["preview_sample_code"]
        assert row["preview_sample_code"] in row["preview"]


async def test_the_wire_and_the_preview_agree_on_everything_but_the_code(
    session_factory, admin_headers, client
) -> None:
    """ما يُعرض وما يخرج **من دالّةٍ واحدة** — والفرقُ الرمزُ وحدَه."""
    from app.services import otp

    body = "{app_name} — {code} — {minutes}"
    await client.put(
        "/admin/otp-templates/registration",
        json={"body": body},
        headers=admin_headers,
    )
    listed = (await client.get("/admin/otp-templates", headers=admin_headers)).json()
    row = next(t for t in listed["templates"] if t["purpose"] == "registration")

    on_wire = otp_templates.render(
        body, code="999111", minutes=otp.CODE_TTL_SECONDS // 60
    )
    assert row["preview"].replace(row["preview_sample_code"], "999111") == on_wire


def test_the_bare_code_is_a_valid_template() -> None:
    """**قالبٌ لا يحمل غيرَ الرمز** (قرارُ المالك 2026-08-19).

    ما يُحرَس هنا ثلاثةٌ معاً: أن `{code}` وحدَه يمرّ، وأن الحارسَ الإلزاميَّ
    ما زال يعضّ من حذفه، وأن حدَّ الطول لم يتحرّك بحركة القالب.
    """
    from app.services import otp_templates

    assert otp_templates.validate("{code}", purpose="registration") == []
    assert otp_templates.validate("{code}", purpose="password_reset") == []

    # **ولا رسالةَ رمزٍ بلا رمز**: الأرقامُ مكتوبةً ليست المتغيّر
    missing = otp_templates.validate("123456", purpose="registration")
    assert [v.code for v in missing] == ["template_missing_variable"]

    # وحدُّ الطول مقيسٌ من ملفِّ الشروط لا من القالب
    assert otp_templates.max_bytes() == 3989
    too_long = "{code}" + "x" * 4000
    assert [v.code for v in otp_templates.validate(too_long, purpose="registration")] == [
        "template_too_long"
    ]


def test_the_preview_is_exactly_what_goes_on_the_wire() -> None:
    """**المعاينةُ تُصاغ بنفس الدالة التي تصوغ المرسَل** — لا نسخةٌ ثانية.

    وهذا شرطُ أن تكون المعاينةُ برهاناً: صياغتان تفترقان، فيرى المشرفُ شكلاً
    ويستقبل صاحبُ الهاتف شكلاً آخر.
    """
    from app.services import otp_templates

    rendered = otp_templates.render("{code}", code="424242", minutes=5)
    assert rendered == "424242"
    assert rendered.isdigit()
