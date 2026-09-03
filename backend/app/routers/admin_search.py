"""البحثُ العامُّ في رأس اللوحة — **بابٌ واحدٌ يقفز، لا صفحةُ نتائج** (§39٫١٢٫٤).

## الشرطُ بنصِّه

> «بحثٌ عامٌّ واحدٌ في رأس اللوحة يقفز إلى مستخدمٍ أو كبتنٍ أو رحلةٍ أو
> مطالبةٍ **بالرقم أو الاسم أو المرجع**، **ومن أيِّ صفٍّ يخصّ مستخدماً زرٌّ
> يفتح ملفَّه مباشرة**.»

## ولا شرطَ بحثٍ يُكتب هنا — **البيتُ `services/admin_search.py`**

كلُّ مطابقةٍ في هذا الملفّ تمرّ بدوالِّ ذلك البيت: `person_clause` للاسم
والرقم، و`user_clause` لصاحب الصفّ، و`text_clause` للمرجع. **وحروفُ `LIKE`
تُهرَّب هناك مرّةً واحدة** — ونسخةٌ رابعةٌ من النمط هنا كانت ستفوت التهريبَ
كما فاتته ثلاث مرّاتٍ قبلها (عطبُ ٢٠٢٦-٠٩-٠٢).

## والحراسةُ `StaffUser` **لأن القوائمَ الأربعَ كذلك — مقيساً لا مفترَضاً**

`/admin/users` · `/admin/drivers` · `/admin/rides` · `/admin/topups`
**أربعتُها `_staff: StaffUser` بلا `require_permission`** (قُرئ من توقيعاتها
٢٠٢٦-٠٩-٠٣). **فهذا البابُ يعطي ما تعطيه هي بحرفه، ولا يفتح شيئاً جديداً** —
وهو شرطُ §39٫١٢٫٧: «لا اقتراحَ يعرض ما لا يملك المشرفُ صلاحيتَه».

> **⚠ ومن أضاف `require_permission` إلى إحدى تلك القوائم بعد اليوم يضيفها
> هنا** — وإلا صار هذا البابُ يعرض ما تمنعه هي، **وهو التفافٌ على حارسٍ من
> حيث لا يُرى**. ويقيسه `test_admin_global_search.py::
> test_every_bucket_matches_its_list_guard`.

## والحدُّ خمسةٌ لكلِّ صنف

**قائمةٌ في قائمةٍ منسدلةٍ ليست صفحةَ نتائج**: من يرى عشرين اسماً في درجٍ لا
يقرأ، **ويقفز إلى الصفحة إن أراد الكلّ**. والحدُّ في الاستعلام لا بعده.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import aliased

from app.core.deps import DbSession, StaffUser
from app.models.driver import Driver
from app.models.user import User
from app.models.wallet import WalletTopupRequest
from app.schemas.admin_search import SearchHit, SearchHits
from app.services import admin_search, ride_log

router = APIRouter(prefix="/admin/search", tags=["admin"])

#: **خمسةٌ لكلِّ صنفٍ لا عشرون في واحد**: صنفٌ يفيض يخفي البقيّةَ من الدرج.
PER_KIND = 5


@router.get("", response_model=SearchHits)
async def global_search(
    _staff: StaffUser,
    session: DbSession,
    q: str = Query(max_length=120, description="اسمٌ أو رقمٌ أو مرجعٌ أو معرّف"),
) -> SearchHits:
    """يجمع أوّلَ خمسةٍ من كلِّ صنف — **ولا يبحث بحرفٍ واحد**.

    **حرفٌ واحدٌ يطابق نصفَ الجدول** فيرجع درجاً لا يقرؤه أحد، ويكلّف مسحاً
    كاملاً على كلِّ ضغطة مفتاح. **والحدُّ حرفان كما في `Picker` على الواجهة** —
    والرقمُ المحلّيُّ «07» حرفان، فالحدُّ لا يمنع بحثاً حقيقياً.
    """
    term = admin_search.normalize(q)
    if term is None or len(term) < 2:
        return SearchHits(hits=[])

    hits: list[SearchHit] = []

    # ── حسابات: **الاسمُ سطرٌ والرقمُ تحته** كما في `Picker`
    users = (
        await session.scalars(
            select(User)
            .where(admin_search.person_clause(term))
            .order_by(User.created_at.desc())
            .limit(PER_KIND)
        )
    ).all()
    hits += [
        SearchHit(kind="user", id=row.id, label=row.name, hint=row.phone)
        for row in users
    ]

    # ── كباتن: **`drivers.id` لا `users.id`** — والدرجُ يقفز إلى ملفِّ الكبتن
    drivers = (
        await session.execute(
            select(Driver, User)
            .join(User, Driver.user_id == User.id)
            .where(admin_search.person_clause(term))
            .order_by(Driver.created_at.desc())
            .limit(PER_KIND)
        )
    ).all()
    hits += [
        SearchHit(kind="driver", id=driver.id, label=user.name, hint=user.phone)
        for driver, user in drivers
    ]

    # ── رحلات: **بيتُها `ride_log.list_rides`** — ومعرّفُ الرحلة يُطابَق
    #    كاملاً حين يكون UUID صالحاً، وهو منطقٌ قائمٌ لا يُعاد هنا
    rides = await ride_log.list_rides(session, query=term, limit=PER_KIND)
    hits += [
        SearchHit(
            kind="ride",
            id=ride.id,
            label=str(ride.id),
            hint=ride.status.value,
        )
        for ride in rides
    ]

    # ── مطالبات كليك: **صاحبُها أو مرجعُها** — و`reference` هو ما يُطابَق به
    #    الإيصالُ الورقيُّ بعد شهر.
    #
    # **والتلميحُ اسمُ صاحبها لا حالُها**: «مؤكَّدة» لا تفرّق مطالبتين في درجٍ
    # واحد، **والاسمُ يفرّق** — ولا يحتاج خريطةَ أسماءٍ جديدةً في الواجهة.
    # **واسمٌ مستعارٌ للضمّ، والشرطُ على `users` نفسِه** (عطبٌ أمسكه أوّلُ
    # تشغيل): `user_clause` استعلامٌ متداخلٌ على `users`، **وضمُّ `users` نفسِه
    # في الخارج يجعل SQLAlchemy يربط الداخلَ بالخارج آلياً فيمحو كلَّ FROM** —
    # `InvalidRequestError: returned no FROM clauses due to auto-correlation`.
    # **والاسمُ المستعارُ يفصل الاثنين**: الضمُّ للعرض، والشرطُ للمطابقة.
    owner_alias = aliased(User)
    claims = (
        await session.execute(
            select(WalletTopupRequest, owner_alias)
            .join(owner_alias, WalletTopupRequest.owner_id == owner_alias.id)
            .where(
                or_(
                    admin_search.user_clause(term, WalletTopupRequest.owner_id),
                    admin_search.text_clause(term, WalletTopupRequest.reference),
                )
            )
            .order_by(WalletTopupRequest.created_at.desc())
            .limit(PER_KIND)
        )
    ).all()
    hits += [
        SearchHit(
            kind="claim",
            id=row.id,
            label=row.reference or str(row.id),
            hint=owner.name,
        )
        for row, owner in claims
    ]

    return SearchHits(hits=hits)
