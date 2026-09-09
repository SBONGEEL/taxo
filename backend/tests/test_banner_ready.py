"""**لافتةٌ بلا نصٍّ لا تبلغ أحداً** — والصفُّ يبقى ويُعلَن سببُه.

## العلّةُ مقيسةٌ لا مفترضة (٢٠٢٦-٠٩-٠٩)

على رئيسية الراكب بطاقةٌ فيها **جرسٌ وكلمة «لافتة جديدة» ولا شيءَ غيرها** —
صفٌّ أُنشئ من اللوحة ولم يُملأ، **ومشتعل**. ورآها الناسُ، **ورآها المتجرُ في
`site/assets-src/screens/rider-home.png` المنشورة**.

**والصفُّ لا يُحذف** (قرارُ المالك): الحذفُ يمحو شاهداً، والتحريرُ بيده.
**فالحارسُ يمنع العرضَ وحدَه**، ويقول للمشرف لماذا.

**ويُقاس بالنقض**: بحذف `and banner_is_ready(row)` من `banners_for` يسقط
`test_an_empty_banner_never_reaches_a_rider`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.models.enums import CampaignAudience, CountryCode, UserRole
from app.models.storefront import PromoBanner
from app.services.storefront import DEFAULT_BANNER_TITLE, banner_is_ready


def _banner(title: str | None, body: str | None) -> PromoBanner:
    now = datetime.now(UTC)
    return PromoBanner(
        id=uuid.uuid4(),
        country_code=CountryCode.JO,
        title=title,
        body=body,
        icon="gift",
        audience=CampaignAudience.ALL_RIDERS,
        sort_order=0,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=1),
        is_active=True,
    )


def test_a_banner_with_the_default_title_and_no_body_is_not_ready() -> None:
    """**هي التي رآها الناس**: عنوانٌ افتراضيٌّ وجسمٌ فارغ."""
    assert banner_is_ready(_banner(DEFAULT_BANNER_TITLE, None)) is False
    assert banner_is_ready(_banner(DEFAULT_BANNER_TITLE, "")) is False
    assert banner_is_ready(_banner(DEFAULT_BANNER_TITLE, "   ")) is False


def test_a_banner_with_no_title_and_no_body_is_not_ready() -> None:
    """**ولا عنوانَ أصلاً** — الحالُ نفسُها بثوبٍ آخر."""
    assert banner_is_ready(_banner(None, None)) is False
    assert banner_is_ready(_banner("", "")) is False


def test_a_body_alone_is_enough() -> None:
    """**ونصٌّ بلا عنوانٍ يبلغ**: فيه ما يُقرأ، والعنوانُ زينة.

    **ولا يُشترط الاثنان**: شرطٌ أضيقُ من الحاجة يحجب لافتةً صالحة، **وحارسٌ
    يصيح على سليمٍ يُطفأ** — فيسقط معه ما يمسكه حقّاً.
    """
    assert banner_is_ready(_banner(None, "خصمٌ على رحلتك الأولى")) is True
    assert banner_is_ready(_banner(DEFAULT_BANNER_TITLE, "خصمٌ على رحلتك")) is True


def test_a_real_title_is_enough() -> None:
    assert banner_is_ready(_banner("عرضُ الافتتاح", None)) is True


async def test_an_empty_banner_never_reaches_a_rider(session_factory) -> None:
    """**والقياسُ عند الباب لا عند الدالّة**: صفٌّ حيٌّ في القاعدة لا يخرج.

    فلو صُفّي في التطبيق بدل الخلفية لَبقيت ثلاثةُ أبوابٍ مفتوحة.
    """
    from app.services import storefront

    now = datetime.now(UTC)
    async with session_factory() as session:
        empty = _banner(DEFAULT_BANNER_TITLE, None)
        good = _banner("عرضُ الافتتاح", "خصمٌ على أوّل رحلة")
        session.add_all([empty, good])
        await session.commit()

        rows = await storefront.banners_for(
            session, country=CountryCode.JO, role=UserRole.RIDER
        )
        titles = [r.title for r in rows]
        assert "عرضُ الافتتاح" in titles, titles
        assert DEFAULT_BANNER_TITLE not in titles, (
            "لافتةٌ بلا نصٍّ بلغت الراكب: " + str(titles)
        )
        # **والصفُّ باقٍ** — الحجبُ عرضٌ لا حذف
        alive = await storefront.list_banners(session, country=CountryCode.JO)
        assert any(r.title == DEFAULT_BANNER_TITLE for r in alive), (
            "الصفُّ اختفى — والحارسُ يمنع العرضَ لا يحذف"
        )
