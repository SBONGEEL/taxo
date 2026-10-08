"""حسابا التجربة على الإنتاج (SPEC §٦٥-ج) — **البيتُ الواحدُ لكلِّ سؤالٍ عنهما**.

**قولُ المالك**: راكبٌ واحدٌ وكبتنٌ واحد، موسومان بوضوح، **يُستثنيان من التقارير والإحصاءات ولوحات الترتيب وكلِّ ما
يراه المستخدمون، ولا مالَ حقيقيٌّ فيهما** — أيُّ رصيدٍ يلزمهما من تصحيحٍ موسومٍ «تجربة» وحدَه.

**والوسمُ `users.is_test` لا يكتبه بابٌ في التطبيقات ولا في اللوحة** — لا حقلَ له في أيِّ مخطَّط طلب؛ يكتبه سكربتُ الإنشاء
(`scripts/provision_test_accounts.py`) والقاعدةُ وحدَهما.

**ولمَ بيتٌ واحد**: الاستثناءُ يقع في عشرين موضعاً — العدُّ والجمعُ والتوزيعُ والمال — **وشرطٌ يُكتب في كلِّ موضعٍ بصيغته
يفترق أوّلَ تعديل**: أحدُها يقرأ الراكبَ وينسى الكبتن، وآخرُ يكتب `NOT IN` فيُسقط رحلةً بلا كبتن (`NULL NOT IN …` ليس
صدقاً). فتُسمّى الشروطُ هنا مرّةً وتُستعار.

**وثلاثةُ أصنافٍ من الأدوات:**

١. **العزلُ** — يُقرأ في نقطة القرار نفسِها لا فوقها (`dispatch._eligible_levels`، وكلُّ سوقٍ يلتقي فيه راكبٌ بكبتنٍ خارج
   التوزيع: المشاركة، والمشوارُ الثابت، والحجزُ المضمون، وبين المدن). **والافتراضُ «حقيقيّ»**: بابٌ نسي أن يمرّر الوسمَ
   يعامل الطالبَ حقيقيّاً، **فلا يرى كبتنَ تجربةٍ أبداً** — والخطأُ في الاتجاه الآمن.
٢. **الاستثناءُ من العدّ** — `real_user` و`real_driver` و`real_ride`: شروطُ SQL بـ`NOT EXISTS` مرتبطةٌ بالعمود الذي يُسأل
   عنه، **بأسماءٍ مستعارةٍ لا بالجدول نفسِه** — فاستعلامٌ يضمّ `users` أصلاً لا يربط الشرطَ بصفِّه هو خطأً.
٣. **المال** — `require_real_money` تردّ الأبوابَ التي يدخلها مالٌ حقيقيّ أو يخرج منها **باسمها**، و`is_test_*` تُتخطّى بها
   المكافآتُ التي يدفعها TAXO **صامتةً** (الإحالة · الاسترداد الأسبوعي · حافزُ المشوار · عروضُ الاشتراك · رسمُ إلغاءٍ تتحمّله
   الشركة) — **فلا يُخلق مالٌ ولا يُردّ أحدٌ عن شيءٍ لم يطلبه**. **ولا يعبر رسمُ إلغاءٍ بين عالمين** (`cancellation.try_collect`).

**ولا قفلَ هنا ولا كتابة**: قراءاتٌ وشروطٌ وحدَها — **فلا موضعَ لها في ترتيب الأقفال**، والأبوابُ التي تستعيرها تأخذ
أقفالَها كما كانت.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ColumnElement, and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.exceptions import NoRealMoneyOnTestAccount
from app.models.driver import Driver
from app.models.ride import Ride
from app.models.user import User

#: **علامةُ التصحيح** — تتقدّم مرجعَ كلِّ تصحيحٍ في محفظة حساب تجربة (`adjustment_reference`)،
#: **فمن يقرأ الدفترَ بعد شهرٍ يعرف من أين جاء الرصيدُ بلا أن يسأل**.
TEST_ADJUSTMENT_MARK = "تصحيحُ تجربة"

#: طولُ عمود المرجع في الدفتر (`wallet_transactions.reference`) — والعلامةُ لا تُقصّ أبداً، يُقصّ ما بعدها
_REFERENCE_MAX = 120


# --------------------------------------------------------------- الاستثناءُ من العدّ


def real_user(user_id: ColumnElement) -> ColumnElement[bool]:
    """**صاحبُ هذا المعرّف ليس حسابَ تجربة** — شرطٌ مرتبطٌ بالعمود.

    **`NOT EXISTS` لا `NOT IN`**: عمودٌ فارغٌ (`NULL`) تحت `NOT IN` ليس صدقاً ولا كذباً فيُسقط صفَّه صامتاً، وهنا يبقى.
    **وبجدولٍ مستعار**: استعلامٌ يضمّ `users` أصلاً (كأفضل الكباتن) لا يجوز أن يربط الشرطُ نفسَه بصفِّه هو.
    """
    tester = aliased(User)
    return ~(
        select(tester.id)
        .where(tester.id == user_id, tester.is_test.is_(True))
        .exists()
    )


def real_driver(driver_id: ColumnElement) -> ColumnElement[bool]:
    """**الكبتنُ صاحبُ هذا المعرّف ليس حسابَ تجربة** — و`NULL` (رحلةٌ بلا كبتن) يبقى."""
    driver = aliased(Driver)
    tester = aliased(User)
    return ~(
        select(driver.id)
        .join(tester, tester.id == driver.user_id)
        .where(driver.id == driver_id, tester.is_test.is_(True))
        .exists()
    )


def real_ride() -> ColumnElement[bool]:
    """**رحلةٌ لا يمسّها حسابُ تجربةٍ من طرفيها** — والطرفان يُسألان معاً.

    العزلُ يمنع اليومَ رحلةً بين عالمين، **لكن العدَّ لا يتّكئ عليه**: صفٌّ كُتب قبل الوسم (كبتنُ تجربةٍ أخذ رحلةً حقيقيّةً
    قبل أن يُوسَم) يبقى في القاعدة، **وشرطٌ على أحد الطرفين وحدَه يُدخله رقمَ المالك**.
    """
    return and_(real_user(Ride.rider_id), real_driver(Ride.driver_id))


# --------------------------------------------------------------------- القراءات


async def is_test_user(session: AsyncSession, user_id: uuid.UUID | None) -> bool:
    """أحسابُ تجربةٍ هذا؟ — **و`None` حقيقيّ** (لا حسابَ يُسأل عنه، فلا وسمَ يُقرأ)."""
    if user_id is None:
        return False
    return bool(await session.scalar(select(User.is_test).where(User.id == user_id)))


async def is_test_driver(session: AsyncSession, driver_id: uuid.UUID | None) -> bool:
    """أكبتنُ تجربةٍ هذا؟ — **الوسمُ على الحساب لا على صفِّ الكبتن**، كدولته."""
    if driver_id is None:
        return False
    return bool(
        await session.scalar(
            select(User.is_test)
            .join(Driver, Driver.user_id == User.id)
            .where(Driver.id == driver_id)
        )
    )


async def marked_driver_ids(session: AsyncSession) -> set[uuid.UUID]:
    """كباتنُ التجربة — **لما يُعدّ من Redis لا من القاعدة** (المتصلون الآن): الفهرسُ الجغرافيُّ لا يعرف الوسم.

    **والجوابُ صفٌّ أو اثنان** يقرؤهما الفهرسُ الجزئيُّ `ix_users_is_test` — فطرحُهما من عدِّ الحاضرين لا يكلّف شيئاً.

    **والاسمُ لا يبدأ بـ`test`** بقصد: `pytest` يجمع كلَّ دالّةٍ تبدأ به في وحدةِ اختبارٍ استوردتها، فيشغّلها اختباراً.
    """
    return set(
        await session.scalars(
            select(Driver.id)
            .join(User, User.id == Driver.user_id)
            .where(User.is_test.is_(True))
        )
    )


# ------------------------------------------------------------------------- المال


def require_real_money(user: User | None, message: str | None = None) -> None:
    """**يردّ حسابَ التجربة عن بابٍ يُدخل مالاً حقيقيّاً أو يُخرجه** — بنصٍّ يسمّي الباب إن مُرِّر.

    **ويُنادى عند الباب قبل أيِّ أثر**: قبل فتح طلبٍ عند المزوّد، وقبل كتابة صفّ — فلا يبقى طلبٌ معلّقٌ عند Telr لحسابٍ
    لا يُقبل مالُه، ولا صفٌّ ينتظر مشرفاً لن يؤكّده.
    """
    if user is not None and user.is_test:
        raise NoRealMoneyOnTestAccount(message)


def adjustment_reference(user: User, reason: str) -> str:
    """**مرجعُ التصحيح كما يُكتب في الدفتر** — موسوماً «تصحيحُ تجربة» لحساب التجربة.

    **ولمَ يُوسَم ولا يُشترط**: بابُ التصحيح القائم يشترط سبباً (`AdjustmentCreate.reason`)، **والعلامةُ تُضاف إليه لا تحلّ
    محلَّه** — فيبقى ما كتبه المشرفُ مقروءاً، ويعرف قارئُ الدفتر أن هذا الرصيدَ ليس مالاً حقيقيّاً **بلا أن يتذكّر المشرفُ
    أن يكتبها**. **والحسابُ الحقيقيُّ يُكتب سببُه كما هو حرفاً.**
    """
    text = reason.strip()
    if not user.is_test or text.startswith(TEST_ADJUSTMENT_MARK):
        return text[:_REFERENCE_MAX]
    marked = f"{TEST_ADJUSTMENT_MARK} — {text}" if text else TEST_ADJUSTMENT_MARK
    return marked[:_REFERENCE_MAX]
