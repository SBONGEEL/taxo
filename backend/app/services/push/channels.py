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

**والمجموعةُ الثالثة: قناةُ المكالمة وخدمةٌ ترسمها** (§٦٦-ج/١٧، ٢٠٢٦-١٠-٠٩). الحزمةُ «2.0» تُنشئ `taxo.call` **وتحمل
خدمةَ رسائلَ أصليّةً** (`CallMessagingService`) ترنّ كمكالمة هاتفٍ والتطبيقُ مغلق — **والقناةُ والخدمةُ في الحزمة نفسِها**،
فوجودُ القناة على الجهاز شاهدٌ على الخدمة. **ولها يُرسل `incoming_call` بياناتٍ وحدَها** (`data_only`): إشعارٌ بقسم
`notification` يرسمه النظامُ والتطبيقُ في الخلفية **فلا يبلغ الخدمةَ أصلاً**. **ومعه أمرُ إسكات الرنين** حين تكفّ المكالمةُ
عن الرنين — **ولا يُرسل هذا لما دونها**: لا خدمةَ هناك تفهمه، وبياناتٌ صامتةٌ لا تُرسم شيئاً. **والمجموعةُ الثانيةُ كما
كانت حرفاً** — `incoming_call` فيها إشعارٌ عاديٌّ على قناة الافتراض.
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


#: إصدارُ المجموعة التي فيها قناةُ المكالمة **وخدمةٌ أصليّةٌ ترسم رنينَها** (§٦٦-ج/١٧)
CHANNELS_V3 = 3
#: قناةُ المكالمة — **نغمةُ رنينٍ على مجرى الرنين** (`TaxoChannels.java`)، فتسكت حيث يسكت رنينُ الهاتف كمكالمةٍ حقيقيّة
CALL = "taxo.call"
#: نوعُ أمر الإسكات — **«كفّت هذه المكالمةُ عن الرنين»**: رُدّ عليها أو رُفضت أو قطعها المتصلُ أو فاتت ثلاثونُها
CALL_RING_STOPPED = "call_ring_stopped"

#: **الحدثُ ← قناتُه في المجموعة الثالثة، بياناتٍ وحدَها** — ترسمه الخدمةُ الأصليّة على قناته وترنّ حتى يُسكَت.
EVENT_CHANNELS_V3: dict[str, str] = {"incoming_call": CALL}
#: **ما لا يُرسل إلا للمجموعة الثالثة** — أمرٌ لخدمتها لا إشعار، فلا معنى له حيث لا خدمة. **ولا يُحجب عن جهازٍ أمامَ صاحبه**
#: (`notifications.notify_user`): الويبُ لا يراه، ورنينٌ أصليٌّ قد يبقى قائماً والتطبيقُ ظاهر.
NATIVE_ONLY_KINDS: frozenset[str] = frozenset({CALL_RING_STOPPED})


def level_of(push_channels: int | None) -> int:
    """المجموعةُ التي يُرسَل بها — **ما دون الثانية أقدمُ كلُّه**، فلا يُخترع لها وسط. **وما فوق الثالثة ثالثةٌ**
    حتى تُعرَّف رابعة: حزمةٌ أحدثُ من هذا الخادم تحمل ما تحمله الثالثةُ على الأقلّ."""
    value = push_channels or 0
    if value >= CHANNELS_V3:
        return CHANNELS_V3
    return CHANNELS_V2 if value >= CHANNELS_V2 else 0


def for_level(message: PushMessage, level: int) -> PushMessage | None:
    """الرسالةُ كما تُرسل لمجموعةٍ بعينها — **والأقدمُ كما هي حرفاً**، **و`None` لما لا يُرسل إليها أصلاً**.

    **وفي الثالثة يصير الرنينُ بياناتٍ وحدَها**: نصُّ الدرج (`title`/`body`) ينتقل إلى `data` — **فالخدمةُ ترسمه كما كان
    النظامُ يرسمه**، ونصٌّ واحدٌ في الخادم لا نسخةٌ في كلِّ تطبيق — ومعه ما للجهاز الراسم وحدَه (`native_data`).
    """
    kind = message.data.get("type", "")
    if level >= CHANNELS_V3 and (kind in EVENT_CHANNELS_V3 or kind in NATIVE_ONLY_KINDS):
        tray = {"title": message.title, "body": message.body} if message.title else {}
        return replace(
            message,
            data={**message.data, **message.native_data, **tray},
            data_only=True,
            android_channel_id=EVENT_CHANNELS_V3.get(kind),
        )
    if kind in NATIVE_ONLY_KINDS:
        return None
    if level < CHANNELS_V2:
        return message
    return replace(message, android_channel_id=EVENT_CHANNELS_V2.get(kind))
