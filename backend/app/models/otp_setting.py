"""سقوفُ طلب رمز التحقق لدولةٍ واحدة (قرارُ المالك 2026-08-16).

**والسقفُ سياسةُ حسابٍ لا خاصيةُ قناة**: يُقاس على **الرقم المطلوب** أيّاً كانت
القناة التي يُرسل بها الرمز — واتساب أو رسائل قصيرة. فمن استنفد محاولاته لا
يلتفّ عليها بتبديل القناة، ومن بدّل القناة لعطبٍ في الأولى لا يُعاقَب مرتين.

**وثلاثةُ سقوفٍ لا واحد**، وكلٌّ منها يمنع شيئاً لا يمنعه الآخر:

| السقف | يمنع |
|---|---|
| **نافذةٌ قصيرة** (٥ في الساعة) | الرشقَ الآليَّ على رقمٍ واحد |
| **يوميّ** (١٠) | من يعاود كلَّ ساعةٍ طوالَ اليوم |
| **عمرُ التسجيل** (١٠) | **من لا يُسجِّل أصلاً** — والتسجيلُ حدثٌ مرةً لا حدثٌ متكرر |

والثالثُ هو الذي لا يُشترى بالانتظار: من طلب عشرةَ رموزٍ على رقمٍ ولم يُكمل
تسجيلاً مرةً واحدة، ليس مستخدماً متعثّراً — وانتظارُه يوماً لا يجعله كذلك.

**ومهلةُ الإعادة تتزايد** (٣٠ث ← دقيقة ← دقيقتان…) بدل ثابتٍ واحد: الأولى
تُعالج ضغطةً مكرّرة، والعاشرةُ تُعالج آلة. **والسقفُ عليها** كي لا تبلغ ساعةً
فتصير منعاً دائماً بلا أن يقرّره أحد.

**وكلُّها أرقامٌ في اللوحة لا ثوابتُ في الكود**: سوقٌ ترتفع فيه كلفةُ الرسالة
يضيّق، وسوقٌ جديدٌ يوسّع — ورقمٌ في الكود يعني نشراً لكل تعديل.
"""

from __future__ import annotations

from sqlalchemy import Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, pg_enum
from app.models.enums import CountryCode

# **الافتراضاتُ محافظةٌ عمداً وليست صفراً**: هذه سقوفٌ **حارسة** لا ميزةٌ
# تُفتح، وغيابُ ضبطٍ لها يجب أن يحمي لا أن يفتح — قاعدةُ
# `DEFAULT_ENABLED_FLAGS` نفسُها من الجهة الأخرى. **والصفرُ هنا يعني «لا سقف»**
# ويُكتب صراحةً، فلا يقع الانفتاحُ بالسكوت
DEFAULT_WINDOW_MINUTES = 60
DEFAULT_MAX_PER_WINDOW = 5
DEFAULT_MAX_PER_DAY = 10
DEFAULT_MAX_PER_REGISTRATION = 10
DEFAULT_LOCKOUT_MINUTES = 60
DEFAULT_RESEND_BASE_SECONDS = 30
DEFAULT_RESEND_MAX_SECONDS = 600


class OtpSetting(TimestampMixin, Base):
    """سقوفُ الرمز لدولةٍ واحدة — **ولا حقلَ لقناةٍ هنا**.

    القناةُ تُقرَّر في `services/verification.py`، وهذه سياسةُ الحساب: خلطُهما
    يجعل من يبدّل القناةَ يبدّل سقفَه معها، وهو بابُ الالتفاف الوحيد على سقفٍ
    يُقاس على الرقم.
    """

    __tablename__ = "otp_settings"

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), primary_key=True
    )

    # النافذةُ القصيرة
    window_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text(str(DEFAULT_WINDOW_MINUTES))
    )
    max_per_window: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text(str(DEFAULT_MAX_PER_WINDOW))
    )
    # اليوميّ — **نافذةٌ متدحرجةٌ لا يومُ تقويم**: منتصفُ الليل ليس عفواً عاماً،
    # ومن رشق في الحادية عشرة يبدأ من جديد بعد ساعة
    max_per_day: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text(str(DEFAULT_MAX_PER_DAY))
    )
    # عمرُ التسجيل — يُصفَّر **بإنشاء الحساب** لا بمرور الوقت
    max_per_registration: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text(str(DEFAULT_MAX_PER_REGISTRATION)),
    )
    # الانتظارُ بعد الاستنفاد — ويُقال للمستخدم برقمه لا بجملةٍ عامة
    lockout_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text(str(DEFAULT_LOCKOUT_MINUTES))
    )

    # مهلةُ الإعادة: تبدأ من الأساس وتتضاعف حتى السقف
    resend_base_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text(str(DEFAULT_RESEND_BASE_SECONDS))
    )
    resend_max_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text(str(DEFAULT_RESEND_MAX_SECONDS))
    )
