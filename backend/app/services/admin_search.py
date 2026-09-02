"""بحثُ قوائم اللوحة — **مرشِّحٌ فقط، بيتٌ واحد** (إذنُ المالك 2026-09-01).

## الشرطُ الذي بُني عليه، بنصِّه

> «أضف `q` إلى استعلامات القوائم المرقَّمة الباقية. **والشرطُ أن الإضافة
> مرشِّح فقط: لا تمسّ الترتيبَ ولا حدودَ الصفحات ولا أيَّ منطقٍ قائم**، ويقيس
> اختبارٌ أن النتائجَ بـ`q` فارغةٍ مطابقةٌ تماماً لما كانت قبل التغيير — في
> القوائم كلِّها لا في واحدة.»

**ولذلك `EXISTS` لا `JOIN`**: ضمُّ جدولٍ يغيّر عددَ الصفوف حين يتعدّد المطابق،
**فيتغيّر ما تحويه الصفحةُ الواحدة** — وهو مسٌّ لحدود الصفحات من حيث لا يُرى.
و`EXISTS` شرطٌ على الصفّ نفسِه: **يمرّ أو لا يمرّ، ولا يضاعف**.

**و`q` الفارغةُ لا تضيف شرطاً البتّة** — لا `WHERE TRUE` ولا `LIKE '%%'`:
**فخطّةُ الاستعلام هي هي**، والنتيجةُ هي هي بايتاً. وهذا ما يقيسه
`tests/test_admin_search.py` على القوائم كلِّها.

## ولمَ الاحتواء لا البادئة

**الرقمُ مخزَّنٌ `E.164` (`+9627…`) والمشرفُ يكتب `07…`** — فبحثُ بادئةٍ لا
يجد شيئاً أبداً، **ويُقرأ «لا نتائج» وهو «لا يبحث»**. والاسمُ يُبحث بجزئه
لأن «أبو محمد» يُكتب «محمد».

## وما لا يفعله هذا الملفّ

**لا يحرس صلاحية**: الحراسةُ على الباب (`require_permission`) — ومن لا يملك
قراءةَ قائمةٍ لا يبلغ هذا الشرطَ أصلاً.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, or_, select

from app.models.driver import Driver
from app.models.user import User


def normalize(q: str | None) -> str | None:
    """يعيد النصَّ مشذَّباً، **أو `None` إن لم يكن فيه شيء**.

    **والفراغُ ليس بحثاً**: `q=""` و`q="   "` و`q=None` ثلاثتُها «لا بحث» —
    **ولو مرّ أحدُها شرطاً لَاختلفت النتيجةُ عمّا كانت**.
    """
    if q is None:
        return None
    text = q.strip()
    return text or None


def like(q: str) -> str:
    """نمطُ الاحتواء — **والحروفُ الخاصّةُ تُهرَّب**.

    **`%` و`_` من حروف `LIKE`**: من كتب `100%` في البحث كان يبحث عن أيِّ شيء،
    **ومن كتب `_` كان يبحث عن أيِّ حرف** — فتُقرأ نتائجُ لا علاقةَ لها بما
    طُلب. والتهريبُ بـ`\\` وهو افتراضُ Postgres.
    """
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def user_clause(q: str, user_id_column) -> ColumnElement[bool]:
    """«صاحبُ هذا الصفِّ اسمُه أو رقمُه يطابق» — **بـ`EXISTS` لا بضمّ**."""
    _must_point_at(user_id_column, "users")
    pattern = like(q)
    return (
        select(User.id)
        .where(
            User.id == user_id_column,
            or_(User.name.ilike(pattern), User.phone.ilike(pattern)),
        )
        .exists()
    )


def text_clause(q: str, *columns) -> ColumnElement[bool]:
    """يطابق أعمدةً نصّيةً على الصفِّ نفسِه — مرجعاً أو عنواناً أو سبباً."""
    pattern = like(q)
    return or_(*(column.ilike(pattern) for column in columns))


def _fk_target(column) -> str | None:
    """اسمُ الجدول الذي يشير إليه العمود — **مقروءٌ من المخطَّط لا مفترَضاً**."""
    for key in column.foreign_keys:
        return key.column.table.name
    return None


def _must_point_at(column, table: str) -> None:
    """يصيح إن كان العمودُ يشير إلى جدولٍ غير الذي يفترضه الشرط.

    **العلّةُ عطبٌ قِيس 2026-09-02**، وهو أخبثُ ما يقع لمرشِّح: `rides.driver_id`
    يشير إلى **`drivers.id` لا `users.id`**، **و`withdrawal_requests.driver_id`
    كذلك** — وهو مكتوبٌ في `ARCHITECTURE.md` بحرفه: «passing the latter silently
    returns zero because it matches no row». فشرطُ `users.id = rides.driver_id`
    **لا يطابق صفّاً أبداً**: لا يرمي، ولا يعيد خطأً، **بل يُسقط نصفَ البحث
    صامتاً** — فمن بحث عن دفعاتِ كبتنٍ باسمه قرأ «لا نتائج» وهو «لا يبحث»،
    وهي علّةُ §35 نفسُها بوجهٍ ثانٍ.

    **ولمَ يُقاس الشكلُ عند بناء الشرط لا عند قراءة النتيجة**: «لا نتائج» جوابٌ
    مشروعٌ لبحثٍ سليم، **فلا اختبارَ عامٌّ يفرّقه عن بحثٍ لا يبحث**. أمّا
    العمودُ فيُقرأ من المخطَّط، **فيسقط الموضعُ الخاطئ في أوّل نداءٍ يحمل `q`**.
    """
    found = _fk_target(column)
    if found is not None and found != table:
        raise AssertionError(
            f"{column} يشير إلى {found} لا إلى {table} — "
            f"وشرطٌ على الجدول الخطأ لا يطابق شيئاً ويُقرأ «لا نتائج»"
        )


def driver_clause(q: str, driver_id_column) -> ColumnElement[bool]:
    """«كبتنُ هذا الصفِّ اسمُه أو رقمُه يطابق» — **والعمودُ `drivers.id`**.

    **وهي ليست `user_clause` بعمودٍ آخر**: بين الصفِّ والاسم قفزتان لا واحدة
    (`drivers.id → drivers.user_id → users.id`)، **وقفزةٌ منسيّةٌ تُسقط البحثَ
    بلا خطأ**. و`EXISTS` لا ضمٌّ، للسبب المكتوب في رأس الملفّ.
    """
    _must_point_at(driver_id_column, "drivers")
    pattern = like(q)
    return (
        select(Driver.id)
        .join(User, Driver.user_id == User.id)
        .where(
            Driver.id == driver_id_column,
            or_(User.name.ilike(pattern), User.phone.ilike(pattern)),
        )
        .exists()
    )


def ride_parties_clause(
    q: str, rider_id_column, driver_id_column
) -> ColumnElement[bool]:
    """طرفا الرحلة معاً — **الراكبُ عبر `users.id` والكبتنُ عبر `drivers.id`**.

    **وسببُ وجودها بيتٌ واحدٌ لا ثلاثة**: ثلاثةُ مواضعَ كانت تكتب هذا الشرطَ
    بيدها (الدفعاتُ · رسومُ الإلغاء · وما يأتي)، **واثنان منها أخطآ العمودَ
    يومَ كُتبا** فسقط نصفُ بحثهما صامتاً.
    """
    return or_(
        user_clause(q, rider_id_column),
        driver_clause(q, driver_id_column),
    )
