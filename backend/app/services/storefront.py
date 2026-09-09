"""بلاطاتُ الخدمات ولافتاتُ المحتوى — قراءةً وكتابةً (الترحيلة `0063`).

## ما يقرّره هذا الملفُّ وحدَه

**من يرى ماذا**: الجمهورُ والسوقُ والحالُ والنافذة — **في موضعٍ واحد**.
وتطبيقان يسألان السؤالَ نفسَه، **وحسابان له يفترقان أوّلَ تعديل**.

## و«فعّالة بلا مقصدٍ مبنيّ» يمنعها البابُ بعلّته

**طبقتان لا واحدة**: قيدُ القاعدة يمنع **الفارغ**، وهذا البابُ يمنع **ما ليس
مبنيّاً**. **والقاعدةُ لا تعرف مساراتِ React** — فقائمةٌ مصرَّحةٌ هنا يقابلها
مسارٌ في التطبيقين، **ولا تُقبل قيمةٌ خارجها**.

**وبلا هذه الطبقة يصير الإشعالُ وعداً بشاشةٍ لا وجودَ لها** — والكبتنُ يضغط
فلا يقع شيء، وهو الشكلُ «بابٌ بلا زرّ» مقلوباً: زرٌّ بلا باب.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInput, NotFound
from app.models.enums import (
    BannerLinkKind,
    CampaignAudience,
    CountryCode,
    ServiceTileStatus,
    UserRole,
)
from app.models.storefront import PromoBanner, ServiceTile

#: **المقاصدُ المبنيّةُ في التطبيقين** — والقائمةُ عقدٌ بين الخلفية والواجهة.
#:
#: **ولا تُقبل قيمةٌ خارجها**: مسارٌ يُكتب بيدٍ في اللوحة يفتح شاشةً لا وجودَ
#: لها، **والكبتنُ يضغط فلا يقع شيء**. وإضافةُ مسارٍ هنا **تُلزم بناءه** —
#: وهذا هو الاتجاهُ الصحيح: الشاشةُ أوّلاً ثم الإذنُ بالإشارة إليها.
# **أيقوناتٌ من قائمةٍ مقرَّرة لا حقلٍ حرّ** (قرارُ المالك 2026-08-31).
#
# **والحجّةُ قياسٌ لا ذوق**: اسمٌ خاطئٌ كان يرسم `LayoutGrid` **صامتاً** — لا
# خطأَ ولا تحذير — **فلا يعلم المشرفُ أنه أخطأ حتى يفتح التطبيق**. وهو «بديلٌ
# يعمل ويخفي العطبَ الذي بُني له» بعينه.
#
# **وموضعٌ واحدٌ يقرؤه من يحتاجه**: البابُ يرفض ما ليس فيها، **واللوحةُ تقرأها
# من `GET /admin/settings/service-icons`** فترسم منتقياً. **ولا نسخةٌ ثانيةٌ
# تُكتب في اللوحة** — نسختان تفترقان بحرفٍ يوماً، فيَعرض المنتقي ما يرفضه
# الباب.
#
# **والأسماءُ بصيغة lucide** (kebab) كما تنطقها المكتبةُ في التطبيقين.
SERVICE_ICONS: tuple[str, ...] = (
    # ── تنقّلٌ ومركبات
    "car", "car-taxi-front", "bus", "truck", "bike", "plane-takeoff",
    "map-pin", "map", "route", "navigation", "calendar-clock",
    # ── طرودٌ وتسوّق
    "package", "boxes", "shopping-bag", "shopping-cart", "store", "gift",
    # ── مالٌ ومحفظة
    "wallet", "banknote", "credit-card", "coins", "receipt", "percent",
    # ── حسابٌ وخدمة
    "user", "users", "shield-check", "life-buoy", "headphones", "star",
    "trophy", "badge-check", "bell", "settings", "file-text", "clock",
    # ── عامّ
    "layout-grid", "sparkles", "heart", "flame", "zap",
)


def require_icon(icon: str | None) -> None:
    """**اسمٌ خارج القائمة لا يُقبل أصلاً** — ولا يُرسم افتراضاً.

    **و`None` تمرّ**: اللافتةُ قد تكون بلا أيقونة، والبلاطةُ لا (عمودُها
    إلزاميّ). **فالفراغُ خيارٌ، والاسمُ الخاطئُ ليس خياراً.**
    """
    if icon is None:
        return
    if icon not in SERVICE_ICONS:
        raise InvalidInput(
            f"الأيقونة «{icon}» ليست من القائمة المقرَّرة — "
            "اخترها من المنتقي، ولا تُكتب باليد"
        )


SERVICE_DESTINATIONS: dict[str, tuple[UserRole, ...]] = {
    # ── مشتركةٌ بالمسار نفسِه في التطبيقين
    "/rides": (UserRole.RIDER, UserRole.DRIVER),
    "/wallet": (UserRole.RIDER, UserRole.DRIVER),
    "/account": (UserRole.RIDER, UserRole.DRIVER),
    "/account/cards": (UserRole.RIDER, UserRole.DRIVER),
    "/account/settings": (UserRole.RIDER, UserRole.DRIVER),
    "/account/referrals": (UserRole.RIDER, UserRole.DRIVER),
    # ── الراكب وحدَه
    "/account/bookings": (UserRole.RIDER,),
    "/account/places": (UserRole.RIDER,),
    "/account/profile": (UserRole.RIDER,),
    "/account/notifications": (UserRole.RIDER,),
    "/wallet/topup": (UserRole.RIDER,),
    "/wallet/transfer": (UserRole.RIDER,),
    # ── الكبتن وحدَه
    "/notifications": (UserRole.DRIVER,),
    "/subscription": (UserRole.DRIVER,),
    "/account/missions": (UserRole.DRIVER,),
    "/account/garage": (UserRole.DRIVER,),
    "/account/garage/store": (UserRole.DRIVER,),
    "/account/advances": (UserRole.DRIVER,),
    "/account/debt": (UserRole.DRIVER,),
    "/account/permissions": (UserRole.DRIVER,),
    "/account/vehicle": (UserRole.DRIVER,),
    "/wallet/withdrawals": (UserRole.DRIVER,),
    "/wallet/earnings": (UserRole.DRIVER,),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _audience_matches(audience: CampaignAudience, role: UserRole) -> bool:
    """**`by_country` تعني الاثنين** — مقروءةً من `campaigns.py` لا مخترَعة."""
    if audience is CampaignAudience.BY_COUNTRY:
        return role in (UserRole.RIDER, UserRole.DRIVER)
    if audience is CampaignAudience.ALL_RIDERS:
        return role is UserRole.RIDER
    if audience is CampaignAudience.ALL_DRIVERS:
        return role is UserRole.DRIVER
    # **`segment` تُرفض هنا كما تُرفض في الحملات** — ولا يُخترع لها معنى
    return False


def require_destination(
    destination: str | None,
    *,
    status: ServiceTileStatus,
    audience: CampaignAudience,
) -> None:
    """**فعّالةٌ بلا مقصدٍ مبنيٍّ لا تُقبل** — ويُمنع عند الإنشاء لا عند الضغط.

    **والجمهورُ جزءٌ من السؤال لا زينةٌ في الجدول** (عطبٌ قِيس 2026-08-30):
    أوّلُ نسخةٍ سألت «أهذا المسارُ مبنيّ؟» وحدَها، **وأدوارُ القاموس مكتوبةٌ
    لا يقرؤها أحد** — فمرّت بلاطةُ كبتنٍ تشير إلى `/account/bookings`،
    **وهو مسارُ الراكب**. فكان الكبتنُ يضغط ويقع على `path="*"`.

    **و«مبنيٌّ» ليست حالاً واحدةً بل حالان**: مبنيٌّ **عند من يراه**.
    """
    if status is not ServiceTileStatus.ACTIVE:
        return
    if not destination:
        raise InvalidInput("خدمةٌ فعّالةٌ بلا مقصد — اختر شاشةً أو اجعلها «قريباً»")
    roles = SERVICE_DESTINATIONS.get(destination)
    if roles is None:
        raise InvalidInput(
            f"المقصد «{destination}» غير مبنيٍّ في التطبيق — "
            "والإشعالُ عليه يَعِد بشاشةٍ لا وجودَ لها"
        )
    # **ويُسأل عن كلِّ من يراها**: `by_country` تعني الاثنين، فيلزم أن يكون
    # المسارُ مبنيّاً في التطبيقين معاً
    seen = [
        role
        for role in (UserRole.RIDER, UserRole.DRIVER)
        if _audience_matches(audience, role)
    ]
    missing = [role for role in seen if role not in roles]
    if missing:
        who = "الكبتن" if UserRole.DRIVER in missing else "الراكب"
        raise InvalidInput(
            f"المقصد «{destination}» ليس مبنيّاً في تطبيق {who} — "
            "وبلاطةٌ تُشعَل لمن لا شاشةَ له تقع على صفحةٍ مفقودة"
        )


def require_banner_link(kind: BannerLinkKind, link: str | None) -> None:
    """**ولا تُعرض لافتةٌ مقصدُها غير مبنيّ** (قرارُ المالك)."""
    if kind is BannerLinkKind.NONE:
        return
    if not link:
        raise InvalidInput("اللافتةُ تفتح شيئاً ولم يُكتب عنوانُه")
    if kind is BannerLinkKind.INTERNAL and link not in SERVICE_DESTINATIONS:
        raise InvalidInput(
            f"المقصد «{link}» غير مبنيٍّ في التطبيق — "
            "ولافتةٌ تفتح شاشةً لا وجودَ لها أسوأُ من لافتةٍ لا تُنقر"
        )


# ─────────────────────────────────────────────────────────── بلاطاتُ الخدمات


async def tiles_for(
    session: AsyncSession, *, country: CountryCode, role: UserRole
) -> list[ServiceTile]:
    """**ما يراه صاحبُ هذا الدور في سوقه** — والمخفيّةُ لا تُرسل أصلاً.

    **و«قريباً» تُرسل**: هي خبرٌ مقصودٌ يُقرأ ولا يُنقر — والتطبيقُ يعرف
    ذلك من `status` فلا يفتح لها باباً.
    """
    rows = await session.scalars(
        select(ServiceTile)
        .where(
            ServiceTile.country_code == country,
            ServiceTile.status != ServiceTileStatus.HIDDEN,
        )
        .order_by(ServiceTile.sort_order, ServiceTile.created_at)
    )
    return [tile for tile in rows if _audience_matches(tile.audience, role)]


async def get_tile(session: AsyncSession, tile_id: uuid.UUID) -> ServiceTile:
    tile = await session.get(ServiceTile, tile_id)
    if tile is None:
        raise NotFound("البلاطة غير موجودة")
    return tile


async def list_tiles(
    session: AsyncSession, *, country: CountryCode | None = None
) -> list[ServiceTile]:
    """كلُّها للوحة — **بما فيها المخفيّة**، فالمشرفُ يرى ما أخفاه."""
    query = select(ServiceTile).order_by(
        ServiceTile.country_code, ServiceTile.sort_order
    )
    if country is not None:
        query = query.where(ServiceTile.country_code == country)
    return list(await session.scalars(query))


# ─────────────────────────────────────────────────────────────── اللافتات


async def banners_for(
    session: AsyncSession, *, country: CountryCode, role: UserRole
) -> list[PromoBanner]:
    """**الحيّةُ الآن في هذا السوق لهذا الدور** — والنافذةُ تُقاس هنا.

    **ولا تُقاس في التطبيق**: ساعةُ الجهاز يملكها صاحبُه، **ولافتةٌ انتهت
    تبقى ظاهرةً لمن أخّر ساعته**. والخلفيةُ هي الساعة.
    """
    now = _now()
    rows = await session.scalars(
        select(PromoBanner)
        .where(
            PromoBanner.country_code == country,
            PromoBanner.is_active.is_(True),
            PromoBanner.starts_at <= now,
            PromoBanner.ends_at > now,
        )
        .order_by(PromoBanner.sort_order, PromoBanner.starts_at)
    )
    return [
        row
        for row in rows
        if _audience_matches(row.audience, role) and banner_is_ready(row)
    ]


#: العنوانُ الذي تكتبه اللوحةُ عند «لافتة جديدة» — **مصدرُه واحد**
#: (`admin-panel/src/components/Storefront.tsx`)، ويُقرأ هنا لأن الخلفيةَ
#: هي التي تقرّر ما يبلغ الناس.
DEFAULT_BANNER_TITLE = "لافتة جديدة"


def banner_is_ready(row: PromoBanner) -> bool:
    """**أفيها ما يُقرأ؟** — وإلا فلا تبلغ أحداً.

    ## العلّةُ مقيسةٌ لا مفترضة (٢٠٢٦-٠٩-٠٩)

    على رئيسية الراكب بطاقةٌ فيها **جرسٌ وكلمة «لافتة جديدة» ولا شيءَ غيرها**
    — صفٌّ أُنشئ من اللوحة ولم يُملأ، **ومشتعلٌ**. فرآها الناسُ **ورآها
    المتجرُ في لقطةِ الشاشة المنشورة**.

    **وبطاقةٌ فارغةٌ ليست نقصَ تصميم**: هي **وعدٌ بمحتوىً لا وجودَ له** —
    من يراها يظنّ عرضاً لم يُحمَّل، فيضغط، فلا شيء.

    ## ولمَ تُصفّى هنا لا تُحذف

    **الصفُّ يبقى** (قرارُ المالك): حذفُه يمحو شاهداً، **وتحريرُه من اللوحة
    بيد المالك وحدَه**. فالحارسُ يمنع **العرض**، والصفُّ ينتظر نصَّه.

    **وتُقاس في الخلفية لا في التطبيق**: ثلاثةُ تطبيقاتٍ ترسم اللافتات،
    **وشرطٌ في واحدٍ منها يترك بابين مفتوحين** — وهي «بابان يقولان أمرين».

    **والشرطُ نصٌّ يُقرأ**: عنوانٌ غيرُ فارغٍ **وغيرُ العنوان الافتراضيّ**،
    أو جسمٌ غيرُ فارغ. فلافتةٌ عنوانُها «لافتة جديدة» وجسمُها فارغ **لم
    يكتبها أحدٌ بعد**.
    """
    title = (row.title or "").strip()
    body = (row.body or "").strip()
    if title and title != DEFAULT_BANNER_TITLE:
        return True
    return bool(body)


async def get_banner(session: AsyncSession, banner_id: uuid.UUID) -> PromoBanner:
    banner = await session.get(PromoBanner, banner_id)
    if banner is None:
        raise NotFound("اللافتة غير موجودة")
    return banner


async def list_banners(
    session: AsyncSession, *, country: CountryCode | None = None
) -> list[PromoBanner]:
    """كلُّها للوحة — **ومنها المنتهيةُ**، فالمشرفُ يرى ما مضى ويعيد استعماله."""
    query = select(PromoBanner).order_by(
        PromoBanner.country_code, PromoBanner.starts_at.desc()
    )
    if country is not None:
        query = query.where(PromoBanner.country_code == country)
    return list(await session.scalars(query))


def is_new(tile: ServiceTile, *, today: date | None = None) -> bool:
    """**شارةُ «جديد» تُحسب هنا لا في كلِّ قارئ**."""
    return tile.is_new_on(today or _now().date())


# ═══════════════════════════════ العرضُ والحذف ═══════════════════════════════


def stamp_if_shown(row, *, now: datetime | None = None) -> None:
    """**يختم أوّلَ ظهورٍ لأحد** — ولا يُعاد ختمُه.

    **والختمُ فعلُ الباب لا الشاشة**: من عرضها هو الخادمُ حين أجاب
    `GET /storefront`، **لكنّ الختمَ هناك يكتب في كلِّ قراءة** — فيُختم عند
    **الإشعال** لا عند القراءة: **الإشعالُ هو القرار**، والقراءةُ أثرُه.

    ## واللافتةُ تُختم بنافذتها — **وميلُ الخطأ مقصود**

    **السؤالُ لحظةَ الإشعال ليس «أتُعرض الآن؟» بل «أستُعرض بعدُ؟»**: لافتةٌ
    تُشعَل قبل نافذتها **تُعرض حتماً حين تفتح**، ولو لم يُلمس صفُّها ثانيةً.
    **فالختمُ على «حيّةٌ الآن» وحدَها يترك ثقباً**: تُشعَل اليومَ لنافذةِ
    الأسبوع القادم فلا تُختم، **ثم تُعرض على الناس وهي ما تزال تُقرأ مسوّدةً
    تُحذف** — وذلك بعينه محوُ الشاهد الذي بُني له العمود.

    **فالشرطُ: مشتعلةٌ ونافذتُها لم تنتهِ.** وأثرُ الخطأ في الاتجاهين غيرُ
    متساوٍ: **ختمٌ زائدٌ يمنع حذفاً** والإخفاءُ قائمٌ بديلاً، **وختمٌ ناقصٌ
    يأذن بمحو صفٍّ رآه الناس** — الأولُ يُراجَع والثاني لا يُستدرك.
    """
    if row.first_shown_at is not None:
        return
    moment = now or _now()
    if isinstance(row, ServiceTile):
        live = row.status is ServiceTileStatus.ACTIVE
    else:
        # **ولا يُسأل عن `starts_at`** — مشتعلةٌ قبل نافذتها ستُعرض حين تفتح
        live = bool(row.is_active) and row.ends_at > moment
    if live:
        row.first_shown_at = moment


def require_draft(row) -> None:
    """**الحذفُ للمسوّدة وحدَها** (قرارُ المالك 2026-08-31).

    **وما عُرض مرّةً يُخفى ولا يُحذف**: حذفُه **يمحو شاهداً على ما رآه
    الناس** — ومن يقرأ بعد شهرٍ «لمَ ارتفعت الضغطاتُ ذلك الأسبوع» يجد فراغاً.
    **ولافتةٌ أُخفيت خيرٌ من صفٍّ ذهب.**
    """
    if row.first_shown_at is not None:
        raise InvalidInput(
            "هذا الصفُّ عُرض على الناس ولا يُحذف — أخفِه بدل ذلك، "
            "فحذفُه يمحو شاهداً على ما عُرض"
        )
