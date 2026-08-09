from __future__ import annotations

import pytest

from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("SuperSecret123")
    assert hashed != "SuperSecret123"
    assert verify_password("SuperSecret123", hashed)
    assert not verify_password("wrong-password", hashed)


def test_password_hash_is_salted() -> None:
    assert hash_password("same") != hash_password("same")


def test_long_and_arabic_passwords_are_not_truncated() -> None:
    """bcrypt يقتطع بعد 72 بايت — الـ pre-hash يمنع ذلك."""
    base = "كلمة-مرور-عربية-طويلة-جداً" * 5
    hashed = hash_password(base)
    assert verify_password(base, hashed)
    assert not verify_password(base + "x", hashed)


def test_verify_password_with_null_hash() -> None:
    assert not verify_password("anything", None)


def test_access_token_roundtrip() -> None:
    token, jti, _ = create_access_token("user-1", {"role": "rider"})
    payload = decode_token(token, "access")
    assert payload["sub"] == "user-1"
    assert payload["jti"] == jti
    assert payload["role"] == "rider"


def test_token_type_is_enforced() -> None:
    refresh, _, _ = create_refresh_token("user-1")
    with pytest.raises(TokenError):
        decode_token(refresh, "access")


def test_tampered_token_rejected() -> None:
    token, _, _ = create_access_token("user-1")
    with pytest.raises(TokenError):
        decode_token(token + "x", "access")
