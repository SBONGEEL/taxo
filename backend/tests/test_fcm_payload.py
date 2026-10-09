"""حمولةُ FCM لـiOS — ثلاثةٌ أُضيفت مع الطريق الأصليّ للتطبيقين (٢٠٢٦-٠٩-٢٩).

**لا شبكةَ هنا**: `_payload` دالّةٌ نقيّةٌ على الرسالة، فتُقاس بلا مزوّد.
"""

from __future__ import annotations

import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.services.push import channels
from app.services.push.base import PushMessage
from app.services.push.fcm import FcmPushProvider


def _provider() -> FcmPushProvider:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return FcmPushProvider(
        project_id="taxo-test",
        service_account={"client_email": "t@taxo-test.iam", "private_key": pem},
    )


def test_every_ios_push_is_an_alert_with_a_sound() -> None:
    apns = _provider()._payload("tok", PushMessage(title="t", body="b"))["message"]["apns"]
    assert apns["headers"]["apns-push-type"] == "alert"
    assert apns["headers"]["apns-priority"] == "5"
    # **بغير الصوت يُرسم الإشعارُ صامتاً** على iOS
    assert apns["payload"] == {"aps": {"sound": "default"}}
    # وما لا يحمل عمرَه لا ترويسةَ انتهاءٍ له — يبقى حتى يُسلَّم
    assert "apns-expiration" not in apns["headers"]


def test_a_ride_offer_is_not_delivered_after_its_window() -> None:
    before = int(time.time())
    message = PushMessage(
        title="طلب رحلة جديد",
        body="…",
        data={"type": "ride_offer", "ride_id": "r", "expires_in_seconds": "20"},
        high_priority=True,
    )
    headers = _provider()._payload("tok", message)["message"]["apns"]["headers"]
    assert headers["apns-priority"] == "10"
    expires = int(headers["apns-expiration"])
    assert before + 20 <= expires <= int(time.time()) + 20


def test_a_malformed_lifetime_drops_the_header_not_the_push() -> None:
    message = PushMessage(title="t", body="b", data={"expires_in_seconds": "soon"})
    payload = _provider()._payload("tok", message)["message"]
    assert "apns-expiration" not in payload["apns"]["headers"]
    assert payload["notification"] == {"title": "t", "body": "b"}


# ---------------------------------------------------- أندرويد (§٦١-ل/٣، ٢٠٢٦-١٠-٠٥)


def test_android_offer_carries_its_lifetime_and_channel() -> None:
    """**`ttl` أخو `apns-expiration`**: عرضٌ يصل بعد مهلته يدعو إلى رحلةٍ ذهبت لغيره."""
    message = PushMessage(
        title="طلب رحلة جديد",
        body="…",
        data={"type": "ride_offer", "ride_id": "r", "expires_in_seconds": "20"},
        high_priority=True,
        android_channel_id="taxo.offer.v2",
    )
    android = _provider()._payload("tok", message)["message"]["android"]
    assert android == {
        "priority": "high",
        "ttl": "20s",
        "notification": {"channel_id": "taxo.offer.v2"},
    }


def test_android_without_lifetime_or_channel_is_as_before() -> None:
    """**ما لا يحمل عمراً ولا قناةً كما كان حرفاً** — فلا يتغيّر إشعارٌ لم يُقصد."""
    message = PushMessage(title="t", body="b", data={"expires_in_seconds": "soon"})
    assert _provider()._payload("tok", message)["message"]["android"] == {"priority": "normal"}


# ---------------------------------------------------- رنينُ المكالمة الأصليّ (§٦٦-ج/١٧، ٢٠٢٦-١٠-٠٩)


def _ring() -> PushMessage:
    """**الرنينُ كما يبنيه `notifications.publish_incoming_call`** — وعمرُه للجهاز الراسم وحدَه."""
    return PushMessage(
        title="مكالمةٌ من الكبتن",
        body="افتح التطبيق للرد",
        data={"type": "incoming_call", "ride_id": "r", "call_id": "c", "caller_role": "driver", "recording": "false"},
        high_priority=True,
        native_data={"expires_in_seconds": "30"},
    )


def test_a_native_ring_reaches_the_app_as_data_alone() -> None:
    """**بلا `notification` ولا `android.notification`** — وبأيٍّ منهما يرسمه النظامُ والتطبيقُ في الخلفية فلا يبلغ الخدمة.
    **وعمرُه `ttl`**: رنينٌ يصل بعد ثلاثينه لمكالمةٍ فاتت."""
    shaped = channels.for_level(_ring(), channels.CHANNELS_V3)
    assert shaped is not None and shaped.data_only and shaped.android_channel_id == channels.CALL
    wire = _provider()._payload("tok", shaped)["message"]
    assert set(wire) == {"token", "data", "android"}
    assert wire["android"] == {"priority": "high", "ttl": "30s"}
    # **نصُّ الدرج في `data`** — الخدمةُ ترسمه كما كان النظامُ يرسمه
    assert wire["data"]["title"] == "مكالمةٌ من الكبتن" and wire["data"]["body"] == "افتح التطبيق للرد"
    assert wire["data"]["expires_in_seconds"] == "30" and wire["data"]["call_id"] == "c"


def test_below_the_third_set_the_ring_is_todays_notification() -> None:
    """**المجموعةُ الثانيةُ وما دونها كما كانت حرفاً** — إشعارٌ يرسمه النظام، بلا عمرٍ ولا قناةٍ ولا نصٍّ في `data`."""
    for level in (0, channels.CHANNELS_V2):
        shaped = channels.for_level(_ring(), level)
        assert shaped is not None and not shaped.data_only
        wire = _provider()._payload("tok", shaped)["message"]
        assert wire["notification"] == {"title": "مكالمةٌ من الكبتن", "body": "افتح التطبيق للرد"}
        assert wire["android"] == {"priority": "high"}
        assert set(wire["data"]) == {"type", "ride_id", "call_id", "caller_role", "recording"}


def test_the_stop_order_goes_to_the_native_service_alone() -> None:
    """**«أسكت الرنين» أمرٌ لخدمةٍ لا إشعار** — لا يُرسل حيث لا خدمة، ولا نصَّ معه. **وبأولويّةٍ عاديّة**
    (`notifications.publish_call_ring_stopped`): عاليةٌ لا يُرى منها شيءٌ تُبطئ عند FCM ما يحتاج العاليةَ حقّاً."""
    stop = PushMessage(
        title="",
        body="",
        data={"type": channels.CALL_RING_STOPPED, "ride_id": "r", "call_id": "c"},
        native_data={"expires_in_seconds": "30"},
    )
    assert channels.for_level(stop, 0) is None
    assert channels.for_level(stop, channels.CHANNELS_V2) is None
    shaped = channels.for_level(stop, channels.CHANNELS_V3)
    assert shaped is not None and shaped.data_only and shaped.android_channel_id is None
    wire = _provider()._payload("tok", shaped)["message"]
    assert wire["data"] == {"type": channels.CALL_RING_STOPPED, "ride_id": "r", "call_id": "c", "expires_in_seconds": "30"}
    assert wire["android"] == {"priority": "normal", "ttl": "30s"}


def test_the_third_set_is_three_and_anything_newer() -> None:
    """**ما دون الثانية أقدم، وما فوق الثالثة ثالثة** — حزمةٌ أحدثُ من الخادم تحمل ما تحمله الثالثةُ على الأقلّ."""
    assert [channels.level_of(value) for value in (None, 1, 2, 3, 7)] == [0, 0, 2, 3, 3]
    # **وما ليس رنيناً في الثالثة كما في الثانية** — قناتُه، ويرسمه النظام
    accepted = PushMessage(title="تم قبول رحلتك", body="…", data={"type": "driver_assigned"})
    shaped = channels.for_level(accepted, channels.CHANNELS_V3)
    assert shaped is not None and not shaped.data_only and shaped.android_channel_id == "taxo.accepted"
