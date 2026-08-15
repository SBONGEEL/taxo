"""حالُ السداد — **اختبارٌ يمرّ على التعداد كلِّه، لا على قيمِه اليوم**.

طلبُ المالك حرفياً: «اختباراً يثبت أن حالة رابعة تُضاف يوماً لا تكسرها، لا
اختباراً يعدّ الثلاث الحالية». فالفرقُ هنا ليس في عدد الحالات المذكورة بل في
**مصدرها**: كلُّ ما يلي يشتقّ من `PaymentStatus` نفسِه، فقيمةٌ سادسةٌ تُضاف
غداً تدخل هذه الاختبارات تلقائياً وتسقط حتى تُصنَّف في `_STATUS_ROLE`.

ولا يحتاج قاعدةَ بيانات: `state_for` دالّةٌ صِرفة، وصفُّ الدفع عندها بروتوكولٌ
لا نموذج.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from app.models.enums import PaymentStatus
from app.models.payment import OWING_PAYMENT_STATUSES
from app.services import settlement
from app.services.settlement import SettlementState, state_for

FARE = Decimal("10.000")


@dataclass(slots=True)
class Row:
    status: PaymentStatus
    amount: Decimal


@pytest.mark.parametrize("status", list(PaymentStatus))
def test_every_payment_status_carries_a_role(status: PaymentStatus) -> None:
    """كلُّ عضوٍ في التعداد مصنَّف — وحالةٌ تُضاف بلا تصنيفٍ تُسقط هذا."""
    assert settlement.role_of(status) in set(settlement._Role)


@pytest.mark.parametrize("status", list(PaymentStatus))
def test_a_single_row_covering_the_fare_lands_in_a_named_state(
    status: PaymentStatus,
) -> None:
    """رحلةٌ بصفٍّ واحدٍ يغطّي الأجرة: لكلِّ حالةٍ جوابٌ صريح، ولا استثناء.

    والمقارنةُ بمجموعةِ القاعدة نفسِها (`OWING_PAYMENT_STATUSES`) لا بأسماءٍ
    مكتوبةٍ هنا: هما جوابان لسؤالٍ واحد — «أيشغل هذا الصفُّ المبلغَ؟» —
    فافتراقُهما عطبٌ في المال قبل أن يكون عطباً في الشاشة.
    """
    state = state_for(chargeable=FARE, payments=[Row(status, FARE)])
    occupies = status in OWING_PAYMENT_STATUSES
    assert (state is not SettlementState.DUE) is occupies


@pytest.mark.parametrize("status", list(PaymentStatus))
def test_the_role_map_agrees_with_the_database_grouping(
    status: PaymentStatus,
) -> None:
    """`RELEASES` ⇔ خارجَ `OWING_PAYMENT_STATUSES` — مصدرٌ واحدٌ لمفهومٍ واحد."""
    releases = settlement.role_of(status) is settlement._Role.RELEASES
    assert releases is (status not in OWING_PAYMENT_STATUSES)


def test_a_confirmed_row_settles_and_a_pending_one_does_not() -> None:
    """العطبُ الذي وُجد الملفُّ لأجله: `pending` ليست «اكتمل الدفع»."""
    assert (
        state_for(chargeable=FARE, payments=[Row(PaymentStatus.CONFIRMED, FARE)])
        is SettlementState.SETTLED
    )
    assert (
        state_for(chargeable=FARE, payments=[Row(PaymentStatus.PENDING, FARE)])
        is SettlementState.AWAITING
    )


def test_a_ride_with_nothing_owed_is_never_settled() -> None:
    """رحلةٌ ملغاةٌ بلا رسم: `not_due` — ودفعٌ لم يقع لا «يكتمل»."""
    assert state_for(chargeable=None, payments=[]) is SettlementState.NOT_DUE
    assert state_for(chargeable=Decimal("0"), payments=[]) is SettlementState.NOT_DUE


def test_a_dispute_outranks_both_paid_and_pending() -> None:
    """نزاعٌ مفتوحٌ لا يُقرأ «بانتظار التأكيد» ولا «اكتمل»."""
    rows = [
        Row(PaymentStatus.CONFIRMED, Decimal("6.000")),
        Row(PaymentStatus.DISPUTED, Decimal("4.000")),
    ]
    assert state_for(chargeable=FARE, payments=rows) is SettlementState.DISPUTED


def test_a_failed_row_frees_the_amount_again() -> None:
    """`failed` تُفرِج: الرحلةُ تعود «عليها دفع» لا «بانتظار»."""
    rows = [Row(PaymentStatus.FAILED, FARE)]
    assert state_for(chargeable=FARE, payments=rows) is SettlementState.DUE


def test_mixed_payment_is_read_from_the_sum_not_the_first_row() -> None:
    """المختلطُ صفّان: نصفٌ مؤكَّدٌ ونصفٌ منتظِرٌ = بانتظار، لا مسدَّدة."""
    rows = [
        Row(PaymentStatus.CONFIRMED, Decimal("6.000")),
        Row(PaymentStatus.PENDING, Decimal("4.000")),
    ]
    assert state_for(chargeable=FARE, payments=rows) is SettlementState.AWAITING
    rows[1].status = PaymentStatus.CONFIRMED
    assert state_for(chargeable=FARE, payments=rows) is SettlementState.SETTLED


def test_a_partly_covered_fare_is_still_due() -> None:
    """ما لم يُغطَّ يبقى «عليها دفع» — والباقي هو ما يفتح له صفٌّ جديد."""
    rows = [Row(PaymentStatus.CONFIRMED, Decimal("6.000"))]
    assert state_for(chargeable=FARE, payments=rows) is SettlementState.DUE
