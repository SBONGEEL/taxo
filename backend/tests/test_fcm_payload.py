"""حمولةُ FCM لـiOS — ثلاثةٌ أُضيفت مع الطريق الأصليّ للتطبيقين (٢٠٢٦-٠٩-٢٩).

**لا شبكةَ هنا**: `_payload` دالّةٌ نقيّةٌ على الرسالة، فتُقاس بلا مزوّد.
"""

from __future__ import annotations

import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

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
