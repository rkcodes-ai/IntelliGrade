"""
Rate limiting (built on `slowapi`, backed by Redis).

Wires a configured `Limiter` onto `app.state` and registers its exception
handler, so endpoints can opt in with `@limiter.limit(...)` or
`dependencies=[Depends(limiter.limit(...))]`.

`@limiter.exempt` is applied to the unversioned `/health*` probes
(`app/api/health.py`) so orchestrators (Kubernetes, load balancers) polling
them frequently are never throttled or made to depend on the rate-limit
backend's availability.

`slowapi`'s storage-error handling has a sharp edge: if the Redis-backed
limit check itself fails (e.g. Redis is down), the resulting exception is
caught and reported as `RateLimitExceeded` rather than propagating as an
infrastructure error — meaning a Redis outage would make protected routes
return 429 instead of failing open. `in_memory_fallback_enabled=True` below
mitigates this by falling back to an in-process counter if the Redis
backend becomes unreachable.

GLOBAL DEFAULT ENFORCEMENT — `DefaultRateLimitMiddleware`, not
`slowapi.middleware.SlowAPIMiddleware`:

Module 08 originally wired up `SlowAPIMiddleware` for this. Module 10's
live deployment validation discovered — by actually hammering a running
server with 150 rapid requests and observing zero 429s, not by reading
code — that `SlowAPIMiddleware` had gone silently non-functional for
every route without its own explicit `@limiter.limit(...)`/`@limiter.exempt`
decorator (i.e. everywhere except the auth endpoints and health probes).

Root cause: `SlowAPIMiddleware` finds the matching route by walking
`app.routes` and calling `route.matches(scope)` on each
(`slowapi/middleware.py::_find_route_handler`). FastAPI 0.139.0 (installed
per this project's unpinned `fastapi>=0.115.0` constraint — a real
dependency-drift issue in its own right) wraps `include_router()`'d routes
in an internal `_IncludedRouter` optimization object that this lookup
cannot see through, so it always returns `handler=None` for every
`/api/v1/*` and `/health/*` route. `slowapi` treats "no handler found" as
"exempt" (`_should_exempt`), so every route silently skipped the global
default check — verified directly: `_find_route_handler` returns `None`
for `/api/v1/institutions` on this FastAPI version, while `slowapi`'s own
`Limiter._check_request_limit` correctly enforces the limit when given
any real, stable callable.

`DefaultRateLimitMiddleware` below sidesteps this entirely: it doesn't
need to resolve which route matched at all — it calls
`Limiter._check_request_limit` with a fixed, stable module-level marker
function (giving it a non-empty, non-route-specific tracking key) for
every request outside the exempt path prefixes. This makes
`RATE_LIMIT_DEFAULT` a genuine per-client cap across the whole API surface
combined (not per-route) — a stricter, not weaker, interpretation of
"enforced globally," and immune to this FastAPI-version-specific
route-introspection incompatibility. See
`tests/test_rate_limit_middleware.py` for the regression test that would
have caught this.
"""

from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import get_settings

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=settings.REDIS_URI,
    in_memory_fallback_enabled=True,
)

# A stable, real module-level callable — never called, only inspected by
# slowapi for its `__module__`/`__name__` to build a tracking key. Must
# NOT be a lambda/closure (those don't have a stable, predictable name).
def _default_rate_limit_marker() -> None:  # pragma: no cover - never invoked
    pass


# Requests to these path prefixes bypass the global default entirely —
# mirrors `app/api/health.py`'s `@limiter.exempt` routes plus `/metrics`
# (scraped frequently by Prometheus, never user-facing).
_RATE_LIMIT_EXEMPT_PREFIXES = ("/health", "/metrics")


class DefaultRateLimitMiddleware(BaseHTTPMiddleware):
    """Enforces `RATE_LIMIT_DEFAULT` globally, independent of `slowapi`'s
    own (currently broken on this FastAPI version — see module docstring)
    route-introspection-based `SlowAPIMiddleware`."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        if not any(path.startswith(prefix) for prefix in _RATE_LIMIT_EXEMPT_PREFIXES):
            try:
                limiter._check_request_limit(request, _default_rate_limit_marker, True)
            except RateLimitExceeded as exc:
                return _rate_limit_exceeded_handler(request, exc)
        return await call_next(request)


def register_rate_limiting(app: FastAPI) -> None:
    """Attach the limiter and its exception handler to the FastAPI app."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
