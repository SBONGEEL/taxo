"""الدخول برمز هوية Firebase (المرحلة 8-ب).

قسمان: منطقُ التحقق نفسه على مُحقِّقٍ حقيقي بمفتاح RSA يولّده الاختبار (لا
شبكة، ولا سبيل لتزوير رمز Google أصلاً)، ثم تدفّقُ الدخول والتسجيل على
المُحقِّق الوهمي.
"""

from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from app.services.firebase_auth import InvalidIdToken
from app.services.firebase_auth.google_certs import FirebaseIdTokenVerifier

PROJECT = "taxo-test-project"
OTHER_PROJECT = "someone-elses-project"
KEY_ID = "test-key-1"

E164 = "+962791234567"


# ------------------------------------------------- منطق التحقق (بلا شبكة)


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def verifier(signing_key, monkeypatch):
    """مُحقِّقٌ حقيقي، ومفاتيحُ Google مُستبدَلة بمفتاح الاختبار وحده.

    يُستبدل جلبُ الشهادات فقط — أما التوقيع و`aud` و`iss` والانتهاء فتُفحص
    بالمنطق الحقيقي، وهو ما يجب أن يُختبر.
    """
    from app.services.firebase_auth import google_certs

    certificate = _self_signed(signing_key)

    class _Certs:
        async def get(self):
            return {KEY_ID: certificate}

        def clear(self):
            return None

    monkeypatch.setattr(google_certs, "_cache", _Certs())
    return FirebaseIdTokenVerifier(project_id=PROJECT)


def _self_signed(key) -> str:
    """شهادة X.509 موقّعة ذاتياً — Google تنشر شهادات لا مفاتيح خام."""
    import datetime

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.x509.oid import NameOID

    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "taxo-test")])
    now = datetime.datetime.now(datetime.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return certificate.public_bytes(serialization.Encoding.PEM).decode()


def _token(key, **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": f"https://securetoken.google.com/{PROJECT}",
        "aud": PROJECT,
        "sub": "firebase-uid-1",
        "iat": now - 10,
        "exp": now + 3600,
        "phone_number": E164,
        "firebase": {"sign_in_provider": "phone"},
    } | overrides
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": KEY_ID})


async def test_valid_token_yields_the_phone(verifier, signing_key) -> None:
    identity = await verifier.verify(_token(signing_key))
    assert identity.phone == E164
    assert identity.provider_uid == "firebase-uid-1"
    assert identity.sign_in_provider == "phone"


async def test_token_signed_by_someone_else_is_rejected(verifier) -> None:
    """أي مفتاحٍ غير مفاتيح Google — وهذا هو جوهر التحقق كله."""
    stranger = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(InvalidIdToken):
        await verifier.verify(_token(stranger))


async def test_token_for_another_project_is_rejected(verifier, signing_key) -> None:
    """رمزٌ صحيح التوقيع لمشروعٍ آخر رمزٌ **صالح** — وقبولُه يفتح الباب للعالم."""
    with pytest.raises(InvalidIdToken):
        await verifier.verify(_token(signing_key, aud=OTHER_PROJECT))

    with pytest.raises(InvalidIdToken):
        await verifier.verify(
            _token(
                signing_key,
                iss=f"https://securetoken.google.com/{OTHER_PROJECT}",
            )
        )


async def test_expired_token_is_rejected(verifier, signing_key) -> None:
    now = int(time.time())
    with pytest.raises(InvalidIdToken):
        await verifier.verify(_token(signing_key, iat=now - 7200, exp=now - 3600))


async def test_token_without_a_phone_is_rejected(verifier, signing_key) -> None:
    with pytest.raises(InvalidIdToken):
        await verifier.verify(_token(signing_key, phone_number=None))
    with pytest.raises(InvalidIdToken):
        await verifier.verify(_token(signing_key, phone_number="0791234567"))


async def test_non_phone_sign_in_provider_is_rejected(verifier, signing_key) -> None:
    """دخولٌ بحساب Google أو بمجهول ليس إثباتاً لملكية رقم."""
    with pytest.raises(InvalidIdToken):
        await verifier.verify(
            _token(signing_key, firebase={"sign_in_provider": "google.com"})
        )


async def test_unsigned_token_is_rejected(verifier) -> None:
    """`alg: none` — أقدم حيلة على JWT، وتُرفض قبل أي نظرٍ في المحتوى."""
    now = int(time.time())
    forged = jwt.encode(
        {
            "iss": f"https://securetoken.google.com/{PROJECT}",
            "aud": PROJECT,
            "sub": "x",
            "iat": now,
            "exp": now + 600,
            "phone_number": E164,
            "firebase": {"sign_in_provider": "phone"},
        },
        key=None,
        algorithm="none",
        headers={"kid": KEY_ID},
    )
    with pytest.raises(InvalidIdToken):
        await verifier.verify(forged)


# ------------------------------------- المُحقِّق داخل تدفق التسجيل

# تدفّقا التسجيل والاستعادة على هذا المُحقِّق في `test_phone_verification.py`؛
# ما هنا هو المنطق التشفيري الذي لا يمر به مسارٌ وهمي.


async def test_the_mock_verifier_is_refused_in_production(monkeypatch) -> None:
    """مُحقِّقٌ يقبل «أنا صاحب هذا الرقم» بلا إثبات بابُ دخولٍ إلى أي حساب."""
    from app.core.config import settings
    from app.services.firebase_auth import build_verifier
    from app.services.firebase_auth.google_certs import FirebaseIdTokenVerifier
    from app.services.firebase_auth.mock import MockIdTokenVerifier

    values = {"project_id": PROJECT, "use_mock": True}
    assert isinstance(build_verifier(values), MockIdTokenVerifier)

    monkeypatch.setattr(settings, "environment", "production")
    assert isinstance(build_verifier(values), FirebaseIdTokenVerifier)


async def test_a_contract_without_a_project_is_unavailable() -> None:
    from app.services.firebase_auth import FirebaseAuthUnavailable, build_verifier

    try:
        build_verifier({"use_mock": True})
    except FirebaseAuthUnavailable:
        return
    raise AssertionError("عقدٌ بلا معرّف مشروع يجب أن يُرفض")
