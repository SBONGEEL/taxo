"""بابُ الشاشة الرئيسة — **نداءٌ واحدٌ يعطي البلاطاتِ واللافتاتِ والعرض**.

**ولمَ بابٌ واحدٌ لا بابان**: ندءان يعنيان شاشةً تُرسم على مرحلتين —
البلاطاتُ تظهر ثم تقفز اللافتةُ فوقها، **وهو ارتجافٌ يراه المستخدمُ عطباً**.

**والدورُ يُشتقّ من سياق الطلب لا من عمود**: من يحمل الدورين يرى ما يخصّ
التطبيقَ الذي هو فيه — **وهي قاعدةُ «سياقُ الفعل لا دورُ الفاعل»** المسجَّلة
في `ARCHITECTURE.md`.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.core import storage
from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import NotFound
from app.models.driver import Driver
from app.models.enums import UserRole
from app.schemas.storefront import (
    PromoBannerOut,
    ServiceTileOut,
    StorefrontOfferOut,
    StorefrontOut,
)
from app.services import offers as offers_service, storefront

router = APIRouter(prefix="/storefront", tags=["storefront"])


async def _offer_card(
    session, *, user, surface: UserRole
) -> StorefrontOfferOut | None:
    """عرضُ اشتراكِ هذا الكبتن للصندوق — **أو `None`، وهي الحالُ الغالبة**.

    **ولا يُسأل عنه للراكب أصلاً**: الاشتراكُ للكبتن وحدَه، **واستعلامٌ يُطلق
    لكلِّ راكبٍ يفتح رئيسيّته** يقرأ الخططَ والعروضَ ليجيب «لا» دائماً.

    **ومن حسابُه ليس كبتناً يمرّ بلا خطأ**: `surface=driver` تأتي من التطبيق
    لا من الحساب — **وحاملُ الدورين يفتح تطبيقَ الكبتن قبل أن يُعتمد صفُّه**،
    فخطأٌ هنا يُسقط الرئيسيّةَ كلَّها على من ينتظر الاعتماد.

    **والمالُ محسوبٌ هنا لا في الشاشة** (§14): الشاشةُ تعرض رقمين ولا تطرح.
    """
    if surface is not UserRole.DRIVER:
        return None
    driver = await session.scalar(select(Driver).where(Driver.user_id == user.id))
    if driver is None:
        return None
    best = await offers_service.best_for_driver(
        session, driver=driver, country=user.country_code
    )
    if best is None:
        return None
    after = best.plan.price - best.amount
    return StorefrontOfferOut(
        name=best.offer.name,
        plan_name=best.plan.name,
        price=best.plan.price,
        price_after=after,
        currency=best.plan.currency,
        # **«مجاناً» كلمةٌ لا رقمٌ صفر** — و«0.000» تُقرأ عطباً لا هديّة
        free=after == 0,
    )


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
        offer=await _offer_card(session, user=user, surface=surface),
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


@router.get("/banners/{banner_id}/image")
async def serve_banner_image(
    banner_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> FileResponse:
    """**صورةُ اللافتة — بايتاتٌ أو ٤٠٤**، ولا حقلَ يقول «لها صورة».

    **والطلبُ نفسُه هو الجواب** — كما في `DriverAvatar`: حقلٌ ثانٍ يقول «لها
    صورة» **بيتٌ ثانٍ للحقيقة** يفترق عن الملفّ أوّلَ رفعٍ أو نزع.

    **ولا تُخدَم من مُثبَّتٍ ساكن**: كلُّ ملفٍّ في هذا المشروع يمرّ ببابٍ يسأل
    سؤالَه أوّلاً — وسؤالُ هذا الباب **سوقُ صاحبِ الحساب**.

    **ولمَ السوق شرطٌ وليست الصورةُ سرّاً**: سوقٌ يُبنى كاملاً **وهو مخفيّ**
    (`country_visible`)، **ولافتتُه تُعلن خطّةَ إطلاقٍ لم تُعلن بعد** — فبابٌ
    يخدمها لكلِّ من يحمل رمزَها يفتح ما أغلقه المفتاح.
    """
    banner = await storefront.get_banner(session, banner_id)
    if banner.country_code != user.country_code or not banner.image_path:
        raise NotFound("لا صورةَ لهذه اللافتة")
    return FileResponse(
        storage.resolve(banner.image_path),
        headers={
            # **`nosniff` و`no-store`** — كما يجيب بابُ المستندات، ولسببٍ
            # ثانٍ هنا: الصورةُ تُستبدل تحت العنوان نفسِه، **فذاكرةٌ وسيطةٌ
            # تعرض لافتةَ أمسٍ بعد أن بدّلها المشرف**
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )
