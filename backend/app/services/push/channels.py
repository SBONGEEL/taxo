"""قنواتُ إشعار أندرويد — **ما يحمله الجهازُ يختار القناة** (SPEC §٦١-ل/٣–٥، ٢٠٢٦-١٠-٠٥).

**قناةٌ لكلِّ حدثٍ بصوته**، وكلُّ تطبيقٍ يُنشئ ما يصله منها **بأصواته هو** — فالمعرّفُ واحدٌ والصوتُ لكلِّ
تطبيق («وصل» عند الراكب غيرُها عند الكبتن). **وأهميّةُ القناة وصوتُها يُضبطان مرّةً عند إنشائها ولا
يُغيَّران** (أندرويد) — فالقناةُ الجديدةُ معرّفٌ جديد، وقناةُ الطلب الجديدة `taxo.offer.v2` لا `taxo.offer`.

**ولا تُرسل قناةٌ لجهازٍ لا يحملها**: الحزمُ المنشورةُ تُحمِّل شاشاتها من خادم، فشيفرةُ الويب قد تكون أحدثَ
من الحزمة — **وقناةٌ غائبةٌ تُسقط الإشعارَ إلى القناة الاحتياطية بلا منبّه**، فيصل طلبُ الرحلة همساً. فالتطبيقُ
يسأل أندرويد عن قنواته **ويرسل إصدارَ مجموعتها** مع رمزه (`device_tokens.push_channels`) — **و`NULL` حزمةٌ
أقدمُ على قنواتها اليوم حرفاً**: `taxo.offer` بمنبّه الهاتف، وما عداه في الافتراض.

**والعامُّ بلا معرّف**: الحزمةُ الجديدةُ تجعل `taxo.general` قناةَ الافتراض في بيانها، فما لا قناةَ له يقع
فيها بصوت «الإشعار» — **فالحملاتُ وما يشبهها لا تحتاج تغييراً هنا**.
"""

from __future__ import annotations

from dataclasses import replace

from app.services.push.base import PushMessage

#: إصدارُ المجموعة التي فيها قنواتُ الأحداث وقناةُ الطلب الجديدة
CHANNELS_V2 = 2
#: قناةُ الطلب القديمة — **منبّهُ الهاتف على مجرى المنبّه**، وتبقى للحزم الأقدم
OFFER_LEGACY = "taxo.offer"
#: قناةُ الطلب الجديدة — **صوتُ الطلب الجديد على مجرى المنبّه نفسِه**، فترنّ والهاتفُ صامت
OFFER_V2 = "taxo.offer.v2"

#: **الحدثُ ← قناتُه** في المجموعة الثانية — **وما ليس هنا عامٌّ** (بلا معرّف، فيقع في الافتراض).
EVENT_CHANNELS_V2: dict[str, str] = {
    "ride_offer": OFFER_V2,
    "driver_assigned": "taxo.accepted",
    "driver_approaching": "taxo.approaching",
    "driver_arrived": "taxo.arrived",
    "ride_started": "taxo.started",
    "ride_completed": "taxo.ended",
    # **«نجح دفعٌ أو شحن» — مالٌ وصل**: لا رسمٌ خرج من جيبٍ ولا تذكيرٌ بمالٍ لم يصل
    "payment_confirmed": "taxo.payment",
    "tip_received": "taxo.payment",
    "referral_rewarded": "taxo.payment",
    "cancellation_compensation": "taxo.payment",
}


def level_of(push_channels: int | None) -> int:
    """المجموعةُ التي يُرسَل بها — **ما دون الثانية أقدمُ كلُّه**، فلا يُخترع لها وسط."""
    return CHANNELS_V2 if (push_channels or 0) >= CHANNELS_V2 else 0


def for_level(message: PushMessage, level: int) -> PushMessage:
    """الرسالةُ كما تُرسل لمجموعةٍ بعينها — **والأقدمُ كما هي حرفاً**."""
    if level < CHANNELS_V2:
        return message
    return replace(message, android_channel_id=EVENT_CHANNELS_V2.get(message.data.get("type", "")))
