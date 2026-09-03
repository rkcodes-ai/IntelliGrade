"""
Password strength policy — pure validation, no I/O.

Deliberately separate from `app.core.security` (which only knows how to
hash/verify, not what makes a password acceptable) and from
`app.services.password_service` (which adds the stateful concerns: reuse
history, "is this the user's current password," persistence). Keeping this
layer pure makes it trivial to unit test every rule in isolation.
"""

import re
from dataclasses import dataclass

MIN_LENGTH = 8
MAX_LENGTH = 72  # bcrypt's hard limit — see app.core.security._BCRYPT_MAX_BYTES

_UPPERCASE_RE = re.compile(r"[A-Z]")
_LOWERCASE_RE = re.compile(r"[a-z]")
_DIGIT_RE = re.compile(r"\d")
_SPECIAL_RE = re.compile(r"""[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?~`]""")

# A deliberately short blocklist of the most common weak passwords. This is
# a baseline sanity check, not a substitute for a full breached-password
# corpus (e.g. HaveIBeenPwned's k-anonymity API) — integrating one is a
# reasonable follow-up, tracked in KNOWN_LIMITATIONS.md.
_COMMON_PASSWORDS = frozenset(
    {
        "password",
        "password1",
        "password123",
        "12345678",
        "123456789",
        "qwerty123",
        "letmein123",
        "admin1234",
        "welcome123",
        "iloveyou1",
        "changeme1",
    }
)


@dataclass(frozen=True)
class PasswordPolicyResult:
    is_valid: bool
    errors: list[str]


def validate_password_strength(password: str) -> PasswordPolicyResult:
    """
    Check `password` against the enterprise policy: length bounds, character
    class diversity (upper/lower/digit/special), and a common-password
    blocklist. Returns every violation found, not just the first — a form
    should show a user all the rules they still need to satisfy at once.
    """
    errors: list[str] = []

    if len(password) < MIN_LENGTH:
        errors.append(f"Password must be at least {MIN_LENGTH} characters long.")
    if len(password.encode("utf-8")) > MAX_LENGTH:
        errors.append(f"Password must not exceed {MAX_LENGTH} bytes.")
    if not _UPPERCASE_RE.search(password):
        errors.append("Password must contain at least one uppercase letter.")
    if not _LOWERCASE_RE.search(password):
        errors.append("Password must contain at least one lowercase letter.")
    if not _DIGIT_RE.search(password):
        errors.append("Password must contain at least one number.")
    if not _SPECIAL_RE.search(password):
        errors.append("Password must contain at least one special character.")
    if password.lower() in _COMMON_PASSWORDS:
        errors.append("Password is too common — choose something less guessable.")

    return PasswordPolicyResult(is_valid=len(errors) == 0, errors=errors)


def validate_password_field(value: str) -> str:
    """
    Pydantic-`field_validator`-shaped wrapper around `validate_password_strength`,
    for schemas that accept a new password (registration, reset, change).
    Shared across `app.schemas.user` and `app.schemas.auth` so the rule set
    lives in exactly one place.
    """
    result = validate_password_strength(value)
    if not result.is_valid:
        raise ValueError("; ".join(result.errors))
    return value
