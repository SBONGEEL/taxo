"""إدارةُ كتالوج المركبات في اللوحة (2026-08-22) — `admin` حصراً.

**ولا `StaffUser`**: سعرُ مركبةٍ وكميّتُها ونافذةُ موسمها **قرارٌ ماليّ** لا
إجراءُ دعمٍ فنيّ — كصفحة العقود ورموزِ الخصم وعروضِ الاشتراكات بالضبط
(القسم ١٣/٨).

**وكلُّ بابٍ هنا له زرّ** — `check:doors` يحرسه، ولا استثناءَ مكتوبٌ لواحدٍ منها.

---

## أين تسكن منطقةُ الكتالوج — **قرارٌ مؤقَّتٌ مكتوبٌ لا صامت**

قاعدةُ المشروع أن الراوترَ غلافٌ رقيقٌ والمنطقُ في `services/`. **ومنطقُ
الكتالوج هنا في الراوتر مؤقتاً**، لأن `services/vehicle_skins.py` يكتبه وكيلٌ
آخر في الجلسة نفسِها، **والعقدُ الذي سُلِّم إليَّ سمّى أبوابَ الكبتن وحدَها**
(`store_for` · `garage_for` · `buy` · `activate` · `publishable_skin_for`)
ولم يسمِّ أبوابَ الإدارة. **وكتابةُ نسخةٍ ثانيةٍ من الخدمة هي بعينها ما نُهيت
عنه**، فالخيارُ بين تأخيرِ الشاشة كلِّها وبين بيتٍ مؤقَّتٍ **مُسمّى**.

**وموضعُها النهائيُّ `services/vehicle_skins.py`** بأسماء `admin_list` ·
`admin_create` · `admin_update` · `admin_stats` · `attach_artwork`. ونقلُها
حركةُ دوالَّ لا إعادةُ كتابة.

**وخطرُ ذلك يُسمّى قبل أن يقع**: `owners_count` **يُحسب هنا وسيُحسب هناك**
لمتجر الكبتن — **وهو الشكلُ الثامن حرفياً**: بابان ينشران الرقمَ نفسَه، كلٌّ
منهما صادقٌ وحدَه، ويفترقان أوّلَ شرطٍ يُضاف إلى أحدهما (هديةٌ إداريةٌ لا
تُعدّ، أو صفٌّ مسترجَع). **فالعلاجُ بانٍ واحدٌ لا إصلاحُ حقل**، ومكانُه
الخدمة.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.deps import AdminUser, DbSession
from app.core.exceptions import InvalidInput, NotFound
from app.models.enums import AuditAction, CountryCode
from app.models.vehicle_skin import (
    DriverVehicleSkin,
    VehicleSkin,
    VehicleSkinPrice,
)
from app.schemas.vehicle_skin import (
    AdminSkinOut,
    SkinCreateIn,
    SkinPriceIn,
    SkinStatsOut,
    SkinUpdateIn,
)
from app.services import audit, skin_artwork

router = APIRouter(prefix="/admin/vehicle-skins", tags=["admin"])


# ─────────────────────────────────────────────── قراءةُ الكتالوج ومجاميعُه


def _owned_counts() -> Select:
    """عددُ المالكين وعددُ **المشترين** والإيرادُ بعملته — **مجموعةً في القاعدة**.

    §14: اللوحةُ لا تجمع صفوفاً. وجمعُ صفحةٍ مقصوصةٍ في المتصفح يُخرج رقماً
    عنوانُه «الإيرادُ الكلي» وقيمتُه «إيرادُ ما ظهر»، **والفرقُ لا يُرى**.
    """
    return (
        select(
            DriverVehicleSkin.skin_id.label("skin_id"),
            func.count().label("owners"),
            func.count(DriverVehicleSkin.price_paid).label("sold"),
            DriverVehicleSkin.currency.label("currency"),
            func.coalesce(func.sum(DriverVehicleSkin.price_paid), 0).label("revenue"),
        )
        .group_by(DriverVehicleSkin.skin_id, DriverVehicleSkin.currency)
        .subquery()
    )


async def _rows(session: AsyncSession) -> list[AdminSkinOut]:
    """الكتالوجُ **بحاله لا مصفّىً بسوق** — والسعرُ لكلِّ سوقٍ في الصفّ نفسِه.

    وترتيبُه بالندرة ثم بالاسم: **عقدٌ لا ذوق**، فشاشتان ترتّبانه اختلافاً
    تعرضان على مشرفَين كتالوجين مختلفين لِما هو واحد.
    """
    skins = (
        await session.execute(
            select(VehicleSkin).order_by(VehicleSkin.rarity, VehicleSkin.name)
        )
    ).scalars().all()

    # **الأسعارُ بنداءٍ واحدٍ لا نداءٍ لكلِّ صفّ**: النموذجُ بلا علاقةٍ مُعلَنة
    # (وهو ملفٌّ لا أملكه)، **والحلقةُ التي تسأل عن كلِّ مركبةٍ على حدة** هي
    # `N+1` بعينها — عشرون مركبةً تصير إحدى وعشرين رحلةً إلى القاعدة
    price_rows = (await session.execute(select(VehicleSkinPrice))).scalars().all()
    by_skin: dict[uuid.UUID, list[VehicleSkinPrice]] = {}
    for price in price_rows:
        by_skin.setdefault(price.skin_id, []).append(price)

    counts = _owned_counts()
    aggregates = (await session.execute(select(counts))).all()

    owners: dict[uuid.UUID, int] = {}
    sold: dict[uuid.UUID, int] = {}
    revenue: dict[uuid.UUID, dict[str, Decimal]] = {}
    for row in aggregates:
        owners[row.skin_id] = owners.get(row.skin_id, 0) + row.owners
        sold[row.skin_id] = sold.get(row.skin_id, 0) + row.sold
        if row.currency and row.revenue:
            bucket = revenue.setdefault(row.skin_id, {})
            bucket[row.currency] = bucket.get(row.currency, Decimal("0")) + row.revenue

    out: list[AdminSkinOut] = []
    for skin in skins:
        out.append(
            AdminSkinOut(
                **{
                    column: getattr(skin, column)
                    for column in (
                        "id", "name", "rarity", "map_scale_percent", "map_rotates",
                        "visible_before_accept", "max_supply", "level_required",
                        "valid_from", "valid_until", "is_gift", "is_public_default",
                        "is_feminine", "feminine_drivers_only", "is_active",
                    )
                },
                store_image_url=_artwork_url(skin, "store"),
                map_image_url=_artwork_url(skin, "map"),
                prices=[
                    SkinPriceIn(country_code=price.country_code, price=price.price)
                    for price in sorted(
                        by_skin.get(skin.id, []),
                        key=lambda p: p.country_code.value,
                    )
                ],
                owners_count=owners.get(skin.id, 0),
                sold_count=sold.get(skin.id, 0),
                # **المال مُكمَّمٌ ولو كان صفراً** — الشكلُ السابع: قيمةٌ تُكوَّن
                # في بايثون تُسلسَل `"0"` لا `"0.000"`، فيقرأ المشرفُ صفراً
                # عارياً في عمودٍ كلُّه ثلاثُ خانات
                revenue={
                    code: amount.quantize(Decimal("0.001"))
                    for code, amount in sorted(revenue.get(skin.id, {}).items())
                },
            )
        )
    return out


def _artwork_url(skin: VehicleSkin, slot: skin_artwork.Slot) -> str:
    """**عنوانٌ نسبيٌّ يبنيه التطبيقُ على أصله** — كما يقول العقد.

    و`""` حين لا رسمةَ بعد: **مركبةٌ أُنشئت ولم تُرفع رسمتُها حالٌ حقيقية**
    (الإنشاءُ ثم الرفعُ خطوتان)، والشاشةُ ترسم مكانَها موضعاً فارغاً يقول ذلك.
    """
    if not skin.asset_key and not (
        skin.store_image_path if slot == "store" else skin.map_image_path
    ):
        return ""
    return f"/admin/vehicle-skins/{skin.id}/artwork/{slot}"


async def _get(session: AsyncSession, skin_id: uuid.UUID) -> VehicleSkin:
    skin = await session.get(VehicleSkin, skin_id)
    if skin is None:
        raise NotFound("المركبة غير موجودة")
    return skin


async def _write_prices(
    session: AsyncSession, skin: VehicleSkin, prices: list[SkinPriceIn]
) -> None:
    """**استبدالٌ لا إضافة**: القائمةُ المرسَلةُ هي الأسعارُ كلُّها.

    و**العملةُ لا تُخزَّن هنا**: تُشتقّ من الدولة (`core/currency`)، فسعرٌ
    يحمل عملةً مخالفةً لسوقه شيءٌ لا يمكن أن يُكتب أصلاً.
    """
    # **حدُّ الازدواج قبل الكتابة**: سوقٌ مرتين في الطلب الواحد يكسر المفتاحَ
    # الأساسيَّ بخطأِ قاعدةٍ خامٍ بالإنجليزية بدل رسالةٍ عربيةٍ تقول ما يُصلَح
    seen = {price.country_code for price in prices}
    if len(seen) != len(prices):
        raise InvalidInput("سوقٌ مكرَّرٌ في قائمة الأسعار")
    await session.execute(
        delete(VehicleSkinPrice).where(VehicleSkinPrice.skin_id == skin.id)
    )
    await session.flush()
    for price in prices:
        # يُنادى ليُرفع خطأٌ مبكّرٌ على سوقٍ بلا عملةٍ معرَّفة
        currency_for_country(price.country_code)
        session.add(
            VehicleSkinPrice(
                skin_id=skin.id,
                country_code=price.country_code,
                price=price.price,
            )
        )
    await session.flush()


# ─────────────────────────────────────────────────────────── الأبواب


@router.get("", response_model=list[AdminSkinOut])
async def list_skins(_: AdminUser, session: DbSession) -> list[AdminSkinOut]:
    """الكتالوجُ كلُّه ومعه عدّادُ الاقتناء والمبيعاتُ والإيراد."""
    return await _rows(session)


@router.get("/assets", response_model=list[dict[str, str]])
async def list_bundled_assets(_: AdminUser) -> list[dict[str, str]]:
    """الرسوماتُ المشحونةُ مع الخلفية — **منتقٍ بدل رفعٍ يدويّ**.

    و**تُقرأ من القرص** لا من قائمةٍ في الكود: قائمةٌ مكتوبةٌ تفترق عن
    المجلَّد أوّلَ رسمةٍ تُضاف، فيعرض المنتقي مركبةً بلا ملفّ.
    """
    return skin_artwork.bundled_assets()


@router.get("/stats", response_model=SkinStatsOut)
async def skin_stats(_: AdminUser, session: DbSession) -> SkinStatsOut:
    """الأكثرُ مبيعاً والإيرادُ الكلي — **مجموعَين في القاعدة** (§14)."""
    rows = await _rows(session)
    revenue: dict[str, Decimal] = {}
    for row in rows:
        for code, amount in row.revenue.items():
            revenue[code] = revenue.get(code, Decimal("0")) + amount
    return SkinStatsOut(
        # **«الأكثرُ مبيعاً» بيعٌ لا اقتناء**: الهديةُ تُقتنى ولا تُباع، وخلطُهما
        # يضع مركبةً لم تُبَع قطُّ على رأس قائمةِ المبيعات
        top_selling=sorted(rows, key=lambda row: row.sold_count, reverse=True)[:5],
        revenue_by_currency={
            code: amount.quantize(Decimal("0.001"))
            for code, amount in sorted(revenue.items())
        },
        total_owned=sum(row.owners_count for row in rows),
    )


@router.post("", response_model=AdminSkinOut, status_code=status.HTTP_201_CREATED)
async def create_skin(
    payload: SkinCreateIn, admin: AdminUser, session: DbSession
) -> AdminSkinOut:
    """مركبةٌ جديدة — **بلا رسمةٍ بعد**، تُرفع في البابِ الذي يليه.

    **والخطوتان مقصودتان**: العقدُ المجمَّد لا يحمل رسمةً في جسم الإنشاء،
    والرفعُ `multipart` لا JSON. **والشاشةُ تعاين الرسمةَ قبل الحفظ** عبر باب
    المعاينة أدناه، فلا يُحفظ شيءٌ على غير ما رآه المشرف.
    """
    data = payload.model_dump()
    prices = [SkinPriceIn(**row) for row in data.pop("prices", [])]
    skin = VehicleSkin(**data)
    session.add(skin)
    await session.flush()
    await _write_prices(session, skin, prices)

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="vehicle_skin",
        entity_id=skin.id,
        details={"fields": sorted(payload.model_dump().keys())},
    )
    await session.commit()
    await session.refresh(skin)
    rows = await _rows(session)
    return next(row for row in rows if row.id == skin.id)


@router.patch("/{skin_id}", response_model=AdminSkinOut)
async def update_skin(
    skin_id: uuid.UUID,
    payload: SkinUpdateIn,
    admin: AdminUser,
    session: DbSession,
) -> AdminSkinOut:
    """تعديلٌ جزئيّ — **والإطفاءُ تعديلٌ لا حذف**.

    ولا بابَ حذفٍ في هذا الملف إطلاقاً: مركبةٌ اشتراها كباتنُ يمحو حذفُها
    **سببَ ما دفعوه**، والمفتاحُ الأجنبيُّ `RESTRICT` يرفض قبل أن يصل الطلب.
    """
    skin = await _get(session, skin_id)
    data = payload.model_dump(exclude_unset=True)
    prices = data.pop("prices", None)
    for key, value in data.items():
        setattr(skin, key, value)
    if prices is not None:
        await _write_prices(session, skin, [SkinPriceIn(**row) for row in prices])

    await audit.record(
        session,
        actor=admin,
        action=(
            AuditAction.DEACTIVATE
            if data.get("is_active") is False
            else AuditAction.ACTIVATE
            if data.get("is_active") is True
            else AuditAction.UPDATE
        ),
        entity_type="vehicle_skin",
        entity_id=skin.id,
        # **الأسماءُ لا القيم** — قاعدةُ التدقيق في هذا المشروع
        details={"fields": sorted(payload.model_dump(exclude_unset=True).keys())},
    )
    await session.commit()
    rows = await _rows(session)
    return next(row for row in rows if row.id == skin.id)


# ──────────────────────────────────────────────────────────── الرسمة


@router.put("/artwork/preview")
async def preview_artwork(
    _: AdminUser,
    file: Annotated[UploadFile, File(description="صورةٌ أو SVG")],
) -> dict[str, object]:
    """**تجربةٌ جافّةٌ بنفس السلسلة** — تُعالَج الرسمةُ ولا يُكتب شيء.

    **وهذا ما يجعل المعاينةَ صادقة**: معاينةٌ ترسم **الملفَّ الخام** تُري
    المشرفَ حجماً غيرَ الذي سيُرسم — فالهوامشُ الشفافةُ تُقصّ عند الحفظ،
    فتصغر السيارةُ في الشاشة ويكبر ما رآه على الخريطة. فيضبط نسبةَ العرض على
    ما **لن يقع**، وهو الشكلُ الذي يُصلحه هذا الباب لا يخلقه.

    وهي طريقةُ إثبات إصلاحِ قوالب الرسائل نفسُها: **نفسُ السلسلة، بلا إرسال**.

    **ولا صفَّ ولا ملفّ**: لا يحتاج مُعرَّفَ مركبةٍ أصلاً، فيُعاين قبل أن
    تُنشأ.
    """
    import base64

    art = skin_artwork.render(await skin_artwork.read_capped(file))
    prefix = f"data:{art.media_type};base64,"
    return {
        "store_image": prefix + base64.b64encode(art.store).decode(),
        "map_image": prefix + base64.b64encode(art.map).decode(),
        "media_type": art.media_type,
        "source_size": list(art.source_size) if art.source_size else None,
        "trimmed": list(art.trimmed) if art.trimmed else None,
        "store_bytes": len(art.store),
        "map_bytes": len(art.map),
    }


@router.put("/{skin_id}/artwork", response_model=AdminSkinOut)
async def upload_artwork(
    skin_id: uuid.UUID,
    admin: AdminUser,
    session: DbSession,
    file: Annotated[UploadFile, File(description="صورةٌ أو SVG")],
) -> AdminSkinOut:
    """يرفع رسمةً ويربطها بالمركبة — **وينسخ `asset_key` إن كان**.

    `PUT` لا `POST` لأنها **إحلال**: للمركبة رسمةٌ واحدة، فرفعُ ثانيةٍ
    استبدالٌ للأولى لا رسمتان. وهو سببُ `PUT` في رفع المستندات نفسُه.

    **والعمودان لا يجتمعان** (`models/vehicle_skin.py`): مرفوعةٌ **أو**
    مشحونة، فرفعُ رسمةٍ يمحو `asset_key` — وبغيره تحمل المركبةُ مصدرين
    ويقرّر ترتيبُ الشرط في `artwork_response` أيَّهما يُرى.
    """
    skin = await _get(session, skin_id)
    stored = await skin_artwork.ingest(file, folder=str(skin.id))
    superseded = [
        path for path in (skin.store_image_path, skin.map_image_path) if path
    ]
    skin.asset_key = None
    skin.store_image_path = stored.store_path
    skin.map_image_path = stored.map_path

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="vehicle_skin",
        entity_id=skin.id,
        details={"fields": ["store_image_path", "map_image_path"]},
    )
    await session.commit()

    # **بعد الـ commit**: ملفٌّ يتيمٌ نفايةٌ تُنظَّف، وصفٌّ يشير إلى ملفٍ محذوف
    # عطلٌ يراه المستخدم — وهي قاعدةُ `documents.upload` نفسُها
    from app.core import storage

    for path in superseded:
        await storage.delete(path)

    rows = await _rows(session)
    return next(row for row in rows if row.id == skin.id)


@router.put("/{skin_id}/asset/{asset_key}", response_model=AdminSkinOut)
async def attach_bundled_asset(
    skin_id: uuid.UUID,
    asset_key: str,
    admin: AdminUser,
    session: DbSession,
) -> AdminSkinOut:
    """يربط المركبةَ برسمةٍ **مشحونةٍ مع الخلفية** — بلا رفعٍ ولا ملفّ.

    **ولولا هذا البابُ لكانت ستَّ عشرةَ رسمةً في الحزمة لا يصل إليها زرّ** —
    وهو «بابٌ بلا زرّ» مقلوباً، والشكلُ الذي يحرسه `check:doors` أصلاً.
    """
    if not any(row["key"] == asset_key for row in skin_artwork.bundled_assets()):
        raise NotFound("لا رسمةَ بهذا المفتاح")
    skin = await _get(session, skin_id)
    superseded = [
        path for path in (skin.store_image_path, skin.map_image_path) if path
    ]
    skin.asset_key = asset_key
    skin.store_image_path = None
    skin.map_image_path = None

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="vehicle_skin",
        entity_id=skin.id,
        details={"fields": ["asset_key"]},
    )
    await session.commit()

    from app.core import storage

    for path in superseded:
        await storage.delete(path)

    rows = await _rows(session)
    return next(row for row in rows if row.id == skin.id)


@router.get("/{skin_id}/artwork/{slot}")
async def get_artwork(
    skin_id: uuid.UUID, slot: skin_artwork.Slot, _: AdminUser, session: DbSession
) -> FileResponse:
    """رسمةُ المركبة — **بترويسات `skin_artwork` لا بترويساتٍ تُكتب هنا**.

    وبابان يخدمان الشيءَ نفسَه بترويستين هما الشكلُ الثامن، فالسياسةُ في
    بانٍ واحدٍ وهذا الراوترُ ينادي. **وبابُ الكبتن ينادي البانِيَ نفسَه.**
    """
    skin = await _get(session, skin_id)
    return skin_artwork.artwork_response(
        asset_key=skin.asset_key,
        stored_path=(
            skin.store_image_path if slot == "store" else skin.map_image_path
        ),
        slot=slot,
    )

