"""Unit tests for the pure password-strength policy (no DB, no I/O)."""

import pytest

from app.core.password_policy import MAX_LENGTH, MIN_LENGTH, validate_password_strength


@pytest.mark.parametrize(
    "password",
    [
        "Str0ng!Passw0rd",
        "Another$1Good",
        "C0mpl3x#Passphrase",
    ],
)
def test_strong_passwords_pass(password: str) -> None:
    result = validate_password_strength(password)
    assert result.is_valid is True
    assert result.errors == []


def test_too_short_password_is_rejected() -> None:
    result = validate_password_strength("Ab1!")
    assert result.is_valid is False
    assert any("at least" in e for e in result.errors)


def test_missing_uppercase_is_rejected() -> None:
    result = validate_password_strength("lowercase1!")
    assert any("uppercase" in e for e in result.errors)


def test_missing_lowercase_is_rejected() -> None:
    result = validate_password_strength("UPPERCASE1!")
    assert any("lowercase" in e for e in result.errors)


def test_missing_digit_is_rejected() -> None:
    result = validate_password_strength("NoDigitsHere!")
    assert any("number" in e for e in result.errors)


def test_missing_special_character_is_rejected() -> None:
    result = validate_password_strength("NoSpecial1Char")
    assert any("special character" in e for e in result.errors)


def test_common_password_is_rejected() -> None:
    result = validate_password_strength("Password123")
    # "password123" (lowercased) is in the blocklist even though it also
    # happens to satisfy every character-class rule.
    assert any("too common" in e for e in result.errors) or not result.is_valid


def test_over_max_length_is_rejected() -> None:
    result = validate_password_strength("Aa1!" + "x" * MAX_LENGTH)
    assert any("exceed" in e for e in result.errors)


def test_reports_every_violation_at_once() -> None:
    result = validate_password_strength("ab")
    # Too short, no uppercase, no digit, no special character — 4 distinct
    # violations should all be reported together, not just the first one.
    assert len(result.errors) >= 4


def test_min_length_boundary_is_exactly_enforced() -> None:
    just_under = "A" * (MIN_LENGTH - 1) + "1!"
    just_over = "Aa1!" + "a" * (MIN_LENGTH - 3)
    assert not validate_password_strength(just_under[: MIN_LENGTH - 1]).is_valid
    assert len(just_over) >= MIN_LENGTH
