"""Timezone-aware datetime helpers. Always store/compare in UTC."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(UTC)


def to_iso8601(value: datetime) -> str:
    """Serialize a datetime to an ISO-8601 string with explicit UTC offset."""
    return ensure_aware(value).isoformat()


def ensure_aware(value: datetime) -> datetime:
    """
    Attach UTC as the timezone if `value` is naive, otherwise return it
    unchanged. All datetimes in this codebase are stored in UTC (see
    `app.models.base.TimestampMixin`), so a naive value can only mean "UTC
    with the tzinfo stripped."

    This matters for cross-database portability: PostgreSQL's `TIMESTAMP
    WITH TIME ZONE` round-trips timezone-aware datetimes correctly, but
    SQLite (used in the test suite — see `tests/conftest.py`) has no
    native datetime type and reliably returns naive `datetime` objects
    even from a `DateTime(timezone=True)` column. Model properties that
    compare a stored datetime against `datetime.now(UTC)` (e.g.
    `User.is_locked`, `RefreshToken.is_active`) go through this helper so
    they behave identically against both databases instead of raising
    `TypeError: can't compare offset-naive and offset-aware datetimes`
    the moment they run against SQLite.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
