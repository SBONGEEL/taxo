from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import func
from app.core.exceptions import (
    EmailAlreadyRegistered,
    InvalidInput,
    PhoneAlreadyRegistered,
)
from app.models.driver import Driver
from app.models.enums import AccountKind, UserRole
from app.models.user import User
from app.models.user_role_grant import UserRoleGrant
from app.schemas.auth import RegisterRequest
from app.core.redis_client import get_redis_client
from app.services import otp_limits, referrals

async def create_account(
    session: AsyncSession,
    *,
    phone: str,
    data: RegisterRequest,
    password_hash: str | None,
    phone_verified_at: datetime | None = None,
    email: str | None = None,
    email_verified_at: datetime | None = None,
    phone_pending: bool = False,
    account_kind: AccountKind = AccountKind.TAXO,
) -> User:
    """إنشاء الحساب — البابُ الوحيد، فلا يُكتب المنطق مرتين ليفترق مرتين.

    `phone_verified_at` فارغة تعني رقماً لم يُثبَت: لا تقع إلا حين يُطفئ
    المشرف مفتاح `otp_verification_enabled` للطوارئ (SPEC القسم 4)، ويبقى
    الحساب موسوماً في اللوحة حتى يُثبِت صاحبُه رقمه.
    """
    # **الرقمُ مع نوعِ الحساب** (الترحيلة `0076`، §D9.1): الرقمُ نفسُه يحمل
    # حساباً من كلِّ نوع، والرفضُ لحسابٍ ثانٍ **من النوع نفسِه** وحدَه
    existing = await session.scalar(
        select(User.id).where(User.phone == phone, User.account_kind == account_kind)
    )
    if existing is not None:
        raise PhoneAlreadyRegistered()

    # **والبريدُ المُثبَتُ كذلك** — بلا حساسيةِ حالة، **وللمُثبَت وحدَه**:
    # عنوانٌ كُتب ولم يُثبَت لا يحجز شيئاً، وإلا حجب من كتب بريدَ غيره خطأً
    # **صاحبَه الحقيقيَّ** عن التسجيل به.
    #
    # **والفحصُ هنا والفهرسُ في القاعدة طبقتان لا واحدة**: هذا يعطي الرسالةَ،
    # وذاك يمسك السباقَ بين طلبين متزامنين — **ومن اكتفى بالفهرس أعطى ٥٠٠**،
    # ومن اكتفى بالفحص فتح ثغرةَ تزامن.
    if email is not None:
        taken = await session.scalar(
            select(User.id).where(
                func.lower(User.email) == email.lower(),
                User.email_verified_at.is_not(None),
                User.account_kind == account_kind,
            )
        )
        if taken is not None:
            raise EmailAlreadyRegistered()

    # جنسُ الكبتن لا يُكتب من مسار التسجيل مهما أُرسل — يضبطه المشرف من
    # الهوية ويُختم (`PUT /admin/drivers/{id}/gender`). ولا يُبتلع صامتاً:
    # حقلٌ يُرسَل ويُهمَل يبدو أنه عمل
    if data.gender is not None and UserRole(data.role) is UserRole.DRIVER:
        raise InvalidInput("جنس الكبتن يثبّته المشرف من الهوية، لا يُكتب عند التسجيل")

    # **ورمزُ الإحالة صار مقبولاً على المسارين** (تعميمُ 2026-08-16): كان
    # يُرفض على مسار الراكب لأن الحافزَ كان لجذب السائقات وحدَهن، ورمزٌ يُقبل
    # ثم لا يُسند شيئاً يبدو أنه عمل. **والبرنامجُ يُختار من دور المُسجِّل**،
    # فرمزٌ واحدٌ يعمل في البرنامجين بلا التباس ولا رفضٍ يفهمه صاحبُه خطأً
    # («الرمز غير صحيح» عن رمزٍ صحيح هو ما كان يُقرأ قبله).

    # **وعدّادُ رموز التسجيل يُصفَّر هنا** (`otp_limits`، قرارُ المالك
    # 2026-08-16): السقفُ الثالث يقيس «كم رمزاً طُلب على رقمٍ **بلا أن يُسجَّل
    # به أحد**» — فبإنشاء الحساب زال موضوعُه. **ولا تُمحى النافذةُ ولا
    # اليوميّ**: من سجّل للتوّ لا يُمنح رصيداً جديداً من الرسائل في الدقيقة
    # نفسِها. وموضعُه هذا البابُ وحدَه لأنه بابُ الإنشاء الوحيد
    await otp_limits.clear_for_registration(get_redis_client(), phone)

    user = User(
        phone=phone,
        account_kind=account_kind,
        name=data.name.strip(),
        role=UserRole(data.role),
        country_code=data.country_code,
        password_hash=password_hash,
        phone_verified_at=phone_verified_at,
        # **البريدُ قناةً بديلة** (قرارُ المالك 2026-08-31) — والثلاثةُ تُكتب
        # هنا لا في مسارٍ ثانٍ: **بابُ الإنشاء واحدٌ فلا يُكتب المنطقُ مرتين
        # ليفترق مرتين**، وحسابٌ يُنشأ من بابٍ ثانٍ يفوته تصفيرُ عدّاد الرموز
        # وبناءُ الدور ورمزُ الإحالة — ثلاثةٌ لا يفشل غيابُها بصوت.
        email=email,
        email_verified_at=email_verified_at,
        phone_pending=phone_pending,
        # إعلانُ الراكبة عن نفسها. **بلا ختم**: يقيّد رحلتَها هي لا أمانَ غيرها
        gender=data.gender,
        # **ورمزُ الإحالة لكل حساب** (تعميمُ 2026-08-16)، وموضعُه `users` لا
        # `drivers` لأن الراكبَ لا صفَّ له هناك. وتوليدٌ متأخرٌ عند أول قراءةٍ
        # يحتاج قفلاً على صفٍّ لا يُكتب فيه شيءٌ آخر، وبغيره تُنتج ضغطتان رمزين
        referral_code=referrals.generate_code(),
    )
    # **الدورُ يُبنى مع الحساب لا يُضاف بعد الدفع** (نموذجُ الأدوار 2026-08-19):
    # العمودُ باقٍ، والمجموعةُ هي ما يقرؤه التخويل — وكتابتُهما معاً في معاملةٍ
    # واحدةٍ تمنع حساباً بلا دورٍ في المجموعة، وهو حسابٌ لا يدخل أيَّ تطبيق.
    #
    # **وبناؤُه في المُنشئ لا بـ`session.add` بعد `flush`**: الثاني يترك
    # `role_grants` غيرَ محمَّلةٍ على صفٍّ صار persistent، فأولُ قراءةٍ لها
    # (`programme_for` في `attach` أدناه) تحاول IO خارج السياق — وهو
    # `MissingGreenlet` بعينه، الفخُّ الذي يعرفه هذا المشروع.
    user.role_grants.append(UserRoleGrant(role=user.role))

    session.add(user)
    await session.flush()

    if user.role is UserRole.DRIVER:
        # ملف الكبتن يُنشأ فوراً بحالة pending بانتظار مراجعة المستندات
        session.add(Driver(user_id=user.id))
        await session.flush()

    # الرمزُ الذي جاء به — إن جاء. **والإسنادُ لا يُفحص استحقاقُه هنا**:
    # هذا سجلُّ ما وقع، والاستحقاقُ سؤالٌ يُطرح لاحقاً (SPEC القسم 9.1)
    if data.referral_code:
        # **برنامجُ التطبيق الذي صدرت منه الإحالة** (§22)، يُختم الآن
        await referrals.attach(
            session, referred=user, code=data.referral_code, app=data.app
        )

    return user
