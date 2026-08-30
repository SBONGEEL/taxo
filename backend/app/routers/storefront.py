"""بابُ الشاشة الرئيسة — **نداءٌ واحدٌ يعطي البلاطاتِ واللافتات**.

**ولمَ بابٌ واحدٌ لا بابان**: ندءان يعنيان شاشةً تُرسم على مرحلتين —
البلاطاتُ تظهر ثم تقفز اللافتةُ فوقها، **وهو ارتجافٌ يراه المستخدمُ عطباً**.

**والدورُ يُشتقّ من سياق الطلب لا من عمود**: من يحمل الدورين يرى ما يخصّ
التطبيقَ الذي هو فيه — **وهي قاعدةُ «سياقُ الفعل لا دورُ الفاعل»** المسجَّلة
في `ARCHITECTURE.md`.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.models.enums import UserRole
from app.schemas.storefront import PromoBannerOut, ServiceTileOut, StorefrontOut
from app.services import storefront

router = APIRouter(prefix="/storefront", tags=["storefront"])


@router.get("", response_model=StorefrontOut)
async def my_storefront(
    user: CurrentUser,
    session: DbSession,
    surface: UserRole = Query(
        default=UserRole.RIDER,
        description="التطبيقُ الذي يسأل — والدورُ من السياق لا من الحساب",
    ),
) -> StorefrontOut:
    """بلاطاتُ سوقه ولافتاتُه الحيّة — **مصفّاةً في الخلفية**.

    **ولا تُصفّى في التطبيق**: ثلاثةُ تطبيقاتٍ تسأل السؤالَ نفسَه، **وثلاثةُ
    حساباتٍ له تفترق أوّلَ تعديل**. والنافذةُ خاصّةً: **ساعةُ الجهاز يملكها
    صاحبُه**، فلافتةٌ انتهت تبقى ظاهرةً لمن أخّر ساعتَه.

    **وسوقٌ لا بلاطاتِ فيه يعيد قائمتين فارغتين** — لا خطأً: الشاشةُ تعمل
    بلا بلاطاتٍ ولا لافتات، **وخطأٌ هنا يُسقط الرئيسيةَ كلَّها**.
    """
    if surface not in (UserRole.RIDER, UserRole.DRIVER):
        surface = UserRole.RIDER

    tiles = await storefront.tiles_for(
        session, country=user.country_code, role=surface
    )
    banners = await storefront.banners_for(
        session, country=user.country_code, role=surface
    )
    return StorefrontOut(
        tiles=[
            ServiceTileOut(
                id=tile.id,
                key=tile.key,
                title=tile.title,
                subtitle=tile.subtitle,
                icon=tile.icon,
                status=tile.status,
                destination=tile.destination,
                is_new=storefront.is_new(tile),
            )
            for tile in tiles
        ],
        banners=[
            PromoBannerOut(
                id=banner.id,
                title=banner.title,
                body=banner.body,
                icon=banner.icon,
                link_kind=banner.link_kind,
                link=banner.link,
            )
            for banner in banners
        ],
    )
