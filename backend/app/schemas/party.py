"""طرفٌ إنسانٌ في صفِّ لوحة — **بيتٌ واحدٌ لثلاث حمولات** (§٤٧٫١٩، ٢٠٢٦-٠٩-٠٤).

## العلّة: زرُّ «الملفّ» يحتاج معرِّفاً **وما يُضيَّق به**

**نصُّ §39٫١٢٫٤**: «ومن أيِّ صفٍّ يخصّ مستخدماً زرٌّ يفتح ملفَّه مباشرة».
**وثلاثةُ جداولَ لم تُوصَل** يومَ بُني الزرُّ (§٤٧٫١٧) بعلّةٍ مقيسة: **صفرُ
معرّفِ إنسانٍ في أنواع صفوفها** — `PaymentOut` و`WithdrawalOut` تحملان
`ride_id` و`driver_id` ولا تحملان إنساناً باسمه.

**و`driver_id` وحدَه لا يكفي**: لا بابَ يقرأ صفَّ كبتنٍ واحد، **فالدرجُ يُفتح
بمطابقة `drivers.id` داخل القائمة المرشَّحة** — **وقائمةٌ بلا ترشيحٍ تعرض
أوّلَ خمسين**، فمن كان خارجها لا يُفتح ملفُّه أبداً **ولا يصيح شيء**. فالاسمُ
والرقمُ ليسا زينةً: **هما ما يُضيَّق به.**

## ولمَ بيتٌ واحدٌ لا نسخةٌ في كلِّ حمولة

**كانت هذه الأشكالُ تسكن `schemas/admin_ride.py` باسمي `RidePartyOut` و
`RideDriverPartyOut`** — واسمٌ يبدأ بـ`Ride` على صفِّ **طلب صرف** يُقرأ خطأً،
**وثلاثُ تسمياتٍ لشيءٍ واحد** هي بعينها العائلةُ التي أنشأت `Picker` و
`MoneyField` قبلها. **فنُقلت ولم تُنسخ**، وكلُّ من كان يستعملها يستعملها هنا.

## و`of` / `of_driver` — **بانٍ واحدٌ لا حقلٌ يُملأ بيد**

**درسُ البند ٣ بنصِّه**: «المعالجةُ بالبانِي الواحد لا بالحقل» — إصلاحُ الحقل
يترك البابَ الثالثَ بلا شيءٍ يجده غداً. **فمن أضاف حقلاً هنا وصل الأبوابَ
الثلاثةَ معاً**، ولا يبقى بابٌ ينشر نصفَ الطرف.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:  # pragma: no cover - للتلميح فقط
    from app.models.driver import Driver
    from app.models.user import User


class PartyOut(BaseModel):
    """طرفٌ في صفٍّ باسمه ورقمه — **للوحة وحدَها**.

    **ولا يُنشر في تطبيقٍ البتّة**: `PaymentOut` و`WithdrawalOut` يقرؤهما
    الراكبُ والكبتن، **فحقلٌ يحمل اسمَ الطرف الآخر ورقمَه فيهما كشفُ هوية** —
    ولذلك صفوفُ اللوحة أنواعٌ مستقلّةٌ ترث لا حقولٌ تُضاف هناك.
    """

    user_id: uuid.UUID
    name: str
    phone: str

    @classmethod
    def of(cls, user: "User") -> "PartyOut":
        return cls(user_id=user.id, name=user.name, phone=user.phone)


class DriverPartyOut(PartyOut):
    """كبتنٌ — **ومعه `drivers.id`**، وهو ما يفتح به الدرجُ ملفَّه.

    **وخلطُ المعرّفين يفتح ملفَّ إنسانٍ آخر ولا يصيح شيء**: كلاهما UUID،
    **فالحقلان منفصلان بالاسم** — `user_id` للحساب و`driver_id` للكبتن.
    """

    driver_id: uuid.UUID
    #: **اختياريٌّ بقصد**: صفُّ الرحلة يحمل اللوحةَ وصفُّ الصرف لا يحملها،
    #: **ولا تُقحَم لوحةٌ في صفٍّ لا يعرضها** فتصير حقلاً بلا قارئ
    plate_number: str | None = None

    @classmethod
    def of_driver(
        cls, driver: "Driver", *, plate_number: str | None = None
    ) -> "DriverPartyOut":
        return cls(
            user_id=driver.user.id,
            name=driver.user.name,
            phone=driver.user.phone,
            driver_id=driver.id,
            plate_number=plate_number,
        )
