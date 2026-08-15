"""حالُ سدادِ رحلةٍ واحدة — **جوابٌ واحدٌ تقرؤه الشاشاتُ الأربع**.

**العطبُ الذي وُجد لأجله**: أربعُ شاشاتٍ كانت تجيب سؤالاً واحداً بحسابٍ خاصٍّ
بها — شاشةُ دفع الراكب، وسجلُّ الرحلات عنده، وسجلُّ الكبتن، وجدولُ اللوحة —
فأخطأت ثلاثٌ منها بثلاث طرق:

* `outstanding <= 0` تُقرأ «سُدِّدت»، و`pending` **داخلَ**
  `OWING_PAYMENT_STATUSES` — فكتبت الشاشةُ «اكتمل دفع هذه الرحلة، شكراً لك»
  بالأخضر وتحتها بسطرين «كاش ٢٫٤٨١ بانتظار التأكيد». والسؤالان مختلفان:
  الخلفيةُ تسأل «أأفتح صفَّ دفعٍ جديد؟» والراكبُ يسأل «أعليَّ شيءٌ بيدي؟».
* ورحلةٌ **ملغاة** بلا أجرةٍ نهائية كان `outstanding` فيها صفراً، فقالت
  الشاشةُ إن دفعَها اكتمل — ودفعٌ لم يقع لا يكتمل.
* ومقارنةُ `paid_amount` بالأجرة في السجلَّين لا ترى نزاعاً مفتوحاً أصلاً.

**والدواءُ واحدٌ لا ثلاثة**: يُحسب الحالُ هنا مرةً، ويُنشر حقلاً
(`settlement`)، وتُحذف الحسابات من الشاشات. وهي قاعدةُ القسم 14 نفسُها:
قرارٌ ماليٌّ يُتخذ في الخلفية، والواجهةُ تعرض.

**وما يجعله يصمد لحالةٍ رابعة**: `_STATUS_ROLE` **خريطةٌ كليّةٌ** على
`PaymentStatus` — كلُّ عضوٍ فيها بدورٍ صريح، و`role_of` يرمي على عضوٍ لم
يُصنَّف. فقيمةٌ تُضاف يوماً إلى التعداد بلا قرارٍ في أيِّ الأدوار تسقط في
`tests/test_settlement.py` الذي يمرّ على التعداد كلِّه — لا على الثلاثة التي
نعرفها اليوم. وذاك الفرقُ بين حارسٍ يعيش وحارسٍ يفوته أولُ تغيير.

**ولا يقرأ حالةَ الرحلة، بل ما استحقّ عليها**: رحلةٌ ملغاة اليوم لا مستحقَّ
عليها فحالُها `not_due`، ورسمُ الإلغاء حين يُبنى (`design/CANCELLATION-FEE.md`)
يجعل المستحقَّ رسماً — فيجيب هذا الملفُّ عنها بلا سطرٍ جديد.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from app.models.enums import PaymentStatus

ZERO = Decimal("0.000")


class SettlementState(StrEnum):
    """حالُ سدادِ الرحلة كما يُقرأ على شاشة.

    خمسُ قيمٍ لا اثنتان، لأن «غيرُ مسدَّدة» وحدَها تجمع ثلاثةَ مواقفَ يفترق
    فيها ما يفعله من يقرأ: من عليه أن يدفع، ومن دفع وينتظر تأكيدَ الآخر، ومن
    في رحلته نزاعٌ مفتوح.
    """

    # لا مستحقَّ على هذه الرحلة أصلاً: لم تنتهِ بعد، أو ملغاةٌ بلا رسم
    NOT_DUE = "not_due"
    # عليها مبلغٌ لم يُفتح له صفُّ دفع — زرُّ «ادفع» هنا
    DUE = "due"
    # لا شيءَ يُبدأ، وما فُتح ينتظر تأكيداً — يُسمّى المبلغُ وقناتُه بلا شكر
    AWAITING = "awaiting"
    # فيها نزاعٌ مفتوح — لا «بانتظار التأكيد» ولا «اكتمل»
    DISPUTED = "disputed"
    # تأكّد ما يغطّي المستحق
    SETTLED = "settled"


class _Role(StrEnum):
    """دورُ صفِّ الدفع في المستحق — لا حالتُه المعروضة."""

    # يحجز المبلغَ ولم يصل بعد
    HOLDS = "holds"
    # وصل المال
    PAID = "paid"
    # يحجز المبلغَ وعليه خلاف
    CONTESTED = "contested"
    # يُفرِج عن المبلغ فيجوز فتحُ صفٍّ جديد بقيمته
    RELEASES = "releases"


# **خريطةٌ كليّة**: كلُّ عضوٍ في `PaymentStatus` له دورٌ مكتوب. وهي المكانُ
# الوحيدُ الذي يُقرَّر فيه معنى حالةِ دفعٍ في السداد — ومقابلُها في القاعدة
# `OWING_PAYMENT_STATUSES` (كلُّ ما ليس `RELEASES`).
_STATUS_ROLE: dict[PaymentStatus, _Role] = {
    PaymentStatus.PENDING: _Role.HOLDS,
    PaymentStatus.CONFIRMED: _Role.PAID,
    PaymentStatus.DISPUTED: _Role.CONTESTED,
    PaymentStatus.FAILED: _Role.RELEASES,
    PaymentStatus.REFUNDED: _Role.RELEASES,
}


def role_of(status: PaymentStatus) -> _Role:
    """دورُ الحالة — **ويرمي على حالةٍ لم تُصنَّف**.

    السكوتُ هنا أسوأُ من الرمي: حالةٌ تُضاف ولا تُصنَّف ستُعامَل صامتةً
    معاملةَ «تُفرِج عن المبلغ»، فتُقرأ رحلةٌ عليها مالٌ رحلةً بلا مستحق.
    """
    try:
        return _STATUS_ROLE[status]
    except KeyError as error:  # pragma: no cover — يمنعه الاختبار قبل النشر
        raise AssertionError(
            f"حالةُ دفعٍ بلا دورٍ في السداد: {status!r} — صنّفها في _STATUS_ROLE"
        ) from error


class _PaymentRow(Protocol):
    """ما يحتاجه الحساب من صفِّ الدفع — لا أكثر، فيصلح للنموذج وللصفِّ المجرّد."""

    status: PaymentStatus
    amount: Decimal


def held_amount(payments: Iterable[_PaymentRow]) -> Decimal:
    """ما تشغله الصفوفُ القائمة من المستحق (المؤكَّدُ والمنتظِرُ والمتنازَعُ عليه)."""
    return sum(
        (p.amount for p in payments if role_of(p.status) is not _Role.RELEASES),
        ZERO,
    )


def paid_amount(payments: Iterable[_PaymentRow]) -> Decimal:
    """ما وصل فعلاً — وهو وحدَه ما يُقرأ «دُفع»."""
    return sum(
        (p.amount for p in payments if role_of(p.status) is _Role.PAID),
        ZERO,
    )


def state_from_totals(
    *,
    chargeable: Decimal | None,
    held: Decimal,
    paid: Decimal,
    contested: bool,
) -> SettlementState:
    """القرارُ نفسُه من مجاميعَ محسوبةٍ في القاعدة.

    **بابان إلى قرارٍ واحد لا قراران**: شاشةُ الدفع تملك الصفوفَ فتمرّ
    بـ`state_for`، وسجلُّ الرحلات يجمعها في استعلامٍ واحد لصفحةٍ كاملة
    (`ride_log.payment_summaries`) فيمرّ بهذه — ولو كُتب الترتيبُ مرتين
    لافترقت الشاشتان في أول تعديل.
    """
    if chargeable is None or chargeable <= ZERO:
        return SettlementState.NOT_DUE
    if contested:
        return SettlementState.DISPUTED
    if paid >= chargeable:
        return SettlementState.SETTLED
    if held >= chargeable:
        return SettlementState.AWAITING
    return SettlementState.DUE


def state_for(
    *, chargeable: Decimal | None, payments: Iterable[_PaymentRow]
) -> SettlementState:
    """حالُ سدادِ رحلةٍ من مستحقِّها وصفوفِ دفعها.

    `chargeable` هو ما استحقَّ على الرحلة: الأجرةُ النهائية لرحلةٍ انتهت،
    ورسمُ الإلغاء لرحلةٍ أُلغيت بعد القبول، و`None` لرحلةٍ لم يستحقَّ عليها
    شيءٌ بعد. **ولا تُقرأ حالةُ الرحلة هنا**: المستحقُّ هو السؤال، وحالتُها
    طريقٌ إليه يتغيّر — كما تغيّر برسم الإلغاء.
    """
    rows = list(payments)
    return state_from_totals(
        chargeable=chargeable,
        held=held_amount(rows),
        paid=paid_amount(rows),
        contested=any(role_of(p.status) is _Role.CONTESTED for p in rows),
    )


class _RideRow(Protocol):
    """ما يُقرأ من الرحلة لمعرفة مستحقِّها."""

    final_fare: Decimal | None
    cancellation_fee: Decimal | None


def chargeable_of(ride: _RideRow) -> Decimal | None:
    """ما استحقَّ على الرحلة — **مكانٌ واحدٌ يُسأل فيه هذا السؤال**.

    الأجرةُ النهائية تُكتب عند الإنهاء، ورسمُ الإلغاء عند الإلغاء بعد القبول،
    ولا يجتمعان على رحلة. ورحلةٌ جارية أو ملغاةٌ قبل القبول لا مستحقَّ عليها،
    فتُقرأ `None` — لا صفراً: الصفرُ رقمٌ يُجمع ويُقارن، و«لا شيء» ليس رقماً.
    """
    if ride.final_fare is not None:
        return ride.final_fare
    return ride.cancellation_fee
