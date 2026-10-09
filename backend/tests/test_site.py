"""إعداداتُ الصفحة التعريفية — **البند ٤٩ (§52)**.

**وما يُقاس هنا خمسُ قواعدَ لا يقولها المُترجِم:**

1. **قائمةُ السماح مقيسةٌ في الاتجاهين** — لا حقلَ خارجها يخرج، ولا حقلَ فيها
   يغيب. **والاتجاهُ الثاني هو المنسيّ**: بابٌ ينشر أقلَّ ممّا وعد يترك الصفحةَ
   بفراغٍ لا يُفسَّر.
2. **ولا رقمَ مالٍ يخرج — ولا نسبةُ العمولة** (§٦٩-ب، ٢٠٢٦-١٠-٠٩) — لا سعرٌ
   ولا سعرٌ مشطوب، **ولا نسبةٌ ولا ما يُشتقّ منها، مهما كانت النسبة**.
3. **والمفاتيحُ تُقرأ من مصدرها** — يتغيّر المصدرُ فيتغيّر الباب، بلا نسخةٍ
   ثانيةٍ تفترق. **والنسبةُ تبقى للمشرف من مصدرها**، لا من الباب العامّ.
4. **وبابُ الكتابة يختم القيمةَ قبل وبعد** — وما لم يتغيّر لا يُذكر.
5. **ولا صفَّ ثانٍ لهذا الجدول** — ولو حاول نداءان معاً.
"""

from __future__ import annotations

import io
import re
from decimal import Decimal
from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.audit import AdminAuditLog
from app.models.enums import CountryCode, FeatureKey
from app.models.site import SiteSettings
from app.services import settings_service, site as site_service

#: جذرُ حزمة الخلفية — **`tests/` تحته مباشرةً في الحاوية وتحت `backend/`
#: على المضيف**، فالمرجعُ يُشتقّ من موضع الملفّ لا من شكل الشجرة.
_APP = Path(__file__).resolve().parents[1] / "app"


# ─────────────────────────────────── قائمةُ السماح، في الاتجاهين


async def test_public_door_publishes_the_allowlist_and_nothing_else(
    client: AsyncClient,
) -> None:
    """**لا حقلَ خارج القائمة يخرج، ولا حقلَ فيها يغيب.**

    **والاتجاهان قاعدةٌ واحدة**: الأولُ يمنع تسريبَ عمودٍ يُضاف غداً، والثاني
    يمنع صفحةً تنتظر حقلاً لا يصلها. **وحارسٌ باتجاهٍ واحدٍ نصفُ حارس.**
    """
    response = await client.get("/public/site")
    assert response.status_code == 200
    body = response.json()

    # **والمحسوبُ يُستثنى لا يُصرَّح**: `features` **تُقرأ من مصدرها لا من
    # أعمدة الجدول**، فقائمةُ السماح تحرس الأعمدةَ وحدَها. **وكان معها
    # `commission_percent` و`driver_keeps_per_100`** — نُزعا من الباب (§٦٩-ب)،
    # **فلو عادا لسقط هذا الاختبارُ بأنهما «خارج القائمة»** لا بصمت.
    published = set(body) - {"features"}
    allowed = set(site_service.PUBLIC_FIELDS)

    assert published - allowed == set(), "خرج حقلٌ خارج قائمة السماح"
    assert allowed - published == set(), "حقلٌ في القائمة لم يخرج"


async def test_a_new_column_is_not_published_until_it_is_allowed() -> None:
    """**عمودٌ يُضاف إلى الجدول لا ينشر نفسَه.**

    **وهذا هو الفرقُ بين السماح والاستبعاد**: قائمةُ استبعادٍ تُنسى عند أوّل
    عمودٍ يُضاف، **وقائمةُ سماحٍ لا تنشر ما لم يُذكر فيها**. ويُقاس بالنصّ لأن
    العطبَ يقع وقتَ الكتابة لا وقتَ التشغيل.
    """
    model = io.open(_APP / "models/site.py", encoding="utf-8").read()
    columns = set(re.findall(r"^    ([a-z_]+): Mapped", model, re.M))
    allowed = set(site_service.PUBLIC_FIELDS)

    # `singleton` قفلُ الجدول لا محتواه — **محجوبٌ بقصدٍ لا بسهو**
    assert columns - allowed == {"singleton"}


# ─────────────────────────────────── ولا رقمَ مالٍ — ولا النسبة


#: **ما نُزع من الباب العامّ مع الموقع الجديد** (§٦٩-ب): النسبةُ وما يُشتقّ منها
_COMMISSION_FIELDS = ("commission_percent", "driver_keeps_per_100")


async def test_no_money_number_leaves_the_public_doors(client: AsyncClient) -> None:
    """**لا سعرٌ ولا سعرٌ مشطوبٌ ولا مكافأة — ولا نسبةُ العمولة** (§٦٩-ب).

    **ويُقاس على الحمولة لا على الشاشة**: صفحةٌ لا ترسم رقماً يصلها ما زالت
    تحمله، **ويقرؤه من يفتح أدوات المطوّر**.
    """
    site = (await client.get("/public/site")).json()
    landing = (await client.get("/public/landing")).json()

    for forbidden in ("price", "price_after", "amount", "reward", "currency", *_COMMISSION_FIELDS):
        assert forbidden not in site
        if landing.get("offer") is not None:
            assert forbidden not in landing["offer"]


# ─────────────────────────────────── تُقرأ من مصدرها لا تُنسخ


async def test_no_commission_on_the_public_door_at_any_commission(
    client: AsyncClient, session_factory
) -> None:
    """**ولا نسبةَ عمولةٍ في الباب العامّ مهما كانت** — ولا رقمُها في أيِّ حقل.

    **والصفرُ أوّلاً** (هو الذي كسر «1E+2» يومَ كان المتبقّي يُنشر)، ثمّ نسبتان
    غيرُه: **بابٌ لا يُخرج الحقلَ عند نسبةٍ ويُخرجه عند أخرى يخضرّ اختبارُه بنسبةٍ
    واحدة**. ويُبحث عن الرقم نفسِه في الحمولة كلِّها لا عن اسم الحقل وحدَه —
    **فحقلٌ بعنوانٍ جديدٍ يحمل النسبةَ يسقط هنا** (§٦٩-ب).
    """
    for percent in (Decimal("0.00"), Decimal("2.00"), Decimal("12.50")):
        async with session_factory() as session:
            setting = await settings_service.get_or_create_commission(
                session, CountryCode.JO
            )
            setting.commission_enabled = True
            setting.commission_percent = percent
            await session.commit()

        response = await client.get("/public/site")
        body = response.json()
        for field in _COMMISSION_FIELDS:
            assert field not in body, f"النسبة {percent}: خرج {field}"
        for shown in {str(percent), format(percent.normalize(), "f")} - {"0"}:
            assert f'"{shown}"' not in response.text, f"النسبة {percent} في الحمولة"


async def test_the_panel_reads_the_commission_from_its_source(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**المشرفُ يرى النسبةَ السارية في شاشة «الموقع»** — من مصدرها لا من الباب.

    **يتغيّر إعدادُ العمولة فيتغيّر ما تعرضه الشاشة** — بلا مفتاحٍ ثانٍ ولا نسخة،
    **والبابُ العامُّ في اللحظة نفسِها لا يحملها**: النسبةُ تُعرض لمن يدير ولا
    تُنشر لمن يزور.
    """
    before = (await client.get("/admin/site", headers=admin_headers)).json()[
        "commission_percent"
    ]
    async with session_factory() as session:
        setting = await settings_service.get_or_create_commission(
            session, CountryCode.JO
        )
        setting.commission_enabled = True
        setting.commission_percent = Decimal("12.50")
        await session.commit()

    after = (await client.get("/admin/site", headers=admin_headers)).json()[
        "commission_percent"
    ]
    assert isinstance(after, str)  # **نصٌّ لا عائم** — قاعدةُ `NUMERIC` في هذا المستودع
    assert Decimal(after) == Decimal("12.50")
    assert after != before
    assert "commission_percent" not in (await client.get("/public/site")).json()


async def test_feature_flags_are_read_from_the_config_source(
    client: AsyncClient, session_factory
) -> None:
    """**المفاتيحُ من المصدر الذي يقرؤه `GET /config`** — لا نسخةٌ ثانية."""
    async with session_factory() as session:
        await settings_service.set_flag(
            session,
            country_code=CountryCode.JO,
            feature_key=FeatureKey.TIPS_ENABLED,
            enabled=False,
        )
        await session.commit()

    body = (await client.get("/public/site")).json()
    assert body["features"][FeatureKey.TIPS_ENABLED.value] is False


# ─────────────────────────────────── بابُ الكتابة


async def test_patch_records_before_and_after_for_what_changed_only(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**القيمةُ قبل وبعد** — وما لم يتغيّر لا يُذكر في السجلّ."""
    await client.get("/admin/site", headers=admin_headers)

    response = await client.patch(
        "/admin/site",
        json={"hero_note": "في الأردن الآن", "hero_title": "TAXO — عنوانٌ جديد"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["hero_title"] == "TAXO — عنوانٌ جديد"

    async with session_factory() as session:
        entry = await session.scalar(
            select(AdminAuditLog)
            .where(AdminAuditLog.entity_type == "site_settings")
            .order_by(AdminAuditLog.created_at.desc())
        )
    changes = entry.details["changes"]
    assert set(changes) == {"hero_title"}, "ذُكر حقلٌ لم يتغيّر"
    assert changes["hero_title"]["before"] == site_service.DEFAULTS["hero_title"]
    assert changes["hero_title"]["after"] == "TAXO — عنوانٌ جديد"


async def test_unsent_fields_are_not_wiped(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**«لم يُرسَل» ليست «أُرسل فارغاً»** — وحفظُ قسمٍ لا يمحو قسماً آخر."""
    await client.patch(
        "/admin/site", json={"support_email": "a@tajora.ly"}, headers=admin_headers
    )
    await client.patch(
        "/admin/site", json={"privacy_email": "b@tajora.ly"}, headers=admin_headers
    )

    body = (await client.get("/admin/site", headers=admin_headers)).json()
    assert body["support_email"] == "a@tajora.ly"
    assert body["privacy_email"] == "b@tajora.ly"


async def test_store_link_must_be_google_play(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**زرٌّ يقول «Google Play» ويفتح غيرَه يكذب على من ضغطه.**"""
    bad = await client.patch(
        "/admin/site",
        json={"play_url_rider": "https://example.com/app"},
        headers=admin_headers,
    )
    assert bad.status_code == 422

    good = await client.patch(
        "/admin/site",
        json={"play_url_rider": "https://play.google.com/store/apps/details?id=ly.tajora.rider"},
        headers=admin_headers,
    )
    assert good.status_code == 200

    # **والفارغُ مقبولٌ بقصد** — لا زرَّ بلا رابط، فالفراغُ شارةٌ معطَّلة
    empty = await client.patch(
        "/admin/site", json={"play_url_rider": ""}, headers=admin_headers
    )
    assert empty.status_code == 200
    assert empty.json()["play_url_rider"] == ""


async def test_links_must_be_https(client: AsyncClient, admin_headers: dict) -> None:
    """**صفحةٌ عامّةٌ تفتح `http` تُنذر المتصفّحُ زائرَها.**"""
    response = await client.patch(
        "/admin/site",
        json={"social_instagram": "http://instagram.com/taxo"},
        headers=admin_headers,
    )
    assert response.status_code == 422


async def test_distribution_mode_has_two_values_only(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**وضعان لا ثالث** — والقيمةُ المخترعةُ تُردّ لا تُخزَّن."""
    assert (
        await client.patch(
            "/admin/site", json={"distribution_mode": "none"}, headers=admin_headers
        )
    ).status_code == 422

    for mode in site_service.DISTRIBUTION_MODES:
        response = await client.patch(
            "/admin/site", json={"distribution_mode": mode}, headers=admin_headers
        )
        assert response.status_code == 200
        assert response.json()["distribution_mode"] == mode


# ─────────────────────────────────── صفٌّ واحدٌ لا غير


async def test_only_one_row_can_exist(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**جدولُ إعداداتٍ بصفّين يجعل «أيُّهما يحكم؟» سؤالاً لا جواب له.**"""
    await client.get("/admin/site", headers=admin_headers)
    await client.get("/admin/site", headers=admin_headers)
    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(SiteSettings))
    assert count == 1


async def test_the_public_door_writes_nothing(
    client: AsyncClient, session_factory
) -> None:
    """**مسارٌ يفتحه زائرٌ لا يكتب في القاعدة** — ولا يُنشئ صفَّ إعدادات."""
    async with session_factory() as session:
        before = await session.scalar(select(func.count()).select_from(SiteSettings))
    await client.get("/public/site")
    async with session_factory() as session:
        after = await session.scalar(select(func.count()).select_from(SiteSettings))
    assert after == before


async def test_policies_stay_private_by_default(client: AsyncClient) -> None:
    """**مطفأٌ افتراضاً بقرارِ المالك المكتوب** — ولا نصَّ يُعرض قبل مراجعته."""
    assert (await client.get("/public/site")).json()["policies_public"] is False


async def test_every_new_service_card_carries_the_new_badge_until_the_panel_removes_it(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**شارةُ «جديد»** (SPEC §٧١-ج/٨): الستُّ كلُّها افتراضاً على البابين، **والمشرفُ ينزعها بطاقةً بطاقة** — ومفتاحٌ لا بطاقةَ
    له يُرفض: زرٌّ يُضغط فلا يقع شيء. **والترتيبُ ترتيبُ الصفحة** لا ترتيبُ الضغط."""
    await client.get("/admin/site", headers=admin_headers)
    assert (await client.get("/public/site")).json()["new_cards"] == list(site_service.NEW_CARDS_DEFAULT)

    unknown = await client.patch("/admin/site", json={"new_cards": ["airport", "teleport"]}, headers=admin_headers)
    assert unknown.status_code == 422, unknown.text

    fewer = await client.patch("/admin/site", json={"new_cards": ["parcel", "airport"]}, headers=admin_headers)
    assert fewer.status_code == 200, fewer.text
    assert (await client.get("/public/site")).json()["new_cards"] == ["airport", "parcel"]


async def test_the_faq_stays_off_the_public_door_until_it_is_switched_on(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**قسمُ الأسئلة مطفأٌ افتراضاً** (SPEC §٧١-ج/٩): الأسئلةُ تُكتب في اللوحة وتُقرأ فيها، **والبابُ العامُّ يعطي قائمةً فارغةً**
    حتى يُشعَل — نصٌّ لم يُشعَل لا يصل حمولةَ زائرٍ ولو لم يُرسم."""
    faq = [{"q": "هل التطبيق مجاني للراكب؟", "a": "نعم.", "order": 1}]
    saved = await client.patch("/admin/site", json={"faq": faq}, headers=admin_headers)
    assert saved.status_code == 200, saved.text
    panel = (await client.get("/admin/site", headers=admin_headers)).json()
    assert panel["faq"] == faq and panel["faq_enabled"] is False
    public = (await client.get("/public/site")).json()
    assert public["faq"] == [] and public["faq_enabled"] is False

    await client.patch("/admin/site", json={"faq_enabled": True}, headers=admin_headers)
    public = (await client.get("/public/site")).json()
    assert public["faq"] == faq and public["faq_enabled"] is True
