"""بابُ الكبتن إلى كراجه ومتجره (2026-08-22).

**والمِلكيّةُ لا تُكتب إلا من `services/vehicle_skins.py`** — لا من راوتر
ولا من مهمّةٍ دورية: بابان يكتبان مِلكيّةً يختلفان في شرطٍ واحدٍ يوماً ما،
وهو الشكلُ الثامن.

**والمفتاحُ يحرس المتجرَ والكراجَ لا الرسمَ** (قرارُ المالك): إطفاءُ
`vehicle_skins_enabled` يغلق الشراءَ والتبديل، **وتبقى مركبةُ من يملك واحدةً
مرسومةً على الخريطة وفي بطاقته** — فمن دفع ثمناً لا يفقد ما اشتراه بقرارِ
تشغيل، وخريطةٌ تُفرِّغ سياراتها عند إطفاء مفتاحٍ زينةٍ عطبٌ لا إطفاء.

**والمطفأُ يردّ خطأً مسمّى لا قائمةً فارغة**: قائمةٌ فارغةٌ تُقرأ «لا مركبات
بعد» فيُنتظر ما لن يأتي، والخطأُ المسمّى يقول ما وقع (§17).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from typing import Annotated

from fastapi import APIRouter, Query, status
from fastapi.responses import FileResponse

from app.core import storage
from app.core.deps import CurrentDriver, CurrentUser, DbSession
from app.core.exceptions import FeatureDisabled, NotFound
from app.models.enums import FeatureKey
from app.models.user import User
from app.models.vehicle_skin import VehicleSkin
from app.schemas.driver import ART_MAP, ART_STORE
from app.schemas.vehicle_skin import ActivateSkinIn, BuySkinOut, GarageOut, StoreOut
from app.services import settings_service, subscriptions, vehicle_skins

router = APIRouter(prefix="/vehicle-skins", tags=["vehicle-skins"])

#: مجلَّدُ الرسمات المولَّدة داخل الصورة — يملؤه `services/skin_artwork.py`
ASSET_DIR = "skins"
#: اصطلاحُ اسم الملفّ المولَّد: `{asset_key}-{kind}.svg`
ASSET_SUFFIX = ".svg"
_ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets" / ASSET_DIR


async def _require_enabled(session: DbSession, user: User) -> None:
    if not await settings_service.is_feature_enabled(
        session, user.country_code, FeatureKey.VEHICLE_SKINS_ENABLED
    ):
        raise FeatureDisabled("متجرُ المركبات غير مفعّلٍ في سوقك")


@router.get("/store", response_model=StoreOut)
async def store(
    driver: CurrentDriver,
    user: CurrentUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=120)] = 48,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> StoreOut:
    """المتجرُ ورصيدُ الكبتن ومستواه — **بنداءٍ واحد، وصفحةً صفحة**.

    **والحدُّ افتراضيٌّ لا اختياريّ**: الكتالوجُ ثلاثُ مئةٍ وزيادة، وطلبٌ بلا
    حدٍّ يرسل ٣٧٣ بطاقةً إلى شاشةِ هاتف — ٣٧٣ صورةً وعقدةَ DOM لكلِّ واحدة.
    فمن نسي `limit` يأخذ صفحةً لا الكتالوجَ كلَّه.
    """
    await _require_enabled(session, user)
    return await vehicle_skins.store_for(
        session, driver, user, limit=limit, offset=offset
    )


@router.get("/garage", response_model=GarageOut)
async def garage(
    driver: CurrentDriver, user: CurrentUser, session: DbSession
) -> GarageOut:
    """كراجُه ومعه الورقةُ الاحتفاليةُ إن كانت له مركبةٌ لم تُعرض بعد."""
    await _require_enabled(session, user)
    current = await subscriptions.current_subscription(session, driver.id)
    return await vehicle_skins.garage_for(
        session, driver, user, has_subscription=current is not None
    )


@router.post("/{skin_id}/buy", response_model=BuySkinOut)
async def buy(
    skin_id: uuid.UUID,
    driver: CurrentDriver,
    user: CurrentUser,
    session: DbSession,
) -> BuySkinOut:
    """شراءُ مركبةٍ من رصيد محفظة الكبتن — **قيدٌ في الدفتر لا رقمٌ يُنقَص**."""
    await _require_enabled(session, user)
    out = await vehicle_skins.buy(session, driver=driver, user=user, skin_id=skin_id)
    await session.commit()
    return out


@router.put("/active", status_code=status.HTTP_204_NO_CONTENT)
async def activate(
    payload: ActivateSkinIn,
    driver: CurrentDriver,
    user: CurrentUser,
    session: DbSession,
) -> None:
    """تبديلُ المركبة النشطة — **للحساب لا للسيارة**."""
    await _require_enabled(session, user)
    await vehicle_skins.activate(session, driver=driver, skin_id=payload.skin_id)
    await session.commit()


@router.post("/{skin_id}/seen", status_code=status.HTTP_204_NO_CONTENT)
async def mark_seen(
    skin_id: uuid.UUID,
    driver: CurrentDriver,
    user: CurrentUser,
    session: DbSession,
) -> None:
    """ختمُ الورقة الاحتفالية — تُعرض مرةً ثم لا تعود."""
    await _require_enabled(session, user)
    await vehicle_skins.mark_seen(session, driver=driver, skin_id=skin_id)
    await session.commit()


# ------------------------------------------------------------------- الرسمة


@router.get("/{skin_id}/art/{kind}")
async def art(skin_id: uuid.UUID, kind: str, session: DbSession) -> FileResponse:
    """رسمةُ مركبةٍ — **بابٌ مفتوحٌ بلا جلسة**، وهذا مقصود.

    خريطةُ الراكب ترسم سياراتِ من حوله قبل أن يطلب، **والراكبُ ليس كبتناً**
    — فحارسُ الجلسة هنا يجعل الخريطةَ لا ترسم شيئاً. والرسمةُ **صفٌّ في
    كتالوجٍ عامّ** يراه كلُّ من فتح المتجر، لا وثيقةَ هوية: فلا شيءَ يُحمى
    بإغلاقها، ويُخسر بها كلُّ رسمٍ.

    **ولا يُطفئه مفتاحُ الميزة**: المركبةُ النشطةُ تبقى مرسومةً بعد الإطفاء
    (ترويسةُ الملف)، ورابطٌ ميّتٌ يفرّغ الخريطةَ من سياراتها.

    **والمصدران بابٌ واحد**: مولَّدةٌ في الصورة (`asset_key`) أو مرفوعةٌ إلى
    التخزين (`store_image_path`/`map_image_path`) — والعميلُ لا يعرف أيَّهما،
    فاستبدالُ إحداهما بالأخرى غداً لا يغيّر رابطاً في يد أحد.
    """
    if kind not in (ART_STORE, ART_MAP):
        raise NotFound("لا رسمةَ بهذا الاسم")
    skin = await session.get(VehicleSkin, skin_id)
    if skin is None:
        raise NotFound("هذه المركبة غير موجودة")

    uploaded = skin.store_image_path if kind == ART_STORE else skin.map_image_path
    if uploaded:
        path = storage.resolve(uploaded)
        media_type = "image/png" if path.suffix == ".png" else "image/jpeg"
    elif skin.asset_key:
        path = _ASSET_ROOT / f"{skin.asset_key}-{kind}{ASSET_SUFFIX}"
        if not path.is_file():
            raise NotFound("رسمةُ هذه المركبة غير موجودة")
        media_type = "image/svg+xml"
    else:
        raise NotFound("رسمةُ هذه المركبة غير موجودة")

    return FileResponse(
        path,
        media_type=media_type,
        headers={
            # **رسمةٌ لا تتغيّر تحت مفتاحها** — والمفتاحُ مُعرّفُ المركبة،
            # فاستبدالُ الرسمة يحتاج صفّاً جديداً أو انقضاءَ اليوم
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        },
    )
