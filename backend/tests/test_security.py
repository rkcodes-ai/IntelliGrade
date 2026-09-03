"""
Regression tests for `app.core.security`.

The password hashing path previously broke silently at runtime (passlib's
bcrypt backend is incompatible with modern `bcrypt` releases) — these tests
exist specifically to catch that class of failure before it reaches a
future Authentication module.
"""

import pytest

from app.core.security import create_token, decode_token, hash_password, verify_password


def test_hash_password_produces_a_bcrypt_hash() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$2b$")
    assert hashed != "correct horse battery staple"


def test_verify_password_accepts_the_correct_password() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_the_wrong_password() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("not the password", hashed) is False


def test_hash_password_rejects_passwords_over_72_bytes() -> None:
    with pytest.raises(ValueError, match="72 bytes"):
        hash_password("x" * 100)


def test_create_and_decode_token_round_trips_the_subject() -> None:
    token = create_token("user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_refresh_token_has_a_type_claim() -> None:
    token = create_token("user-123", token_type="refresh")
    payload = decode_token(token)
    assert payload["type"] == "refresh"
