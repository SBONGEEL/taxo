from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInput, PhoneAlreadyRegistered
from app.models.driver import Driver
from app.models.enums import UserRole
from app.models.user import User
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
) -> User:
    """إنشاء الحساب — البابُ الوحيد، فلا يُكتب المنطق مرتين ليفترق مرتين.

    `phone_verified_at` فارغة تعني رقماً لم يُثبَت: لا تقع إلا حين يُطفئ
    المشرف مفتاح `otp_verification_enabled` للطوارئ (SPEC القسم 4)، ويبقى
    الحساب موسوماً في اللوحة حتى يُثبِت صاحبُه رقمه.
    """
    existing = await session.scalar(select(User.id).where(User.phone == phone))
    if existing is not None:
        raise PhoneAlreadyRegistered()

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
        name=data.name.strip(),
        role=UserRole(data.role),
        country_code=data.country_code,
        password_hash=password_hash,
        phone_verified_at=phone_verified_at,
        # إعلانُ الراكبة عن نفسها. **بلا ختم**: يقيّد رحلتَها هي لا أمانَ غيرها
        gender=data.gender,
        # **ورمزُ الإحالة لكل حساب** (تعميمُ 2026-08-16)، وموضعُه `users` لا
        # `drivers` لأن الراكبَ لا صفَّ له هناك. وتوليدٌ متأخرٌ عند أول قراءةٍ
        # يحتاج قفلاً على صفٍّ لا يُكتب فيه شيءٌ آخر، وبغيره تُنتج ضغطتان رمزين
        referral_code=referrals.generate_code(),
    )
    session.add(user)
    await session.flush()

    if user.role is UserRole.DRIVER:
        # ملف الكبتن يُنشأ فوراً بحالة pending بانتظار مراجعة المستندات
        session.add(Driver(user_id=user.id))
        await session.flush()

    # الرمزُ الذي جاء به — إن جاء. **والإسنادُ لا يُفحص استحقاقُه هنا**:
    # هذا سجلُّ ما وقع، والاستحقاقُ سؤالٌ يُطرح لاحقاً (SPEC القسم 9.1)
    if data.referral_code:
        await referrals.attach(session, referred=user, code=data.referral_code)

    return user
