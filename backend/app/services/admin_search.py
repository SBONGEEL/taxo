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
    pattern = like(q)
    return (
        select(User.id)
        .where(
            User.id == user_id_column,
            or_(User.name.ilike(pattern), User.phone.ilike(pattern)),
        )
        .exists()
    )


def any_user_clause(q: str, *user_id_columns) -> ColumnElement[bool]:
    """يطابق **أيَّ** طرفٍ من أطراف الصفّ — راكبٌ أو كبتن مثلاً."""
    return or_(*(user_clause(q, column) for column in user_id_columns))


def text_clause(q: str, *columns) -> ColumnElement[bool]:
    """يطابق أعمدةً نصّيةً على الصفِّ نفسِه — مرجعاً أو عنواناً أو سبباً."""
    pattern = like(q)
    return or_(*(column.ilike(pattern) for column in columns))
