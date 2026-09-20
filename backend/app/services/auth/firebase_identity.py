"""إثبات ملكية رقمٍ برمز هوية Firebase (المرحلة 8-ب).

**تحقّقٌ لا دخول**: ما كان `FirebaseOtpStrategy` صار دالةً واحدة يستدعيها
`services/verification.py` في الحدثين اللذين يحتاجان إثباتاً — التسجيل
واستعادة كلمة المرور. ولا يُصدر هذا الملف توكناً ولا يفتح جلسة: يقول «نعم،
صاحب الطلب يملك هذا الرقم» أو يرفع خطأً.

قسمةُ العمل: التطبيق يتحقق من الرقم عند Firebase (رسالةٌ وrecaptcha وإعادةُ
إرسال — كلها عندهم)، ويرسل إلينا رمز الهوية. ونحن نتحقق من الرمز.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.phone import mask_phone
from app.services.firebase_auth import InvalidIdToken, VerifiedIdentity, get_verifier

logger = logging.getLogger(__name__)


async def verify_phone_ownership(
    session: AsyncSession, *, phone: str, id_token: str
) -> VerifiedIdentity:
    """يتحقق من الرمز ويطابق هاتفه بالهاتف المقصود.

    **المطابقة شرطٌ لا زينة**: بغيرها يرسل من يملك رقماً رمزَه الصحيح مع
    هاتفِ غيره فيثبت ملكيةً ليست له — والرمز صحيحٌ فعلاً، وهذا بالضبط ما
    يجعل الثغرة غير مرئية في السجل. والصيغتان E.164 كلتاهما: ما تُصدره
    Firebase وما يخزّنه `users.phone` (SPEC القسم 4)، فالمقارنة نصّية مباشرة
    بلا تطبيعٍ ثانٍ يُدخل احتمال اختلاف.
    """
    verifier = await get_verifier(session)
    identity = await verifier.verify(id_token)

    if identity.phone != phone:
        # **الرقمان محجوبان والحدثُ باقٍ** (2026-09-20): كان السطرُ يطبع
        # الرقمين كاملين، **ورقمُ الهاتف هو مُعرِّفُ الدخول** في هذا النظام —
        # فكان سجلُّ الحاوية يحمل مُعرِّفَي حسابين في كلِّ مرّةٍ يقع فيها هذا.
        # و`provider_uid` يبقى عارياً: **هو مُعرِّفُ Firebase نفسِه**، وهو ما
        # يُسلَّم إلى دعمهم، ولا يُقرأ رقمَ هاتف.
        logger.warning(
            "رمز Firebase لرقم %s استُعمل لرقم %s (uid=%s)",
            mask_phone(identity.phone),
            mask_phone(phone),
            identity.provider_uid,
        )
        raise InvalidIdToken("رمز التحقق لا يخص هذا الرقم")

    return identity
