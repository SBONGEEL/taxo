"""فئاتُ الرحلة (SPEC §٦٧، `design/RIDE-CATEGORIES-PLAN.md`) — **قاعدتا من يُطلب ومن يأخذ، في بيتٍ واحد**.

**المدمجتان** (`economy` · `comfort`) **بقاعدة اليوم حرفاً**: تُطلبان حيث لهما أسعار (وصفُّهما في `ride_categories` يُطفئهما إن أُطفئ)، ويأخذهما
من فئةُ مركبته هي فئةُ الطلب — **فلا يتغيّر كبتنٌ واحد** (§٦٧-ب/٧).

**والجديدةُ** تُطلب مشتعلةً وحدَها، ويأخذها من **مركبتُه تستوفي شروطَها** (كلُّ شرطٍ مكتوب؛ وصفةٌ فارغةٌ لا تستوفي شيئاً) **أو مُنحها يدوياً**،
**إلا من نُزعت منه يدوياً**. **وفئةٌ بلا شرطٍ واحدٍ لا يأخذها إلا من مُنحها** — فلا تقع على كلِّ كبتنٍ لأنّ المشرفَ لم يكتب شرطاً.
**والكبتنُ يصله طلبُ فئةِ مركبته وكلِّ فئةٍ جديدةٍ يستحقّها** (§٦٧-ج/٣).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import and_, exists, false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.exceptions import FeatureDisabled, InvalidInput
from app.models.driver import Driver
from app.models.enums import CountryCode, VehicleCategory
from app.models.pricing import PricingRule
from app.models.ride_category import DriverCategoryAccess, RideCategory
from app.models.vehicle import Vehicle
from app.schemas.category import RideCategoryPublic

BUILTIN_KEYS: frozenset[str] = frozenset(category.value for category in VehicleCategory)


#: **وجها المدمجتين حين لا صفَّ لهما** — بأسمائهما في التطبيقين اليوم
_BUILTIN_FACES: dict[str, tuple[str, str, str]] = {
    VehicleCategory.ECONOMY.value: ("اقتصادي", "local_taxi", "الخيار الأوفر"),
    VehicleCategory.COMFORT.value: ("مريح", "directions_car", "سيارة أوسع وأحدث"),
}


def public_face(key: str, row: RideCategory | None) -> RideCategoryPublic:
    """**ما يراه التطبيقان لفئة** — من صفّها، **والمدمجةُ بلا صفٍّ بوجهها الافتراضيّ**."""
    if row is not None:
        return RideCategoryPublic(key=row.key, name=row.name, icon=row.icon, description=row.description, seats=row.seats)
    name, icon, hint = _BUILTIN_FACES.get(key, (key, "local_taxi", ""))
    return RideCategoryPublic(key=key, name=name, icon=icon, description=hint or None, seats=4)


class CategoryUnavailable(FeatureDisabled):
    code = "category_unavailable"
    message = "هذه الفئةُ غيرُ متاحةٍ في بلدك"


def is_builtin(key: str) -> bool:
    return key in BUILTIN_KEYS


async def for_country(session: AsyncSession, country: CountryCode) -> list[RideCategory]:
    """**كلُّ فئات السوق بترتيبها** — للّوحة."""
    rows = await session.scalars(
        select(RideCategory)
        .where(RideCategory.country_code == country)
        .order_by(RideCategory.sort_order, RideCategory.created_at)
    )
    return list(rows)


async def get(session: AsyncSession, country: CountryCode, key: str) -> RideCategory | None:
    return await session.scalar(
        select(RideCategory).where(RideCategory.country_code == country, RideCategory.key == key)
    )


async def requestable_keys(session: AsyncSession, country: CountryCode) -> list[str]:
    """**ما يُطلب الآن في السوق بترتيبه** — المدمجتان ما لم يُطفأ صفُّهما، والجديدةُ المشتعلةُ وحدَها."""
    rows = await for_country(session, country)
    by_key = {row.key: row for row in rows}
    # **مدمجةٌ بلا صفٍّ تُطلب كما اليوم، وأوّلاً** — سوقٌ لم تُبذر له (لا أسعارَ لها فيه يومَ الترحيلة) يبقى كما كان
    keys = [builtin.value for builtin in VehicleCategory if builtin.value not in by_key]
    return keys + [row.key for row in rows if row.is_active]


async def require_requestable(session: AsyncSession, country: CountryCode, key: str) -> None:
    """**يُرفض طلبُ فئةٍ مطفأةٍ أو مجهولة** — والمدمجةُ بلا صفٍّ تمرّ كما اليوم."""
    row = await get(session, country, key)
    if is_builtin(key):
        if row is not None and not row.is_active:
            raise CategoryUnavailable()
        return
    if row is None or not row.is_active:
        raise CategoryUnavailable()


def _vehicle_meets(category: RideCategory) -> ColumnElement[bool]:
    """**مركبةٌ تستوفي كلَّ شرطٍ مكتوب** — وفئةٌ بلا شرطٍ لا تستوفيها مركبة (المنحُ وحدَه)."""
    terms: list[ColumnElement[bool]] = []
    if category.allowed_body_types:
        terms.append(Vehicle.body_type.in_(category.allowed_body_types))
    if category.allowed_fuels:
        terms.append(Vehicle.fuel.in_(category.allowed_fuels))
    if category.min_year is not None:
        terms.append(Vehicle.year >= category.min_year)
    if category.min_seats is not None:
        terms.append(Vehicle.seats >= category.min_seats)
    if not terms:
        return false()
    return and_(*terms)


#: **ترتيبُ المدمجتين بلا صفّ** — كما تبذرهما `0110` (اقتصادي ٠ · مريح ١)
_BUILTIN_RANK: dict[str, int] = {VehicleCategory.ECONOMY.value: 0, VehicleCategory.COMFORT.value: 1}


async def takers(session: AsyncSession, country: CountryCode | None, key: str) -> list[str]:
    """**فئاتُ من يأخذ طلبَ `key`** (§٩١-ب/٩): الفئةُ نفسُها، **وكلُّ فئةٍ أعلى ترتيباً أُشعل فيها «الأعلى يأخذ الأدنى»**.
    والإعدادُ مطفأٌ في كلِّ صفٍّ افتراضاً — فالجوابُ `[key]` وحدَه، والتوزيعُ كما كان حرفاً."""
    if country is None:
        return [key]
    rows = await for_country(session, country)
    by_key = {row.key: row for row in rows}
    own = by_key.get(key)
    rank = own.sort_order if own is not None else _BUILTIN_RANK.get(key)
    if rank is None:
        return [key]
    return [key] + [row.key for row in rows if row.key != key and row.serves_lower and row.sort_order > rank]


async def presence_keys(session: AsyncSession, country: CountryCode | None, key: str) -> frozenset[str] | None:
    """**فئاتُ المركبة التي تُقبل من هاش الحضور** قبل القاعدة (`dispatch`) — و`None`: لا تصفيةَ بالحضور، يحسمها `driver_clause`.
    **والحضورُ لا يحمل إلا مدمجة**، فأيُّ آخذٍ من فئةٍ جديدةٍ يُسقط التصفيةَ كلَّها، كما تسقط لطلبٍ من فئةٍ جديدة."""
    keys = await takers(session, country, key)
    if not all(is_builtin(taker) for taker in keys):
        return None
    return frozenset(keys)


async def driver_clause(session: AsyncSession, country: CountryCode | None, key: str) -> ColumnElement[bool]:
    """**شرطُ «يأخذ هذه الفئة»** على صفِّ `Driver` — يُضمّ إلى شروط التوزيع في `dispatch._eligible_levels`.
    **وكبتنُ فئةٍ أعلى أُشعل فيها «الأعلى يأخذ الأدنى» يأخذها أيضاً** (`takers`)."""
    keys = await takers(session, country, key)
    clauses = [await _own_clause(session, country, taker) for taker in keys]
    return clauses[0] if len(clauses) == 1 else or_(*clauses)


async def _own_clause(session: AsyncSession, country: CountryCode | None, key: str) -> ColumnElement[bool]:
    """**من فئتُه هي `key` نفسُها** — المدمجةُ بفئة مركبته، والجديدةُ بشروطها ومنحها."""
    if is_builtin(key):
        return exists(select(Vehicle.id).where(Vehicle.driver_id == Driver.id, Vehicle.category == key))
    category = await get(session, country, key) if country is not None else None
    if category is None:
        return false()
    qualifies = exists(select(Vehicle.id).where(Vehicle.driver_id == Driver.id, _vehicle_meets(category)))

    def override(granted: bool) -> ColumnElement[bool]:
        return exists(
            select(DriverCategoryAccess.id).where(
                DriverCategoryAccess.driver_id == Driver.id,
                DriverCategoryAccess.category_id == category.id,
                DriverCategoryAccess.granted.is_(granted),
            )
        )

    return and_(or_(qualifies, override(True)), ~override(False))


def _model_matches(patterns: list[str], vehicle: Vehicle) -> bool:
    """**طرازٌ في القائمة** — بلا حالةِ أحرف، وجزءٌ من «الشركة الطراز» يكفي («Camry» يطابق «Toyota Camry»)."""
    label = f"{vehicle.make} {vehicle.model}".casefold()
    return any(pattern.strip().casefold() in label for pattern in patterns if pattern.strip())


async def suggest(session: AsyncSession, country: CountryCode, vehicle: Vehicle) -> tuple[str | None, str]:
    """**الفئةُ المقترحةُ لمركبة** في شاشة الاعتماد (§٩١-ب/٥) — **اقتراحٌ يؤكّده المشرف لا تعيين**، ومعه علّتُه في سطر.

    تُفحص المدمجتان **من الأعلى ترتيباً**: أوّلُ واحدةٍ لها إرشادٌ مكتوب (`min_year` أو `suggest_models`) تستوفيه المركبةُ هي المقترحة،
    وإلا «اقتصادي». **ولا إرشادَ مكتوباً لأيٍّ منهما ⇒ لا اقتراح** — اقتراحٌ بلا قاعدةٍ تخمينٌ يُقرأ قراراً.
    """
    rows = {row.key: row for row in await for_country(session, country)}
    guided = False
    ordered = sorted(BUILTIN_KEYS, key=lambda key: (rows[key].sort_order if key in rows else _BUILTIN_RANK[key]), reverse=True)
    for key in ordered:
        row = rows.get(key)
        if row is None or (row.min_year is None and not row.suggest_models):
            continue
        guided = True
        year_ok = row.min_year is None or vehicle.year >= row.min_year
        model_ok = not row.suggest_models or _model_matches(row.suggest_models, vehicle)
        if year_ok and model_ok:
            return key, f"تستوفي إرشادَ «{row.name}»" + (f" — سنةُ الصنع {vehicle.year} ≥ {row.min_year}" if row.min_year else "")
    if not guided:
        return None, "لا إرشادَ مكتوبٌ للفئتين — اكتبه في «الفئات» (أدنى سنة · الطُّرز)"
    return VehicleCategory.ECONOMY.value, "لا تستوفي إرشادَ فئةٍ أعلى"


#: **الأسعارُ التي لا تُشغَّل فئةٌ بصفرٍ في أيٍّ منها** (§٦٧-ب/٣)
PRICED_FIELDS = ("base_fare", "price_per_km", "price_per_min", "minimum_fare")


async def require_priced(session: AsyncSession, country: CountryCode, key: str) -> None:
    """**لا تُشعَل فئةٌ بلا صفِّ أسعارٍ ولا بسعرٍ صفر** — الخلفيةُ ترفض بعلّتها، لا الشاشةُ وحدَها (§٦٧-ج/٤)."""
    rule = await session.scalar(
        select(PricingRule).where(PricingRule.country_code == country, PricingRule.vehicle_category == key)
    )
    if rule is None:
        raise InvalidInput("ضع أسعارَ هذه الفئة في «التسعير» أوّلاً — لا تُشغَّل فئةٌ بلا أسعار")
    zero = [field for field in PRICED_FIELDS if Decimal(getattr(rule, field)) <= 0]
    if zero:
        raise InvalidInput("لا تُشغَّل فئةٌ بسعرٍ صفر — الأساسيّة والكيلومتر والدقيقة والحدُّ الأدنى كلُّها موجبة")
