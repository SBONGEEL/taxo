"""ظهورُ الدولة في الواجهات (2026-08-19، SPEC §24).

**وما يُقاس هنا ليس أن ليبيا مخفيّة، بل أن الإخفاءَ صفةُ سوقٍ عامّةٌ يقرؤها
بيتٌ واحد**: لا اسمَ دولةٍ في شرط، ولا قائمةَ مكتوبةٍ في تطبيق، ولا بابٌ ثانٍ
ينشر ما أخفاه الأول. وأنّ إشعالَه يُظهرها **في النداء التالي** — بلا بناءٍ ولا
نشرٍ ولا إعادةِ تشغيل.
"""

from __future__ import annotations

import pytest

from app.models.enums import CountryCode, FeatureKey
from app.services import settings_service

pytestmark = pytest.mark.asyncio


async def _set_visible(session_factory, country: CountryCode, visible: bool) -> None:
    async with session_factory() as session:
        await settings_service.set_flag(
            session,
            country_code=country,
            feature_key=FeatureKey.COUNTRY_VISIBLE,
            enabled=visible,
        )
        await session.commit()


def _codes(body: dict) -> list[str]:
    return [entry["country_code"] for entry in body["countries"]]


async def test_silence_means_visible(client) -> None:
    """**غيابُ الصفِّ ظهورٌ** — وإلا اختفت كلُّ دولةٍ على تثبيتٍ لم يُبذر.

    وهذا هو الاستثناءُ المعلَّل في `DEFAULT_ENABLED_FLAGS`: القاعدةُ العامة أن
    السكوت يُطفئ لئلا تُشعل ميزةُ مالٍ بالصمت، وهنا السكوتُ يُطفئ **التطبيقَ
    كلَّه** — لا دولةَ في القائمة، ولا شاشةَ دخولٍ تُرسم.
    """
    body = (await client.get("/config")).json()
    assert set(_codes(body)) == {c.value for c in CountryCode}


async def test_a_hidden_country_is_not_published(client, session_factory) -> None:
    """المطفأةُ تختفي من `/config` — ومعها كلُّ ما كان يُقرأ عنها."""
    await _set_visible(session_factory, CountryCode.LY, False)

    body = (await client.get("/config")).json()
    assert "LY" not in _codes(body)
    assert "JO" in _codes(body)


async def test_enabling_it_again_restores_it_on_the_next_call(
    client, session_factory
) -> None:
    """**الإشعالُ يُظهرها في النداء التالي** — لا بناءَ ولا نشرَ ولا إعادةَ تشغيل.

    وهذا هو سببُ وقوعِ التصفية في الخلفية لا في التطبيقات: قائمةٌ مكتوبةٌ في
    حزمةٍ لا تتغير إلا بحزمةٍ جديدةٍ على كل جهاز.
    """
    await _set_visible(session_factory, CountryCode.LY, False)
    assert "LY" not in _codes((await client.get("/config")).json())

    await _set_visible(session_factory, CountryCode.LY, True)
    assert "LY" in _codes((await client.get("/config")).json())


async def test_asking_for_a_hidden_country_by_name_gets_nothing(
    client, session_factory
) -> None:
    """ولا يُلتفّ عليه بـ`?country_code=` — التصفيةُ على المنشور لا على المسؤول عنه."""
    await _set_visible(session_factory, CountryCode.LY, False)

    body = (await client.get("/config?country_code=LY")).json()
    assert body["countries"] == []


async def test_the_default_country_is_never_one_that_is_hidden(
    client, session_factory
) -> None:
    """**افتراضيةٌ خارج القائمة تُقرأ `undefined`** — فتصير الأولى الظاهرة.

    التطبيقُ يبني عليها بادئةَ الهاتف وشاشةَ الدخول، فاسمُ دولةٍ ليست في
    `countries` حقلٌ بلا مرآة: يصل ويُقرأ ولا يقابله شيء.
    """
    from app.core.config import settings

    default = CountryCode(settings.default_country_code)
    await _set_visible(session_factory, default, False)

    body = (await client.get("/config")).json()
    assert body["default_country_code"] != default.value
    assert body["default_country_code"] in _codes(body)


async def test_the_panel_sees_every_market_including_the_hidden_one(
    client, session_factory, admin_headers
) -> None:
    """**اللوحةُ ترى الكلَّ دائماً**: من يشعل سوقاً يحتاج أن يراه مطفأً أولاً."""
    await _set_visible(session_factory, CountryCode.LY, False)

    answer = await client.get("/admin/countries", headers=admin_headers)
    assert answer.status_code == 200, answer.text
    rows = answer.json()["countries"]
    assert {row["country_code"] for row in rows} == {c.value for c in CountryCode}

    hidden = next(row for row in rows if row["country_code"] == "LY")
    assert hidden["visible"] is False
    assert hidden["name"]
    # **ومعها وصفُها كاملاً**: العملةُ وساعاتُ الهدوء تُقرآن في شاشتَي
    # التسعيرة والحملات وهي تُجهَّز قبل فتحها
    assert hidden["config"]["currency"]
    assert hidden["config"]["dial_code"]


async def test_the_two_doors_publish_the_same_description(
    client, admin_headers
) -> None:
    """**بانٍ واحدٌ لبابين** (الشكلُ الثامن): وصفٌ يُملأ في أحدهما ويُنسى في الآخر.

    وهذا ما وقع في عروض الاشتراكات: كلُّ بابٍ صادقٌ عن نفسه، ولا شيءَ يقارن.
    """
    public = {
        entry["country_code"]: entry
        for entry in (await client.get("/config")).json()["countries"]
    }
    panel = {
        row["country_code"]: row["config"]
        for row in (
            await client.get("/admin/countries", headers=admin_headers)
        ).json()["countries"]
    }

    for code, entry in public.items():
        assert panel[code] == entry, code


async def test_hiding_a_market_needs_no_written_reason(
    client, session_factory, admin_headers
) -> None:
    """**قرارُ إطلاقٍ لا إجراءُ طوارئ** — والسببُ المكتوب لغيره.

    المفتاحُ في `DEFAULT_ENABLED_FLAGS` لأن سكوتَه ظهور، وليس في
    `GUARDED_FLAGS` لأن إخفاءَ سوقٍ ليس إسقاطَ حارس. ولو جُمعا لطالبت اللوحةُ
    بسببٍ ورسالتُه تقول «مفتاح التحقق» — جملةٌ لا علاقةَ لها بما ضُغط.
    """
    answer = await client.put(
        "/admin/settings/feature-flags",
        json={
            "country_code": "LY",
            "feature_key": FeatureKey.COUNTRY_VISIBLE.value,
            "enabled": False,
        },
        headers=admin_headers,
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["flags"][FeatureKey.COUNTRY_VISIBLE.value] is False

    # وإطفاءُ الحارس ما يزال يطلب سبباً
    guard = await client.put(
        "/admin/settings/feature-flags",
        json={
            "country_code": "LY",
            "feature_key": FeatureKey.OTP_VERIFICATION_ENABLED.value,
            "enabled": False,
        },
        headers=admin_headers,
    )
    assert guard.status_code == 422, guard.text


async def test_every_toggle_lands_in_the_audit_log(
    client, session_factory, admin_headers
) -> None:
    """إخفاءُ سوقٍ وإظهارُه قرارٌ يُسأل عنه بعد شهر — فله صفٌّ باسم فاعله."""
    from sqlalchemy import select

    from app.models.audit import AdminAuditLog

    await client.put(
        "/admin/settings/feature-flags",
        json={
            "country_code": "LY",
            "feature_key": FeatureKey.COUNTRY_VISIBLE.value,
            "enabled": False,
        },
        headers=admin_headers,
    )

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(AdminAuditLog).where(AdminAuditLog.entity_type == "feature_flag")
            )
        ).all()
    written = [
        row
        for row in rows
        if row.details.get("feature_key") == FeatureKey.COUNTRY_VISIBLE.value
    ]
    assert written, "تبديلُ الظهور بلا صفِّ تدقيق"
    assert written[-1].details["country_code"] == "LY"
    assert written[-1].details["enabled"] is False
    assert written[-1].actor_id is not None


async def test_support_may_read_the_markets(client, support_headers) -> None:
    """رؤيةُ الأسواق **سياقٌ لا قرار** — والدعمُ يعمل في سوقٍ ليفهم صفَّه."""
    answer = await client.get("/admin/countries", headers=support_headers)
    assert answer.status_code == 200, answer.text


async def test_the_door_is_closed_to_whoever_is_not_staff(client) -> None:
    answer = await client.get("/admin/countries")
    assert answer.status_code == 401, answer.text
