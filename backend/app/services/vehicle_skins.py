"""مركباتُ الكراج والمتجر — **البابُ الوحيدُ الذي يكتب مِلكيّة** (2026-08-22).

**ولمَ بابٌ واحد**: المِلكيّةُ تُكتب من ثلاثة أحداث — شراءٌ، وهديةُ أوّلِ
اشتراك، ومنحةٌ إدارية — وثلاثةُ كُتّابٍ يختلفون في شرطٍ واحدٍ يوماً ما (الكميّة،
أو المستوى، أو تجميدُ السعر). فالكتابةُ هنا وحدَها، والراوتراتُ تقرّر **من**
يسأل لا **ماذا يُكتب**.

**والكميّةُ محسوبةٌ لا مخزَّنة** (`models/vehicle_skin.py`): «المتبقّي» =
`max_supply` ناقص عددَ المالكين. وعمودُ عدّادٍ يُنقَص يدوياً يفترق عن الحقيقة
أوّلَ منحةٍ إدارية، **وحينها يبيع المتجرُ ما ليس عنده أو يمنع ما عنده**.

**وترتيبُ الأقفال** (`CLAUDE.md`): **صفُّ المركبة ← قفلُ المحفظة الاستشاريّ
آخراً**. والقفلُ يُؤخذ **ثم** يُقرأ العدد — لا العكس: قراءةٌ قبل القفل تجعل
مشترِيَين متزامنين يقرآن العددَ نفسَه فيتجاوزان آخرَ نسخة، وهو درسُ
`cancellation.try_collect` نفسُه («اقفل ثم اقرأ»).

**ولا تُنشر الندرةُ قبل القبول**: `publishable_skin_for` تحت الملف — وهي
الشكلُ الثالثَ عشر مطبَّقاً (امتيازٌ يُرى غيابُه يصير علامةً على صاحبه).
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import currency_for_country
from app.core.exceptions import (
    NotFound,
    SkinAlreadyOwned,
    SkinLevelLocked,
    SkinNotOwned,
    SkinSoldOut,
    SkinUnavailable,
)
from app.models.driver import Driver
from app.models.enums import CountryCode, Gender, WalletOwnerType, WalletTransactionType
from app.models.user import User
from app.models.vehicle_skin import (
    RARITIES,
    SOURCE_GIFT,
    SOURCE_GRANT,
    SOURCE_PURCHASE,
    DriverVehicleSkin,
    VehicleSkin,
    VehicleSkinPrice,
)
from app.schemas.driver import ART_MAP, ART_STORE, skin_art_url as art_url
from app.schemas.vehicle_skin import (
    BuySkinOut,
    GarageOut,
    SkinOut,
    SkinPurchaseRow,
    SkinPurchasesOut,
    StoreOut,
)
from app.services import admin_search, geo, skin_artwork, wallet
from app.services.pricing import round_money

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------- القراءة


async def _owned_rows(
    session: AsyncSession, driver_id: uuid.UUID
) -> dict[uuid.UUID, DriverVehicleSkin]:
    rows = await session.scalars(
        select(DriverVehicleSkin).where(DriverVehicleSkin.driver_id == driver_id)
    )
    return {row.skin_id: row for row in rows}


@dataclass(frozen=True, slots=True)
class SkinAggregate:
    """مجاميعُ مركبةٍ واحدة — **بيتٌ واحدٌ لِما كان في بيتين**.

    كان «كم يملكها» يُحسب مرّتين: مرّةً هنا للمتجر والكراج، ومرّةً في
    `routers/admin_vehicle_skins._owned_counts` للوحة. **وهما يتّفقان اليوم**،
    وهذا بعينه ما يجعله الشكلَ الثامن: بابان ينشران الرقمَ نفسَه، **كلٌّ
    صادقٌ وحدَه**، ويفترقان أوّلَ شرطٍ يُضاف إلى أحدهما — منحةٌ لا تُعدّ
    مبيعاً، أو مِلكيّةٌ مسترجَعة. **فصار الحسابُ هنا وحدَه** (`SPEC §28.7`،
    البندُ المفتوحُ الوحيدُ فيه).

    **والثلاثةُ تُفرَّق لأنها ثلاثةُ أسئلة**: `owners` من يملكها كيفما ملكها
    (وهو ما يُنقَص من `max_supply`)، و`sold` من **دفع** ثمنَها — فالهديةُ
    تُقتنى ولا تُباع، وخلطُهما يضع مركبةً لم تُبَع قطُّ على رأس قائمة
    المبيعات. و`revenue` **بعملته** لا مجموعاً: جمعُ دينارٍ أردنيٍّ على ليبيٍّ
    رقمٌ لا معنى له.
    """

    owners: int
    sold: int
    revenue: dict[str, Decimal]


async def aggregates(
    session: AsyncSession, skin_ids: list[uuid.UUID] | None = None
) -> dict[uuid.UUID, SkinAggregate]:
    """مجاميعُ المِلكيّة — **استعلامٌ واحدٌ لا واحدٌ لكلِّ بطاقة**، ومجموعةٌ في
    القاعدة لا في بايثون (§14: اللوحةُ لا تجمع صفوفاً، وجمعُ صفحةٍ مقصوصةٍ
    يُخرج رقماً عنوانُه «الكلّي» وقيمتُه «ما ظهر»).

    و`skin_ids=None` تعني **الكتالوجَ كلَّه** — تحتاجه اللوحة، ولا تحتاجه
    بطاقاتُ المتجر.
    """
    if skin_ids is not None and not skin_ids:
        return {}
    query = select(
        DriverVehicleSkin.skin_id,
        func.count().label("owners"),
        func.count(DriverVehicleSkin.price_paid).label("sold"),
        DriverVehicleSkin.currency,
        func.coalesce(func.sum(DriverVehicleSkin.price_paid), 0).label("revenue"),
    ).group_by(DriverVehicleSkin.skin_id, DriverVehicleSkin.currency)
    if skin_ids is not None:
        query = query.where(DriverVehicleSkin.skin_id.in_(skin_ids))

    out: dict[uuid.UUID, SkinAggregate] = {}
    for row in await session.execute(query):
        current = out.get(row.skin_id)
        revenue = dict(current.revenue) if current else {}
        if row.currency and row.revenue:
            revenue[row.currency] = revenue.get(row.currency, Decimal("0")) + row.revenue
        out[row.skin_id] = SkinAggregate(
            owners=(current.owners if current else 0) + int(row.owners),
            sold=(current.sold if current else 0) + int(row.sold),
            revenue=revenue,
        )
    return out


async def _owners_counts(
    session: AsyncSession, skin_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """عددُ المالكين وحدَه — قراءةٌ ضيّقةٌ فوق `aggregates`.

    و«المتبقّي» و«عدّادُ الاقتناء» يُقرآن منه معاً، فلا رقمان لمصدرٍ واحد.
    """
    return {
        skin_id: item.owners
        for skin_id, item in (await aggregates(session, skin_ids)).items()
    }


async def purchase_log(
    session: AsyncSession,
    *,
    limit: int = 100,
    offset: int = 0,
    skin_id: uuid.UUID | None = None,
    q: str | None = None,
) -> SkinPurchasesOut:
    """سجلُّ مشتريات المركبات — **شاشتُه مستقلّةٌ لأن المال يخرج من محافظ**.

    **وموضعُه الخدمةُ لا الموجّه** (`SPEC §28.7`): اللوحةُ تعرض ولا تحسب،
    والمجاميعُ تُجمع في القاعدة على الجدول كلِّه — **لا على الصفحة**. صفحةٌ
    محدودةٌ بخمسين تُجمع في المتصفّح تُخرج رقماً عنوانُه «الإيرادُ الكلي»
    وقيمتُه «إيرادُ ما ظهر»، **والفرقُ لا يُرى** (§14).

    **والمِلكيّةُ الفعّالةُ تُقرأ من `drivers.active_skin_id` لا تُستنتج**:
    آخرُ ما اشتراه ليس ما فعّله — يشتري ثلاثاً ويُبقي الأولى.
    """
    base = (
        select(DriverVehicleSkin)
        .join(Driver, Driver.id == DriverVehicleSkin.driver_id)
        .join(User, User.id == Driver.user_id)
        .join(VehicleSkin, VehicleSkin.id == DriverVehicleSkin.skin_id)
    )
    if skin_id is not None:
        base = base.where(DriverVehicleSkin.skin_id == skin_id)
    # **مرشِّحٌ فقط** (`services/admin_search.py`): المشتري باسمه أو رقمه، أو
    # اسمُ المركبة. **و`User` و`VehicleSkin` مضمومان أصلاً واحداً لواحد**
    term = admin_search.normalize(q)
    if term is not None:
        pattern = admin_search.like(term)
        base = base.where(
            or_(
                User.name.ilike(pattern),
                User.phone.ilike(pattern),
                VehicleSkin.name.ilike(pattern),
            )
        )

    rows = (
        await session.execute(
            base.add_columns(
                User.name.label("driver_name"),
                User.phone.label("driver_phone"),
                VehicleSkin.name.label("skin_name"),
                VehicleSkin.rarity.label("rarity"),
                Driver.active_skin_id.label("active_skin_id"),
            )
            .order_by(DriverVehicleSkin.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    # **العدُّ والمجاميعُ على الجدول كلِّه** — استعلامٌ مستقلٌّ عن الصفحة
    totals_query = select(
        func.count().label("total"),
        func.count(DriverVehicleSkin.price_paid).label("sold"),
        func.sum(
            case((DriverVehicleSkin.source == SOURCE_GIFT, 1), else_=0)
        ).label("gifted"),
        func.sum(
            case((DriverVehicleSkin.source == SOURCE_GRANT, 1), else_=0)
        ).label("granted"),
    )
    if skin_id is not None:
        totals_query = totals_query.where(DriverVehicleSkin.skin_id == skin_id)
    totals = (await session.execute(totals_query)).one()

    revenue_query = select(
        DriverVehicleSkin.currency,
        func.coalesce(func.sum(DriverVehicleSkin.price_paid), 0),
    ).where(DriverVehicleSkin.currency.is_not(None)).group_by(
        DriverVehicleSkin.currency
    )
    if skin_id is not None:
        revenue_query = revenue_query.where(DriverVehicleSkin.skin_id == skin_id)
    revenue = {
        code: round_money(amount)
        for code, amount in (await session.execute(revenue_query))
        if amount
    }

    return SkinPurchasesOut(
        rows=[
            SkinPurchaseRow(
                id=row.DriverVehicleSkin.id,
                driver_id=row.DriverVehicleSkin.driver_id,
                driver_name=row.driver_name,
                driver_phone=row.driver_phone,
                skin_id=row.DriverVehicleSkin.skin_id,
                skin_name=row.skin_name,
                rarity=row.rarity,
                source=row.DriverVehicleSkin.source,
                price_paid=row.DriverVehicleSkin.price_paid,
                currency=row.DriverVehicleSkin.currency,
                is_active_for_driver=(
                    row.active_skin_id == row.DriverVehicleSkin.skin_id
                ),
                created_at=row.DriverVehicleSkin.created_at,
            )
            for row in rows
        ],
        total=int(totals.total or 0),
        revenue_by_currency=revenue,
        gifted_count=int(totals.gifted or 0),
        granted_count=int(totals.granted or 0),
        # **ميزانيّةُ الشهر المجاني = عددُ الهدايا**: الهديةُ تُمنح على حدث
        # تفعيلِ أوّلِ اشتراكٍ لا على مبلغه، وكلُّ هديةٍ صفٌّ واحدٌ لا يتكرّر
        # (`uq_driver_skin` + مقارنةٌ حيّةٌ على `source='gift'`)
        free_month_grants=int(totals.gifted or 0),
    )


async def _prices(
    session: AsyncSession, country: CountryCode
) -> dict[uuid.UUID, Decimal]:
    rows = await session.execute(
        select(VehicleSkinPrice.skin_id, VehicleSkinPrice.price).where(
            VehicleSkinPrice.country_code == country
        )
    )
    return {skin_id: price for skin_id, price in rows}


def _shuffle_key(skin_id: uuid.UUID) -> str:
    """**مفتاحُ خلطٍ ثابتٌ من المُعرّف** — لا عشوائيَّ ولا أبجديّ.

    الأبجديّةُ تكدّس عائلةَ اللون (الأسماءُ تبدأ بها)، **والعشوائيُّ الحقيقيُّ
    يكسر العقد**: ترتيبان مختلفان لنداءين يجعلان «الثالثةَ من اليسار» تعني
    مركبتين، وهو ما يحرسه شرطُ «الترتيبُ عقدٌ لا ذوق». **والتلبيدُ (hash) صافٍ**:
    الترتيبُ هو هو في كلِّ نداءٍ ولكلِّ قارئ، ولا يتبدّل إلا بتبدّل المُعرّف.
    """
    return hashlib.blake2s(skin_id.bytes, digest_size=8).hexdigest()


def _rarity_rank(skin: VehicleSkin) -> int:
    try:
        return RARITIES.index(skin.rarity)
    except ValueError:  # pragma: no cover - يمنعه قيدُ CHECK
        return len(RARITIES)


def _in_season(skin: VehicleSkin, now: datetime) -> bool:
    if skin.valid_from is not None and skin.valid_from > now:
        return False
    if skin.valid_until is not None and skin.valid_until <= now:
        return False
    return True


def _feminine_ok(skin: VehicleSkin, user: User) -> bool:
    """المركبةُ المقصورةُ على السائقات تقرأ **الوسمَ لا الإقرار**.

    قاعدةُ 10-ج نفسُها: ما يرفع قيداً أو يمنح امتيازاً يحتاج ختمَ الإدارة،
    وما يقيّد صاحبَه وحدَه يُكتب بكلمته.
    """
    if not skin.feminine_drivers_only:
        return True
    return user.gender is Gender.FEMALE and user.gender_verified_at is not None


def _to_out(
    skin: VehicleSkin,
    *,
    price: Decimal | None,
    currency: str | None,
    owners: int,
    owned_row: DriverVehicleSkin | None,
    active_skin_id: uuid.UUID | None,
    driver_level: int,
    balance: Decimal,
    now: datetime,
) -> SkinOut:
    remaining = None if skin.max_supply is None else max(0, skin.max_supply - owners)

    # **سببٌ واحدٌ لا أكثر، وبترتيب العقد** — شاشتان ترتّبانه اختلافاً تقولان
    # لكبتنٍ واحدٍ سببين لرفضٍ واحد
    reason = None
    if owned_row is not None:
        reason = "owned"
    elif remaining is not None and remaining <= 0:
        reason = "sold_out"
    elif skin.level_required is not None and driver_level < skin.level_required:
        reason = "level_locked"
    elif not _in_season(skin, now):
        reason = "out_of_season"
    elif price is not None and balance < price:
        reason = "insufficient_balance"

    return SkinOut(
        id=skin.id,
        name=skin.name,
        rarity=skin.rarity,
        store_image_url=art_url(skin.id, ART_STORE),
        map_image_url=art_url(skin.id, ART_MAP),
        map_scale_percent=skin.map_scale_percent,
        map_rotates=skin.map_rotates,
        visible_before_accept=skin.visible_before_accept,
        price=price,
        currency=currency,
        # **الطرحُ هنا لا في الشاشة** (§14): `Number(balance) − Number(price)`
        # مالٌ عبر عائم. و`quantize` لأن `Decimal` مبنيّاً في بايثون يُسلسَل
        # `"0"` لا `"0.000"` — **الشكلُ السابع**، وقد وقع في هذا الملفّ نفسِه.
        balance_after=(
            None if price is None else round_money(balance - price)
        ),
        remaining=remaining,
        owners_count=owners,
        level_required=skin.level_required,
        valid_until=skin.valid_until,
        owned=owned_row is not None,
        active=active_skin_id is not None and active_skin_id == skin.id,
        blocked_reason=reason,
    )


def has_artwork(skin: VehicleSkin) -> bool:
    """**أله رسمةٌ يخدمها بابُ الرسم؟** — يُقرأ من الصفّ لا من ندرته.

    `art_url` يبني مساراً لكلِّ صفٍّ سواءٌ أحمل رسمةً أم لا، **والفرقُ يظهر
    ٤٠٤ في يد كبتن**: بطاقةٌ برسمةٍ مكسورة. وهي إحدى صورتين، وكلتاهما تقع:
    مركبةٌ أُنشئت في اللوحة ولم تُرفع رسمتُها بعد، وفئةٌ لم يغطِّها المولّد
    (`rare`/`legendary`، 2026-08-22).

    **والشرطُ على الصفّ لا على الندرة** (§28.4): «أين تُرى مكتوبٌ في الصفّ لا
    مستنتَجٌ من الندرة» — والقاعدةُ نفسُها هنا. فشرطٌ بالندرة يُخفي أسطوريةً
    رُفعت رسمتُها فعلاً، **ويُظهر عاديةً أُنشئت فارغة** — أي يخطئ في الاتجاهين.

    **ويُقاس وجودُ الملفِّ لا وجودُ المفتاح** — وهذا ليس تشدّداً: قِيس في
    قاعدة التطوير (2026-08-22) أن `asset_key = "city-taxi"` **ولا ملفَّ بهذا
    الاسم في الحزمة**، فبابُ الرسم يردّ ٤٠٤ والبطاقةُ مكسورة. **وصفٌّ يَعِد
    بملفٍّ ليس هناك** هو بعينه ما تحرسه قاعدةُ «لا نجاحَ يُعلَن قبل التحقق
    ممّا كُتب» — والمفتاحُ المكتوبُ **تصريحٌ**، والملفُّ **واقعة**.
    """
    if skin.asset_key is not None:
        # `bundled_path` تتحقّق من الاسم **ومن أن الملفَّ موجودٌ فعلاً**،
        # وترفع `DocumentFileMissing` فيما عدا ذلك — فلا فحصَ ثانٍ هنا
        # يفترق عنها أوّلَ تغييرٍ في اصطلاح التسمية.
        for slot in ("store", "map"):
            try:
                skin_artwork.bundled_path(skin.asset_key, slot)  # type: ignore[arg-type]
            except Exception:
                return False
        return True
    # **والشكلان شرطٌ لا أحدُهما** (قرارُ المالك 2026-08-23): المجسّمُ للمتجر
    # والكراج، **والعلويّةُ للخريطة** — ولنفس السيارة، والفرقُ زاويةُ النظر.
    #
    # **وكان الشرطُ يمرّ بأحدهما فعلياً** لأن رفعةً واحدةً كانت تملأ الخانتين
    # بمقاسين، **والمقاسُ ليس منظوراً**. فصار لكلِّ شكلٍ رفعتُه، **وصار غيابُ
    # أحدهما يُخفي المركبةَ من المتجر** — «لا تُنشر قبل أن تُرفع» موسَّعةً من
    # «أله رسمة؟» إلى **«أله كلُّ رسماته؟»**.
    #
    # **ولا يُستبدل الناقصُ ببديلٍ عامّ**: نادرةٌ تُرسم بسيارةٍ عامّةٍ على
    # الخريطة **شكلٌ ثانٍ لمركبةٍ واحدة** — وهو ما وُجد هذا الشرطُ ليمنعه.
    return skin.store_image_path is not None and skin.map_image_path is not None


async def _catalogue(session: AsyncSession) -> list[VehicleSkin]:
    """**والمركبةُ بلا رسمةٍ لا تدخل الكتالوج** (قرارُ المالك 2026-08-22).

    **ووعدٌ لا يُنجَز أسوأُ من غيابه** — قاعدتُه في §28.3/٤ نفسُها التي تُخفي
    المقفولةَ بالمستوى حيث المستوياتُ مطفأة. و«أسطوريةٌ» تُرسم كالعادية
    **ندرةٌ لا يفهمها من دفع**، وبطاقةٌ برسمةٍ مكسورةٍ أسوأُ من الاثنتين.

    **ونداءُ هذا البابِ واحدٌ — المتجرُ وحدَه** (قِيس، لا افتُرض): `garage_for`
    يقرأ المملوكةَ بمعرّفاتها مباشرةً ولا يمرّ من هنا. **وهذا هو الصواب**:
    **ما يملكه كبتنٌ لا يُنتزع من كراجه** لأن الإدارةَ لم ترفع رسمةً بعد،
    والمخفيُّ هو **ما يُعرض للبيع** لا ما مُلِك.
    """
    rows = await session.scalars(
        select(VehicleSkin).where(VehicleSkin.is_active.is_(True))
    )
    return [skin for skin in rows if has_artwork(skin)]


async def store_for(
    session: AsyncSession,
    driver: Driver,
    user: User,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> StoreOut:
    """المتجرُ كما يراه هذا الكبتن — **ورصيدُه معه بنداءٍ واحد**.

    **والترتيبُ عقدٌ لا ذوق**: بالندرة صعوداً، **ثم بمفتاحِ خلطٍ ثابت** —
    شاشتان ترتّبان الشيءَ نفسَه اختلافاً تجعلان «الثالثةَ من اليسار» تعني
    مركبتين. **والثباتُ هو الشرط، لا الأبجديّة**: `_shuffle_key` دالّةٌ صافيةٌ
    من مُعرّف المركبة، فترتيبُها هو هو في كلِّ نداءٍ ولكلِّ قارئ.

    **ولمَ تُرك الاسمُ مفتاحاً**: أسماءُ الكتالوج تبدأ بعائلة اللون
    («البرتقالية …»)، فالترتيبُ الأبجديُّ **يكدّس لوناً واحداً في أوّل
    الصفحة** — قِيس: ٣٧٣ بطاقةً صدرُها جدارٌ برتقاليٌّ كامل. وهو عطبُ عرضٍ
    لا ذوق: من يفتح متجراً فيرى عشرين نسخةً من لونٍ واحدٍ يظنّ المعروضَ
    قليلاً ويخرج.

    **والصفحةُ محدودةٌ بحقّ** (`limit`/`offset`): الكتالوجُ ثلاثُ مئةٍ وزيادة،
    وبطاقةٌ لكلِّ واحدةٍ تعني ٣٧٣ صورةً في شاشةِ هاتف. **والمجموعُ يُنشر
    (`total`)** فيعرف التطبيقُ متى يتوقّف بلا أن يجمع صفحاتِه.

    **ولا تُعرض مركبةٌ بلا سعرٍ في هذا السوق**: بطاقةٌ بلا سعرٍ زرُّها لا
    يفعل شيئاً، وهي «بابٌ بلا زرّ» مقلوباً. والهديةُ والبديلُ المنشورُ
    يُقرآن في الكراج لا هنا.
    """
    now = _now()
    country = user.country_code
    prices = await _prices(session, country)
    owned = await _owned_rows(session, driver.id)
    catalogue = [
        skin
        for skin in await _catalogue(session)
        if skin.id in prices and _feminine_ok(skin, user)
    ]
    counts = await _owners_counts(session, [skin.id for skin in catalogue])
    balance = await wallet.balance(session, user.id, WalletOwnerType.DRIVER)
    currency = currency_for_country(country).value

    catalogue.sort(key=lambda skin: (_rarity_rank(skin), _shuffle_key(skin.id)))
    total = len(catalogue)
    page = catalogue if limit is None else catalogue[offset : offset + limit]
    return StoreOut(
        total=total,
        skins=[
            _to_out(
                skin,
                price=prices.get(skin.id),
                currency=currency,
                owners=counts.get(skin.id, 0),
                owned_row=owned.get(skin.id),
                active_skin_id=driver.active_skin_id,
                driver_level=driver.level,
                balance=balance,
                now=now,
            )
            for skin in page
        ],
        balance=balance,
        currency=currency,
        driver_level=driver.level,
    )


async def garage_for(
    session: AsyncSession, driver: Driver, user: User, *, has_subscription: bool
) -> GarageOut:
    """كراجُ الكبتن — **وما يحتاجه الكراجُ نفسُه** بنداءٍ واحد.

    **والورقةُ الاحتفاليةُ تُعرض مرةً**: أوّلُ صفٍّ مملوكٍ لم يُختم `seen_at`،
    والأقدمُ أولاً — فمن وُهب مركبتين ولم يفتح التطبيق يرى ورقتيهما بترتيب
    وقوعهما لا بترتيبٍ عشوائيّ.
    """
    now = _now()
    country = user.country_code
    prices = await _prices(session, country)
    owned = await _owned_rows(session, driver.id)
    if not owned:
        return GarageOut(
            skins=[],
            active_skin_id=driver.active_skin_id,
            celebrate=None,
            has_subscription=has_subscription,
        )

    skins = list(
        await session.scalars(
            select(VehicleSkin).where(VehicleSkin.id.in_(list(owned)))
        )
    )
    counts = await _owners_counts(session, [skin.id for skin in skins])
    balance = await wallet.balance(session, user.id, WalletOwnerType.DRIVER)
    currency = currency_for_country(country).value

    skins.sort(key=lambda skin: (_rarity_rank(skin), skin.name))
    rows = {
        skin.id: _to_out(
            skin,
            price=prices.get(skin.id),
            currency=currency,
            owners=counts.get(skin.id, 0),
            owned_row=owned[skin.id],
            active_skin_id=driver.active_skin_id,
            driver_level=driver.level,
            balance=balance,
            now=now,
        )
        for skin in skins
    }

    unseen = sorted(
        (row for row in owned.values() if row.seen_at is None and row.skin_id in rows),
        key=lambda row: row.created_at,
    )
    return GarageOut(
        skins=[rows[skin.id] for skin in skins],
        active_skin_id=driver.active_skin_id,
        celebrate=rows[unseen[0].skin_id] if unseen else None,
        has_subscription=has_subscription,
    )


# ------------------------------------------------------------------- الكتابة


async def _locked_skin(session: AsyncSession, skin_id: uuid.UUID) -> VehicleSkin:
    """**يُقفل الصفُّ ثم يُقرأ العدد** — والعكسُ يبيع آخرَ نسخةٍ مرتين.

    نفسُ شكلِ `offers.resolve(for_update=True)`: ما قبل القفل قراءةٌ قديمة،
    فيُعاد كلُّ فحصٍ بعده.
    """
    skin = await session.get(
        VehicleSkin, skin_id, with_for_update=True, populate_existing=True
    )
    if skin is None:
        raise NotFound("هذه المركبة غير موجودة")
    return skin


async def buy(
    session: AsyncSession, *, driver: Driver, user: User, skin_id: uuid.UUID
) -> BuySkinOut:
    """شراءُ مركبةٍ من رصيد الكبتن — **صفُّ مِلكيّةٍ وقيدٌ في المعاملة نفسِها**.

    **والسعرُ يُجمَّد على صفِّ المِلكيّة** كـ`commission_percent_at_ride`:
    تعديلُ السعر غداً لا يحرّك ما دُفع أمس، و«كم أنفق الكباتن» يبقى له جوابٌ
    واحدٌ بعد أيِّ تعديل. **والعملةُ من الدولة** لا من عميل.

    و**الرصيدُ لا يُفحص هنا**: `wallet.record` يرفض قيداً يُنزل الرصيدَ تحت
    الصفر (`balance_after >= 0` في القاعدة نفسِها) — وفحصٌ ثانٍ فوقه بيتٌ
    ثانٍ لقاعدةٍ واحدة.
    """
    now = _now()
    skin = await _locked_skin(session, skin_id)

    owned = await _owned_rows(session, driver.id)
    if skin.id in owned:
        raise SkinAlreadyOwned()
    if not skin.is_active or not _feminine_ok(skin, user) or not _in_season(skin, now):
        raise SkinUnavailable()
    if skin.level_required is not None and driver.level < skin.level_required:
        raise SkinLevelLocked()

    price = await session.scalar(
        select(VehicleSkinPrice.price).where(
            VehicleSkinPrice.skin_id == skin.id,
            VehicleSkinPrice.country_code == user.country_code,
        )
    )
    if price is None:
        # **لا تُباع في هذا السوق** — والهديةُ والبديلُ المنشورُ من هذا الصنف
        raise SkinUnavailable()

    if skin.max_supply is not None:
        owners = (await _owners_counts(session, [skin.id])).get(skin.id, 0)
        if owners >= skin.max_supply:
            raise SkinSoldOut()

    currency = currency_for_country(user.country_code).value
    row = DriverVehicleSkin(
        driver_id=driver.id,
        skin_id=skin.id,
        source=SOURCE_PURCHASE,
        price_paid=price,
        currency=currency,
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:  # pragma: no cover - يسبقه فحصُ المِلكيّة
        raise SkinAlreadyOwned() from exc

    entry = await wallet.record(
        session,
        owner=user,
        owner_type=WalletOwnerType.DRIVER,
        tx_type=WalletTransactionType.SKIN_PURCHASE,
        amount=-price,
        reference=skin.name,
        # **مشتقٌّ لا مُرسَلٌ من العميل**: ضغطتان تتسلسلان على قفل المحفظة
        # فتجد الثانيةُ قيدَ الأولى بدل قيدٍ ثانٍ لمركبةٍ واحدة.
        #
        # **وبلا مُعرّف الكبتن فيه**، وهو ليس اختصاراً: التفرّدُ في القاعدة
        # `(owner_id, idempotency_key)`، فالمالكُ في المفتاح مرتين حشوٌ —
        # **وقد قِيس أنه يتجاوز `VARCHAR(64)`** (٧٨ محرفاً) فيسقط كلُّ شراء
        idempotency_key=f"skin:{skin.id}",
    )

    owners = (await _owners_counts(session, [skin.id])).get(skin.id, 0)
    return BuySkinOut(
        skin=_to_out(
            skin,
            price=price,
            currency=currency,
            owners=owners,
            owned_row=row,
            active_skin_id=driver.active_skin_id,
            driver_level=driver.level,
            balance=entry.balance_after,
            now=now,
        ),
        balance_after=entry.balance_after,
        currency=currency,
    )


async def activate(session: AsyncSession, *, driver: Driver, skin_id: uuid.UUID) -> None:
    """تفعيلُ مركبةٍ يملكها — **ولا تُفعَّل مركبةٌ لا يملكها**.

    **والمِلكيّةُ للحساب لا للسيارة**: عمودٌ واحدٌ على `drivers`، فمن يملك
    سيارتين تظهر مركبتُه مهما قاد اليوم.
    """
    owns = await session.scalar(
        select(DriverVehicleSkin.id).where(
            DriverVehicleSkin.driver_id == driver.id,
            DriverVehicleSkin.skin_id == skin_id,
        )
    )
    if owns is None:
        raise SkinNotOwned()
    driver.active_skin_id = skin_id


async def mark_seen(session: AsyncSession, *, driver: Driver, skin_id: uuid.UUID) -> None:
    """ختمُ الورقة الاحتفالية — **تُعرض مرةً**، و`NULL` تعني «لم تُعرض بعد»."""
    row = await session.scalar(
        select(DriverVehicleSkin).where(
            DriverVehicleSkin.driver_id == driver.id,
            DriverVehicleSkin.skin_id == skin_id,
        )
    )
    if row is None:
        raise SkinNotOwned()
    if row.seen_at is None:
        row.seen_at = _now()


async def _gift_skin(session: AsyncSession) -> VehicleSkin | None:
    return await session.scalar(
        select(VehicleSkin)
        .where(VehicleSkin.is_gift.is_(True), VehicleSkin.is_active.is_(True))
        .order_by(VehicleSkin.created_at)
        .limit(1)
    )


async def grant_gift_on_first_subscription(
    session: AsyncSession, driver: Driver
) -> DriverVehicleSkin | None:
    """هديةُ **أوّلِ** اشتراك — تُمنح مرةً في عمر الحساب.

    **و«مرةً» مقارنةٌ حيّةٌ لا عمودُ ختم** (قاعدةُ «flagged يُقاس ولا يُوسَم»):
    وجودُ صفِّ مِلكيّةٍ مصدرُه `gift` **هو** الجواب — وصفوفُ المِلكيّة لا
    تُحذف، فلا يعود السؤالُ يفترق عن جوابه.

    **وموضعُها `subscriptions._create`**: البابُ الوحيدُ الذي يكتب صفَّ اشتراكٍ
    في القنوات الأربع — فتشمل بلا شرطٍ إضافيٍّ **اشتراكَ عرضِ الشهر المجاني**،
    وهو المطلوب: الهديةُ على **حدث التفعيل** لا على المبلغ المدفوع.

    **ولا تُفشل شراءَ اشتراكٍ أبداً**: تُنفَّذ داخل نقطة حفظٍ (`SAVEPOINT`)،
    فتعثُّرُها يُرجع الهديةَ وحدَها ويترك الاشتراكَ قائماً. **ولولا نقطةُ
    الحفظ لأفسد `IntegrityError` المعاملةَ كلَّها** فسقط الاشتراكُ معها —
    وهو أسوأُ ما تفعله هديّة. **والالتقاطُ ضيّقٌ عمداً**: خطأٌ برمجيٌّ يبقى
    ظاهراً (درسُ 12-ط).
    """
    skin = await _gift_skin(session)
    if skin is None:
        return None

    already = await session.scalar(
        select(DriverVehicleSkin.id).where(
            DriverVehicleSkin.driver_id == driver.id,
            DriverVehicleSkin.source == SOURCE_GIFT,
        )
    )
    if already is not None:
        return None

    try:
        async with session.begin_nested():
            row = DriverVehicleSkin(
                driver_id=driver.id, skin_id=skin.id, source=SOURCE_GIFT
            )
            session.add(row)
            await session.flush()
            # **تُفعَّل إن لم يكن له مركبةٌ نشطة** — ولا تنقض اختياراً قائماً:
            # من اختار مركبةً بيده لا تُبدَّل من تحته بهدية
            if driver.active_skin_id is None:
                driver.active_skin_id = skin.id
    except IntegrityError:
        # سباقُ منحتين — القيدُ الفريد `uq_driver_skin` هو الحارس
        logger.warning("هديةُ مركبةٍ تسابقت مع أخرى: driver=%s", driver.id)
        return None
    return row


async def grant(
    session: AsyncSession, *, driver_id: uuid.UUID, skin_id: uuid.UUID
) -> DriverVehicleSkin:
    """منحةٌ إدارية — **بلا مالٍ وبلا سعرٍ مجمَّد**: لم يدفع أحدٌ شيئاً.

    **ولا تتجاوز الكميّة**: منحةٌ فوق `max_supply` تجعل «المتبقّي» سالباً،
    فيقرأ المتجرُ نفادَ ما لم ينفد.
    """
    skin = await _locked_skin(session, skin_id)
    owns = await session.scalar(
        select(DriverVehicleSkin.id).where(
            DriverVehicleSkin.driver_id == driver_id,
            DriverVehicleSkin.skin_id == skin_id,
        )
    )
    if owns is not None:
        raise SkinAlreadyOwned()
    if skin.max_supply is not None:
        owners = (await _owners_counts(session, [skin.id])).get(skin.id, 0)
        if owners >= skin.max_supply:
            raise SkinSoldOut()
    row = DriverVehicleSkin(driver_id=driver_id, skin_id=skin_id, source=SOURCE_GRANT)
    session.add(row)
    await session.flush()
    return row


# ------------------------------------------------------------ ما يُنشر للخريطة


async def _public_default(session: AsyncSession) -> VehicleSkin | None:
    return await session.scalar(
        select(VehicleSkin)
        .where(VehicleSkin.is_public_default.is_(True), VehicleSkin.is_active.is_(True))
        .order_by(VehicleSkin.created_at)
        .limit(1)
    )


def _map_skin(skin: VehicleSkin) -> geo.MapSkin:
    return geo.MapSkin(
        skin_id=skin.id,
        image_url=art_url(skin.id, ART_MAP),
        scale_percent=skin.map_scale_percent,
        rotates=skin.map_rotates,
    )


async def publishable_skin_for(
    session: AsyncSession, driver: Driver
) -> geo.MapSkin | None:
    """**ما يُرسم على الخريطة الحرّة — قبل القبول** (الشكلُ الثالثَ عشر).

    النشطةُ إن كانت `visible_before_accept`، **وإلّا البديلُ المنشور**.

    **و`null` لا تُنشر لمن هو على الخريطة**: غيابُ المركبة يُقرأ «عنده نادرة»
    — فيصير الامتيازُ علامةً على صاحبه، وهو بعينه عطبُ صورة الكبتن المُعفاة
    (2026-08-22). **والعلاجُ ملءُ الغياب بما لا يُفرَّق عن الحضور**: كلُّ من
    على الخريطة يحمل مركبةً، ومن لا مركبةَ نشطةً له يحمل البديلَ نفسَه الذي
    يحمله صاحبُ الأسطورية.

    **وترجع `None` في حالةٍ واحدة**: ألّا يوجد بديلٌ منشورٌ في الكتالوج أصلاً
    — وحينها تغيب عن **الجميع** سواءً، فلا فرقَ يُقاس. وهي حالُ قاعدةٍ لم
    تُبذَر مركباتُها بعد.
    """
    if driver.active_skin_id is not None:
        active = await session.get(VehicleSkin, driver.active_skin_id)
        if active is not None and active.is_active and active.visible_before_accept:
            return _map_skin(active)
    fallback = await _public_default(session)
    return None if fallback is None else _map_skin(fallback)


async def skin_for_ride(session: AsyncSession, driver: Driver) -> geo.MapSkin | None:
    """**مركبتُه الحقيقيةُ بعد القبول** — أياً كانت ندرتُها.

    والفرقُ عن `publishable_skin_for` هو كلُّ الميزة: قبل القبول تُخفى
    النادرةُ لأن **ما يُرى ويندر يصير معرّفاً** ينقض تجهيلَ §10؛ وبعده يعرف
    الراكبُ اسمَ الكبتن ولوحتَه أصلاً، فلا شيءَ يُخفى.
    """
    if driver.active_skin_id is None:
        return None
    skin = await session.get(VehicleSkin, driver.active_skin_id)
    if skin is None or not skin.is_active:
        return None
    return _map_skin(skin)
