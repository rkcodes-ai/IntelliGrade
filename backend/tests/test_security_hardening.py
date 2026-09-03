"""
Security-hardening tests that don't fit neatly under auth-flow or RBAC:
rate limiting on the login endpoint, and JWT tampering rejection.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.rate_limit import limiter
from tests.conftest import create_test_user


async def test_login_is_rate_limited(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """
    `/auth/login` is decorated with `@limiter.limit("10/minute")` (see
    `app/api/v1/endpoints/auth.py`) specifically to blunt credential-
    stuffing/brute-force attempts. The global test fixture disables the
    limiter (see `conftest._disable_rate_limiter`) so unrelated tests don't
    trip it — this test re-enables it deliberately to verify the limit is
    real, then lets the fixture disable it again on teardown.
    """
    await create_test_user(db_session, username="ratelimited", password="CorrectHorse9!")

    limiter.enabled = True
    try:
        statuses = []
        for _ in range(12):
            response = await client.post(
                "/api/v1/auth/login",
                json={"identifier": "ratelimited", "password": "WrongPassword1!"},
            )
            statuses.append(response.status_code)
    finally:
        limiter.enabled = False

    assert 429 in statuses, f"expected at least one 429 among {statuses}"


async def test_default_rate_limit_applies_to_undecorated_routes(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    """Regression test (Module 10 deployment validation): `RATE_LIMIT_DEFAULT`
    must be enforced on routes with no `@limiter.limit(...)`/`@limiter.exempt`
    decorator of their own — this is exactly the class of route
    `SlowAPIMiddleware` silently stopped protecting once FastAPI's
    `_IncludedRouter` optimization broke its route-introspection (see
    `app/middleware/rate_limit.py`'s module docstring for the full root
    cause). Discovered by actually hammering a live server with 150 rapid
    requests and observing zero 429s — a real runtime defect, not
    something the pre-existing test suite could have caught, since no
    prior test exercised any single route anywhere near
    `RATE_LIMIT_DEFAULT` (100/minute) times in one test."""
    limiter.enabled = True
    try:
        statuses = []
        for _ in range(105):
            response = await client.get(
                "/api/v1/institutions", headers={"X-Institution-Id": "00000000-0000-0000-0000-000000000000"}
            )
            statuses.append(response.status_code)
    finally:
        limiter.enabled = False

    assert 429 in statuses, (
        f"expected the global default limit to kick in among {len(statuses)} requests to an "
        f"undecorated route; got status codes {set(statuses)}"
    )

    # Health probes must remain exempt regardless — they're polled far
    # more frequently than any business endpoint and must never depend on
    # the rate-limit backend's availability.
    limiter.enabled = True
    try:
        health_statuses = [
            (await client.get("/health/live")).status_code for _ in range(105)
        ]
    finally:
        limiter.enabled = False
    assert all(code == 200 for code in health_statuses), (
        f"/health/live must never be rate limited; got {set(health_statuses)}"
    )


async def test_access_token_with_tampered_signature_is_rejected(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="tamperuser", password="CorrectHorse9!")
    login_response = await client.post(
        "/api/v1/auth/login", json={"identifier": "tamperuser", "password": "CorrectHorse9!"}
    )
    token = login_response.json()["access_token"]

    # Corrupt the last 4 base64url characters of the signature segment (a
    # full 3-byte-aligned group) rather than just the last character: HS256
    # signatures are 256 bits, which base64url-encodes to 43 characters
    # with 2 unused padding bits in the final character — flipping only
    # that last character can, for some inputs, decode to byte-identical
    # signature bytes and false-negative this test. Corrupting a whole
    # aligned group guarantees the decoded bytes actually change.
    header, payload, signature = token.split(".")
    corrupted_tail = "AAAA" if signature[-4:] != "AAAA" else "BBBB"
    tampered = f"{header}.{payload}.{signature[:-4]}{corrupted_tail}"

    response = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tampered}"})
    assert response.status_code == 401


async def test_refresh_token_cannot_be_used_as_an_access_token(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    await create_test_user(db_session, username="tokentype", password="CorrectHorse9!")
    login_response = await client.post(
        "/api/v1/auth/login", json={"identifier": "tokentype", "password": "CorrectHorse9!"}
    )
    refresh_token = login_response.cookies["refresh_token"]

    response = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert response.status_code == 401


async def test_expired_access_token_is_rejected(
    client: AsyncClient, db_session: AsyncSession, seed_rbac
) -> None:
    from datetime import UTC, datetime, timedelta

    import jwt as pyjwt

    from app.core.config import get_settings

    user = await create_test_user(db_session, username="expiredtoken", password="CorrectHorse9!")
    settings = get_settings()

    now = datetime.now(UTC)
    expired_token = pyjwt.encode(
        {
            "sub": str(user.id),
            "type": "access",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        },
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    response = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401
