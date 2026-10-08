"""حمولاتُ المدفوعات غير المؤكَّدة — القائمتان عند الفتح وطابورُ الإدارة (`design/PAYMENTS-UNCONFIRMED.md` §٥/§٦، SPEC §٦٤-ج).

**كلُّ حمولةٍ هنا لبابٍ واحد**، وبانيها واحدٌ في موجّهها — فلا حقلَ يُملأ في بابٍ ويُنسى في آخر. **والمالُ نصٌّ بثلاث خانات**
من الصفّ نفسِه (`Decimal` من `NUMERIC(12,3)`)، ولا يُحسب شيءٌ منه في الواجهة (§14).

**ولا يحمل تطبيقٌ اسمَ الطرف الآخر كاملاً ولا رقمَه**: الراكبُ يرى **اسمَ كبتنه كما سيظهر في بنكه** (§٤-٢ — به يطابق قبل
الإرسال) والكبتنُ يرى **الاسمَ الأوّل** للراكب (§٦: «ليلى · أمس 21:58»). **والرقمُ للوحة وحدَها، مقنَّعاً** (§٥).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.enums import (
    Currency,
    DisputeResolution,
    PaymentConfirmedBy,
    PaymentMethod,
    PaymentStatus,
)

#: **سببُ المشرف** — «٨ أحرف على الأقل» (§٥)، ويُحفظ في التدقيق وعلى الصفّ
AdminReason = Field(min_length=8, max_length=255)


class PaymentObjectionRequest(BaseModel):
    """«لم أستلم هذا المبلغ» — سببُ الكبتن مكتوباً، كسبب «لم يصلني» القائم."""

    reason: str = Field(min_length=3, max_length=255)


class AdminReasonRequest(BaseModel):
    reason: str = AdminReason


class AdminUnconfirmedResolveRequest(BaseModel):
    """«احسم: مدفوع» / «احسم: غيرُ مدفوع» — **الواقعةُ لا الحالة** (`DisputeResolution`)، والحالُ تُشتقّ منها في الخدمة."""

    outcome: DisputeResolution
    reason: str = AdminReason


# --------------------------------------------------------------- الراكب (R31)

RiderUnconfirmedState = Literal["awaiting_you", "awaiting_captain", "disputed", "payment_due"]


class RiderUnconfirmedItem(BaseModel):
    """بطاقةُ رحلةٍ لم يكتمل دفعُها — «أمس · 21:58 · الشميساني ← دابوق · الكبتن زيد» و«3.364 د.أ · كاش» (§٦).

    **و`payment_due` بلا صفّ** (`payment_id` و`status` فارغان): الأجرةُ مستحقّةٌ ولا دفعةَ حيّةً عليها — حكمُ «غيرُ مدفوع» أو
    دفعٌ سقط. **زرُّها «ادفع الآن»** على `POST /rides/{ride_id}/payments`، و`amount` المستحقُّ على الرحلة محسوباً في الخلفية.
    """

    #: فارغٌ لـ`payment_due` وحدَها
    payment_id: uuid.UUID | None
    ride_id: uuid.UUID
    #: وقتُ الرحلة — نهايتُها
    completed_at: datetime
    pickup_address: str | None
    dropoff_address: str | None
    #: **اسمُ الكبتن كما سجّله** — «الكبتن زيد» في البطاقة، و«ستظهر في بنكك باسم: …» لكليك (§٤-٢)، فيطابقه الراكبُ قبل أن يرسل
    captain_name: str | None
    amount: Decimal
    currency: Currency
    #: طريقةُ الصفّ — **ولـ`payment_due` الطريقةُ التي اختارها مع الطلب**
    method: PaymentMethod
    #: `awaiting_you` (لم تُقِرّ / بلا مرجع) · `awaiting_captain` («لا يلزمك شيء») · `disputed` · `payment_due` («ادفع الآن»)
    state: RiderUnconfirmedState
    #: فارغٌ لـ`payment_due` وحدَها
    status: PaymentStatus | None
    #: «أقررتَ بالتسليم أمس 22:04» — للكاش
    declared_at: datetime | None
    #: كليك: الاسمُ المستعارُ المجمَّد ومرجعُ TAXO (يُكتب في ملاحظة الحوالة)، وما أدخله الراكبُ ووقتُه
    cliq_alias: str | None
    cliq_reference: str | None
    cliq_transfer_reference: str | None
    cliq_reference_at: datetime | None
    dispute_reason: str | None
    #: **متى يصير هذا مانعاً للطلب الجديد** — نهايةُ الرحلة + مهلةُ السوق؛ و`blocks_requests` حكمُه الآن
    blocks_at: datetime
    blocks_requests: bool


class RiderUnconfirmedOut(BaseModel):
    """ما ينتظر الراكب — **الأقدمُ أوّلاً**. و`blocked` هو حكمُ «اطلب رحلة» نفسُه: «لا يمكن طلبُ رحلةٍ جديدةٍ حتى يُحسم» (§٦)."""

    blocked: bool
    items: list[RiderUnconfirmedItem]


# --------------------------------------------------------------- الكبتن (C33)

CaptainUnconfirmedState = Literal["awaiting_you", "auto_confirmed"]


class CaptainUnconfirmedItem(BaseModel):
    """«ليلى · أمس 21:58 · 3.364 د.أ كاش» ← «استلمت المبلغ» · «لم يدفع» (§٦)."""

    payment_id: uuid.UUID
    ride_id: uuid.UUID
    completed_at: datetime
    pickup_address: str | None
    dropoff_address: str | None
    #: **الاسمُ الأوّل للراكب وحدَه**
    rider_first_name: str | None
    amount: Decimal
    currency: Currency
    method: PaymentMethod
    #: `awaiting_you` (ينتظر «استلمت»/«وصلتني») · `auto_confirmed` (أُتمّ آلياً ونافذةُ الاعتراض مفتوحة)
    state: CaptainUnconfirmedState
    status: PaymentStatus
    #: **هل أقرّ الراكبُ بالتسليم** — ومنه يعرف الكبتنُ أن الصمتَ سيُتمّه آلياً
    declared_at: datetime | None
    #: كليك: «حوالةٌ بمرجع FT2410… · 21:47»، ومهلةُ التأكيد المجمَّدة
    cliq_transfer_reference: str | None
    cliq_reference_at: datetime | None
    cliq_confirmation_expires_at: datetime | None
    #: **«فاعترض قبل {الوقت}»** — لما أُتمّ آلياً وحدَه
    objection_deadline: datetime | None


class CaptainUnconfirmedOut(BaseModel):
    """ما ينتظر تأكيدَ الكبتن. و`blocked`: «لا تصلك طلباتٌ جديدةٌ حتى تؤكّد ما سبق» (§٦) — **شرطُ التوزيع نفسُه**."""

    blocked: bool
    #: عتبتا الحجب في سوقه — «تُوقَف الطلباتُ الجديدةُ عند 24 ساعة»
    block_count: int
    block_hours: int
    items: list[CaptainUnconfirmedItem]


# --------------------------------------------------------------- اللوحة (A10)

AdminUnconfirmedState = Literal[
    "awaiting_captain",
    "awaiting_rider",
    "cliq_no_reference",
    "disputed",
    "auto_confirmed_objected",
]


class QueuePartyOut(BaseModel):
    """طرفٌ في صفِّ الطابور — **اسمٌ ورقمٌ مقنَّع ومجموعُ معلَّقاته** (§٥)، ومعرّفُه ليُفتح ملفُّه."""

    user_id: uuid.UUID
    #: للكبتن وحدَه — `drivers.id` غيرُ `users.id`، وخلطُهما يفتح ملفَّ إنسانٍ آخر
    driver_id: uuid.UUID | None
    name: str
    phone_masked: str
    #: **كلُّ ما ينتظر أحداً على رحلاته** (كاشٌ أو كليك معلَّق) — لا هذا الصفُّ وحدَه
    pending_count: int


class ReminderStampOut(BaseModel):
    """تذكيرٌ أُرسل فعلاً — لمن ومتى (من صندوق الوارد؛ والختمُ على الصفِّ عددٌ وآخرُ وقت)."""

    to: Literal["captain", "rider"]
    at: datetime


class AdminUnconfirmedRow(BaseModel):
    """صفٌّ في «المدفوعات غير المؤكَّدة» — **الأقدمُ أوّلاً**، و`age_minutes` من نهاية الرحلة («26 س» — أحمرُ فوق ٢٤).

    **وحالاتُه خمسٌ من ستّ**: «رحلةٌ لم تُنهَ» تحتاج الإنهاءَ الآليَّ وقراءتَه (§٢-٢) ولم يُبنيا.
    """

    payment_id: uuid.UUID
    ride_id: uuid.UUID
    state: AdminUnconfirmedState
    completed_at: datetime | None
    age_minutes: int
    amount: Decimal
    currency: Currency
    method: PaymentMethod
    status: PaymentStatus
    confirmed_by: PaymentConfirmedBy | None
    confirmed_at: datetime | None
    declared_at: datetime | None
    cliq_transfer_reference: str | None
    cliq_reference_at: datetime | None
    dispute_reason: str | None
    disputed_at: datetime | None
    objected_at: datetime | None
    objection_reason: str | None
    auto_confirm_criteria: dict[str, Any] | None
    rider: QueuePartyOut
    driver: QueuePartyOut | None
    #: الختمُ على الصفّ — عددُ التذكيرات المجدولة التي أُرسلت حقاً لكلِّ طرفٍ وآخرُ وقت (**وللكبتن على الكاش المُقَرّ به: منذ
    #: الإقرار** — ساعتُه تبدأ منه، والأثرُ الكاملُ في `reminder_trail`)
    driver_reminders: int
    driver_reminded_at: datetime | None
    rider_reminders: int
    rider_reminded_at: datetime | None
    #: **الأثر**: كلُّ تذكيرٍ أُرسل بوقته، مجدولاً كان أو من «أرسل تذكيراً الآن»
    reminder_trail: list[ReminderStampOut]
    #: **في التدفّق** — رحلةٌ طُلبت والمفتاحُ مشتعلٌ من تطبيقٍ أرسل طريقتَه. **و`false`**: صفٌّ سبق المفتاحَ أو جاء من تطبيقٍ
    #: قديم — **لا تذكيرَ مجدولاً ولا حجبَ ولا إتمامَ آليَّ عليه**، والطابورُ وحدَه يحسمه
    in_flow: bool


class AdminRemindOut(BaseModel):
    """لمن أُرسل التذكيرُ الآن — **ولا شيءَ غيرُه تغيّر**: مواعيدُ الجدول على حالها."""

    sent_to: list[Literal["captain", "rider"]]
