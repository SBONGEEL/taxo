"""**ما يُحذف وما لا يُحذف** — بيتٌ واحدٌ للسؤال (البند ٤، §39٫٤).

## القاعدةُ بنصِّ المالك

**«يشمل كلَّ ما ليس مالاً»** — والمالُ لا يُعدَّل ولا يُحذف: صفوفُ الدفتر
**تُصحَّح بقيدٍ معاكسٍ مسمّى**. **وقائمةُ ما لا يُحذف** مكتوبةٌ في §39٫٤:
الدفترُ · شاهدُ النزاع · سجلُّ التدقيق · الموافقاتُ والسياساتُ المنشورة ·
المستخدمون والكباتن (الإيقافُ **تعليقٌ لا حذف**) · إثباتُ ما أُرسل · **وصفٌّ
عُرض على الناس**.

## والسؤالُ الواحدُ الذي تجيبه هذه الوحدة

**«أرآه أحدٌ أو استعمله؟»** — فإن كان، **يُخفى ولا يُحذف**. وهو مبدأُ
`storefront.require_draft` نفسُه (قرارُ المالك 2026-08-31: «ما عُرض مرّةً
يُخفى ولا يُحذف — حذفُه يمحو شاهداً على ما رآه الناس»)، **موسَّعاً إلى
الكيانات الأربعة الباقية** التي تُنشأ من اللوحة ولا يُحذف منها شيء.

**ولا يُترك للمفتاح الأجنبيّ وحدَه**: `CASCADE` على منح الشارة **يمحو المنحَ
معها صامتاً**، و`RESTRICT` على العرض يرمي `IntegrityError` **برسالةٍ لا يفهمها
المشرف**. **فالسؤالُ يُسأل قبل الحذف، والجوابُ نصٌّ عربيٌّ يقول لماذا.**
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInput
from app.models.badge import Badge, DriverBadge
from app.models.mission import Mission
from app.models.subscription import DriverSubscription
from app.models.subscription_offer import SubscriptionOffer, SubscriptionOfferGrant
from app.models.vehicle_skin import DriverVehicleSkin, VehicleSkin


class InUse(InvalidInput):
    """**استُعمل فلا يُحذف** — والرسالةُ تقول ماذا يُفعل بدلاً منه."""

    code = "row_in_use"


async def _count(session: AsyncSession, column, value) -> int:
    return int(await session.scalar(select(func.count()).where(column == value)) or 0)


async def badge_deletable(session: AsyncSession, badge: Badge) -> None:
    """**شارةٌ مُنحت لأحدٍ لا تُحذف**: `CASCADE` كان سيمحو المنحَ معها.

    **ومنحةٌ ممحوّةٌ تمحو خبراً عن إنسان** — من نالها ومتى.
    """
    granted = await _count(session, DriverBadge.badge_id, badge.id)
    if granted:
        raise InUse(
            f"هذه الشارة مُنحت لـ{granted} من الكباتن ولا تُحذف — "
            "ومحوُها يمحو منحةً نالها إنسان"
        )


async def mission_deletable(
    session: AsyncSession, mission: Mission, *, today: date | None = None
) -> None:
    """**مهمّةٌ بدأ شهرُها لا تُحذف**: كباتنُ يعملون عليها الآن.

    **ولا جدولَ تقدّمٍ يُسأل**: التقدّمُ يُحسب من الرحلات، **فالسؤالُ عن
    الشهر لا عن صفٍّ ثانٍ** — ومهمّةُ شهرٍ لم يبدأ لم يعمل عليها أحد.
    """
    moment = today or date.today()
    if mission.month <= moment.replace(day=1):
        raise InUse(
            "بدأ شهرُ هذه المهمّة ويعمل عليها كباتن — لا تُحذف. أطفئها بدل ذلك"
        )


async def offer_deletable(
    session: AsyncSession, offer: SubscriptionOffer
) -> None:
    """**عرضٌ اشترى به أحدٌ لا يُحذف** — و`RESTRICT` في القاعدة يمنعه أصلاً.

    **لكنّ القاعدةَ ترمي `IntegrityError`**، والمشرفُ يقرأ خطأً لا يفهمه —
    **فالسؤالُ هنا ليجيبَ بالعربية ويقولَ العدد**. وهو ما تقوله وثيقةُ العمود
    نفسِها: «عرضٌ يُحذف بعد أن اشترى به عشرون كبتناً يمحو **سببَ** خصومهم».
    """
    used = await _count(session, DriverSubscription.offer_id, offer.id)
    granted = await _count(session, SubscriptionOfferGrant.offer_id, offer.id)
    if used or granted:
        raise InUse(
            f"استُعمل هذا العرضُ في {used + granted} اشتراكاً أو منحة ولا يُحذف — "
            "ومحوُه يترك خصومَهم أرقاماً بلا سبب. أطفئه بدل ذلك"
        )


async def skin_deletable(session: AsyncSession, skin: VehicleSkin) -> None:
    """**مركبةٌ يملكها أحدٌ لا تُحذف** — ومالٌ خرج من محفظته مقابلها."""
    owned = await _count(session, DriverVehicleSkin.skin_id, skin.id)
    if owned:
        raise InUse(
            f"يملك هذه المركبةَ {owned} من الكباتن ولا تُحذف — "
            "ومنهم من دفع ثمنَها. أخفِها بدل ذلك"
        )
