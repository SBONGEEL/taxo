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


#: **المجموعةُ الرابعة: قناةٌ لكلِّ نغمة** («نغمة الإشعارات»، أمرُ المالك ٢٠٢٦-١١-١٧ ج/١). **صوتُ القناة لا يتغيّر بعد إنشائها**
#: (أندرويد)، فالنغمةُ المختارةُ قناةٌ أخرى معرّفُها معرّفُ الحدث ولاحقةُ النغمة: `taxo.offer.v2.s1_2`. **والقنواتُ القديمةُ تبقى
#: كما هي** للحزم الأقدم ولمن بقي على الافتراضيّ
CHANNELS_V4 = 4
#: **«الافتراضيّ» في الإعداد** — يُكتب `NULL` لمن لم يختر أو عاد إليه، **ومعناه حين يشتعل مفتاحُ السوق `NEW_DEFAULT`**
DEFAULT_TONE = "default"
#: **الصوتُ الافتراضيُّ للجميع** (قرارُ المالك ١٧/١١/٢٠٢٦، `design/OWNER-2026-11-17-DECISIONS.md` ١): **الخيارُ ٥ من المجموعة الثانية**
#: (`design/sounds-v2/`، صوتُ «TAXO» الأنثويّ مع بوق «بيب بيب») — للطلب ولـ«الكابتن وصل» ولأصوات التحديث القصيرة
NEW_DEFAULT = "s2_5"
#: **ما يُختار منه في الإعداد، بترتيبه**: الافتراضيُّ (= `NEW_DEFAULT`)، ثمّ الأربعةُ الباقيةُ من المجموعة الثانية، ثمّ الثلاثةُ من الأولى
#: (`design/sounds/`)، ثمّ «اهتزاز فقط»
TONES: tuple[str, ...] = (DEFAULT_TONE, "s2_1", "s2_2", "s2_3", "s2_4", "s1_1", "s1_2", "s1_3", "vibrate")
#: **لاحقاتُ القنوات التي تحملها الحزمةُ الرابعة** — كلُّ ما يُختار ومعه الافتراضيُّ الجديد بلاحقته (`taxo.offer.v2.s2_5`). والحزمةُ الرابعةُ
#: لم تُنشر قبل هذا (1118 بُنيت ١١/١١)، فاتّسعت في مكانها ولا جهازَ منشوراً يحمل نصفَها
CHANNEL_TONES: frozenset[str] = frozenset((*TONES[1:], NEW_DEFAULT))
#: **ما تتبعه النغمة** — قنواتُ الأحداث ذاتُ الصوت؛ والعامُّ والمكالمةُ لا يتغيّران
TONED_CHANNELS: frozenset[str] = frozenset(
    {OFFER_V2, "taxo.accepted", "taxo.approaching", "taxo.arrived", "taxo.started", "taxo.ended", "taxo.payment"}
)


#: **المجموعةُ الخامسة: إشعارُ الكبتن الغنيّ يرسمه الراكبُ بنفسه** (SPEC §١٠٣/12، ٢٠٢٦-١١-١٨) — الحزمةُ التي تحمل `RideNotice`
#: تُنشئ قناةَ الرحلة الحيّة `taxo.ride.live`، **فوجودُها شاهدٌ على الراسم** كما شهدت `taxo.call` على خدمة الرنين
CHANNELS_V5 = 5
#: **ما يُرسم غنيّاً**: قبولُ الكبتن واقترابُه ووصولُه — حيث تنفع صورتُه ولوحتُه وزرّا «اتصال» و«دردشة»
RICH_KINDS: frozenset[str] = frozenset({"driver_assigned", "driver_approaching", "driver_arrived"})


#: **المجموعةُ السادسة: الطلبُ يرسمه الكبتنُ بنفسه ويرنّه «TAXO بيب بيب»** (أمرُ المالك ٢٠٢٦-١١-٢٦) — الحزمةُ التي تنشئ قناةَ
#: `taxo.offer.v3` تحمل `OfferAlert.showFromPush`، **فوجودُها شاهدٌ على الراسم**. **والعلّةُ مقيسة**: الطلبُ كان يصل الغائبَ إشعاراً
#: يرسمه النظامُ — **يرنّ مرّةً ثانيتين ولا يتكرّر ولا يملأ الشاشة**؛ والطريقُ المكرَّرُ كان لا يبلغه إلا الويبُ من مقبسه
CHANNELS_V6 = 6
OFFER_V3 = "taxo.offer.v3"


def level_of(push_channels: int | None) -> int:
    """المجموعةُ التي يُرسَل بها — **ما دون الثانية أقدمُ كلُّه**، فلا يُخترع لها وسط. **وما فوق الرابعة رابعةٌ**
    حتى تُعرَّف خامسة: حزمةٌ أحدثُ من هذا الخادم تحمل ما تحمله الرابعةُ على الأقلّ."""
    value = push_channels or 0
    if value >= CHANNELS_V6:
        return CHANNELS_V6
    if value >= CHANNELS_V5:
        return CHANNELS_V5
    if value >= CHANNELS_V4:
        return CHANNELS_V4
    if value >= CHANNELS_V3:
        return CHANNELS_V3
    return CHANNELS_V2 if value >= CHANNELS_V2 else 0


def toned(message: PushMessage, tone: str | None) -> PushMessage:
    """**قناةُ النغمة المختارة** — لرسالةٍ شُكّلت للمجموعة الرابعة. **`None` (المفتاحُ مطفأ) وغيرُ المعروف وما لا نغمةَ لقناته: كما هي حرفاً**،
    و«الافتراضيّ» قناةُ `NEW_DEFAULT`."""
    channel = message.android_channel_id
    if tone == DEFAULT_TONE:
        tone = NEW_DEFAULT
    # **الطلبُ يرنّ دائماً والكبتنُ متّصل** (أمرُ المالك ج/١/٤): «اهتزاز فقط» يُسكت ما عداه، والطلبُ على الافتراضيّ الجديد
    if tone == "vibrate" and channel == OFFER_V2:
        tone = NEW_DEFAULT
    if not tone or tone not in CHANNEL_TONES or channel not in TONED_CHANNELS:
        return message
    return replace(message, android_channel_id=f"{channel}.{tone}")


def for_level(message: PushMessage, level: int, tone: str | None = None, rich: bool = False) -> PushMessage | None:
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
    # **الطلبُ للسادسة بياناتٍ وحدَها** — ترسمه الحزمةُ ورقةً أو فقاعةً أو ملءَ شاشةٍ **وترنّ «بيب بيب» حتى قبولٍ أو رفضٍ أو انقضاء**،
    # ولا تتبع «نغمة الإشعارات»: الطلبُ صوتٌ واحد. ونصُّ الدرج معه لمن لا يرسم إلا الدرج
    if level >= CHANNELS_V6 and kind == "ride_offer":
        tray = {"title": message.title, "body": message.body} if message.title else {}
        return replace(
            message,
            data={**message.data, **message.native_data, **tray},
            data_only=True,
            android_channel_id=OFFER_V3,
        )
    if level < CHANNELS_V2:
        return message
    shaped = replace(message, android_channel_id=EVENT_CHANNELS_V2.get(kind))
    # **الغنيُّ للخامسة ومفتاحِها وحدهما** (§١٠٣/12): بياناتٌ ترسمها `RideNotice` **على قناة النغمة نفسِها** (`channel`) —
    # فالصوتُ لا يتغيّر، ويُضاف الوجهُ واللوحةُ والزرّان. **وبلا ما يُرسم به** (`native_data` فارغ) يبقى إشعاراً يرسمه النظام
    if rich and level >= CHANNELS_V5 and kind in RICH_KINDS and message.native_data:
        toned_message = toned(shaped, tone)
        tray = {"title": message.title, "body": message.body}
        channel = {"channel": toned_message.android_channel_id} if toned_message.android_channel_id else {}
        return replace(
            toned_message,
            data={**message.data, **message.native_data, **tray, **channel, "rich": "1"},
            data_only=True,
        )
    # **النغمةُ للرابعة وحدَها** — حزمةٌ أقدمُ لا تحمل قناةَ النغمة، وقناةٌ غائبةٌ تُسقط الطلبَ إلى الاحتياطية همساً
    return toned(shaped, tone) if level >= CHANNELS_V4 else shaped
