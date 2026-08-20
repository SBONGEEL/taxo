"""سياسةُ دخول اللوحة — قراءتُها وكتابتُها (SPEC القسم 14.1، المرحلة 12-د).

الموضعُ الوحيد الذي يجيب عن ثلاثة أسئلة، وكلُّها تُسأل في مسارٍ حارّ:

1. **هل الإلزام مشتعل؟** (`core/deps` يسأله في كل طلبٍ إداريّ)
2. **كم مهلةُ الخمول؟** (يسألها كلُّ إصدارِ توكنٍ لطاقم اللوحة)
3. **هل يجوز إشعال الإلزام الآن؟** (شرطُ المالك: بعد إثبات الاسترداد)

**والغيابُ يُقرأ بالافتراضات ولا يُبذَر صفٌّ**: صفٌّ مبذورٌ لا يضيف إلا موضعاً
ثانياً تُكتب فيه الافتراضاتُ فيفترق عن الكود يوماً. والصفُّ يُنشأ عند أول كتابة.

**والسقفُ الأقصى للمهلة في الكود لا في يد المشرف**: اللوحة تفتح مفاتيح
المزوّدين والدفع، فمهلةٌ يوسّعها مشرفٌ إلى يومٍ تُبطل الحارسَ من داخله. والحدُّ
مكتوبٌ في `models/security_setting.py` ومحروسٌ في القاعدة بـCHECK أيضاً — طبقةُ
Pydantic تردّ المدخل، والقاعدةُ تردّ كلَّ ما لم يمرّ منها.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import TotpRecoveryProofRequired
from app.models.enums import UserRole
from app.models.security_setting import (
    DEFAULT_IDLE_TIMEOUT_MINUTES,
    MAX_IDLE_TIMEOUT_MINUTES,
    MIN_IDLE_TIMEOUT_MINUTES,
    SecuritySetting,
)
from app.models.user import User
from app.services import totp

# أدوارُ اللوحة — ومهلةُ الخمول لها وحدها: راكبٌ يُخرَج من تطبيقه كل نصف ساعة
# يفقد التطبيق، ولا يفتح تطبيقُه مفتاحَ مزوّدٍ ولا طلبَ سحب
STAFF_ROLES: frozenset[UserRole] = frozenset({UserRole.ADMIN, UserRole.SUPPORT})


async def get(session: AsyncSession) -> SecuritySetting | None:
    """الصفُّ إن وُجد — و`None` تعني «الافتراضات» لا «عطلاً»."""
    return await session.scalar(select(SecuritySetting).limit(1))


async def totp_required_for(session: AsyncSession, user: User) -> bool:
    """هل يُلزَم صاحبُ هذا الحساب بعاملٍ ثانٍ؟

    **المفتاحُ للـ`admin`** (قرارُ المالك): `support` تسجيلُه اختياريٌّ اليوم،
    وجعلُه إلزامياً حقلٌ ثانٍ في الجدول لا بناءٌ جديد — ولا يُضاف قبل أن يُطلب.
    وحينَ يُسجّل `support` عاملاً فهو يعمل عليه: العاملُ المؤكَّد يسري على صاحبه
    أيّاً كان دورُه، والمفتاحُ يقرّر مَن **يُلزَم** لا مَن يُسأل.
    """
    if not user.has_role(UserRole.ADMIN):
        return False

    # **وحسابُ الطوارئ لا يُلزَم مهما كان المفتاح** (قرارُ المالك 2026-08-20).
    #
    # وإلا صار العاملُ الثاني **هو ما يقفل بابَ الطوارئ**: الحسابُ الثاني موجودٌ
    # ليُفتح حين يضيع جهازُ الأول، فاشتراطُ جهازٍ عليه يجعله يحتاج ما وُجد
    # ليعوّضه. وهو نفسُ منطقِ `totp_reset` — بابٌ خارج القاعدة هو ما يجعل
    # الإلزامَ ممكناً أصلاً.
    #
    # **وثمنُه معلوم**: الطوارئُ يبقى على كلمةٍ واحدة — ولذلك **كلُّ دخولٍ به
    # يُكتب في التدقيق** (`admin_break_glass_login`)، فهو مكشوفٌ لا محميّ.
    from app.services import admin_credentials

    credential = await admin_credentials.for_user(session, user.id)
    if credential is not None and credential.is_break_glass:
        return False

    row = await get(session)
    return bool(row and row.admin_totp_required)


async def idle_timeout_minutes(session: AsyncSession) -> int:
    row = await get(session)
    return row.admin_idle_timeout_minutes if row else DEFAULT_IDLE_TIMEOUT_MINUTES


async def refresh_ttl_for(session: AsyncSession, user: User) -> int | None:
    """عمرُ مفتاح الـrefresh لهذا الحساب — و`None` تعني «المدّة المعتادة».

    **الطبقةُ الأولى من مهلة الخمول**: يُكتب المفتاح بهذا العمر ويُجدَّد عند كل
    تدوير، فالتدويرُ لمرةٍ واحدة (القائمُ أصلاً) هو نبضةُ النشاط نفسُها — لا
    عمودُ «آخرِ نشاط» ولا مؤقّتٌ ثانٍ يمكن أن يخالفه. وما تملكه هذه الطبقة أن
    **توكنَ تجديدٍ مسروقاً يبطل بعد نصف ساعة**؛ أما التبويبُ المتروك على مكتبٍ
    فتملكه اللوحةُ وحدها (القسم 14.1).
    """
    if not user.has_role(*STAFF_ROLES):
        return None
    return await idle_timeout_minutes(session) * 60


async def ensure_factor_ready(session: AsyncSession, user: User) -> None:
    """يرفع `TotpEnrollmentRequired` على مشرفٍ مُلزَمٍ بلا عاملٍ مؤكَّد.

    يُقرأ في كل طلبٍ إداريّ كما يُقرأ `is_blocked` — فالإلزامُ يسري على جلسةٍ
    قائمة لحظةَ إشعاله، ولا مطالبةٌ تعيش في توكنٍ لا يمكن إبطالُه. والاستعلامُ
    واحدٌ في الحالة الغالبة: المفتاحُ مطفأٌ فلا يُسأل عن العامل أصلاً.
    """
    from app.core.exceptions import TotpEnrollmentRequired

    if not await totp_required_for(session, user):
        return
    if await totp.has_confirmed_factor(session, user.id):
        return
    raise TotpEnrollmentRequired()


async def update(
    session: AsyncSession,
    *,
    actor: User,
    admin_totp_required: bool | None = None,
    admin_idle_timeout_minutes: int | None = None,
) -> tuple[SecuritySetting, list[str]]:
    """يكتب السياسة ويعيد (الصف، ما تغيّر فعلاً) — القيدُ والـcommit للراوتر.

    **وإشعالُ الإلزام مشروطٌ بإثبات استردادٍ حقيقيّ** على **المشرف الطالب
    نفسِه** (قرارُ المالك: «لا تُلزم أحداً قبل أن أُثبت أن الاسترداد يعمل»):
    عاملٌ مؤكَّدٌ و`recovery_codes_verified_at` مختوم. وبغير هذا الشرط يكون أوّلُ
    من يُقفَل خارج اللوحة هو من أشعل المفتاح، ولا بابَ داخلها يُطفئه.
    """
    row = await get(session)
    if row is None:
        row = SecuritySetting()
        session.add(row)
        await session.flush()

    changed: list[str] = []

    if (
        admin_idle_timeout_minutes is not None
        and admin_idle_timeout_minutes != row.admin_idle_timeout_minutes
    ):
        if not (
            MIN_IDLE_TIMEOUT_MINUTES
            <= admin_idle_timeout_minutes
            <= MAX_IDLE_TIMEOUT_MINUTES
        ):
            from app.core.exceptions import InvalidInput

            raise InvalidInput(
                f"مهلة الخمول بين {MIN_IDLE_TIMEOUT_MINUTES} و"
                f"{MAX_IDLE_TIMEOUT_MINUTES} دقيقة"
            )
        row.admin_idle_timeout_minutes = admin_idle_timeout_minutes
        changed.append("admin_idle_timeout_minutes")

    if (
        admin_totp_required is not None
        and admin_totp_required != row.admin_totp_required
    ):
        if admin_totp_required:
            record = await totp.get_record(session, actor.id)
            if record is None or not record.is_confirmed:
                raise TotpRecoveryProofRequired(
                    "سجّل تحققك الثنائي أولاً ثم أثبت رمز الاسترداد"
                )
            if not record.recovery_verified:
                raise TotpRecoveryProofRequired()
        row.admin_totp_required = admin_totp_required
        changed.append("admin_totp_required")

    return row, changed
