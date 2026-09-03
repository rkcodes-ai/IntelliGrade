"""
RESP2-pinned Celery/kombu Redis transport — compatibility shim for any
Redis-protocol server that predates RESP3 (Redis < 6.0; the native Windows
"Redis on Windows" 3.0.504 build available via `winget`/the historical
MSOpenTech port is the concrete case that motivated this, since upstream
Redis dropped native Windows support after the 3.x line).

**Why this exists**: `redis-py` >= 5 defaults every new connection to
attempting a RESP3 handshake (`HELLO` command) before falling back, and
any Redis server older than 6.0 rejects `HELLO` outright as an unknown
command — this app never uses a RESP3-only feature (client-side caching,
push messages, etc.), so RESP2 is strictly the safer, more portable
choice regardless of which Redis-compatible server a given environment
points at, not merely a workaround for one old local install.

`redis-py`'s own client accepts `protocol=2` directly, and
`Settings.REDIS_URI` (see `app.core.config`) passes it via a `?protocol=2`
query parameter for the app's own direct Redis usage (rate limiting,
readiness probes, `app.db.redis`) — but kombu's redis `Transport`/`Channel`
build their connection kwargs from a fixed, non-extensible dict
(`Channel._connparams()`), which has no `protocol` key and cannot be
handed one via `broker_transport_options` either. The supported kombu
extension point for this is overriding `Channel.connection_class` with a
custom `redis.Connection` subclass — registered here as a distinct
transport alias (`redis2`) so opting in is a one-line URL scheme change
(`redis2://...` instead of `redis://...`), never a silent global change to
every `redis://` connection kombu might make elsewhere.
"""

from __future__ import annotations

from typing import Any

import redis
from celery.app.backends import BACKEND_ALIASES
from celery.backends.redis import RedisBackend
from kombu.transport import TRANSPORT_ALIASES
from kombu.transport import redis as kombu_redis


class _RESP2Connection(redis.Connection):
    """Identical to `redis.Connection`, with `protocol` pinned to `2`
    regardless of what's passed in — RESP3 is never appropriate for a
    Celery broker/result-backend connection in this app.

    `maint_notifications_config` is force-disabled alongside it: redis-py
    8.x's Redis Enterprise "maintenance notifications" feature defaults to
    enabled and hard-raises (`RedisError: Maintenance notifications are
    only supported with hiredis and RESP3 parsers!`) the moment it detects
    a non-RESP3 connection — a feature this self-hosted, non-Enterprise
    Redis instance has no use for regardless of protocol version."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["protocol"] = 2
        kwargs["maint_notifications_config"] = None
        super().__init__(*args, **kwargs)  # type: ignore[no-untyped-call]


# `kombu` ships no py.typed marker (see the mypy override in pyproject.toml),
# so `Channel`/`Transport` resolve to `Any` — subclassing an `Any`-typed
# base is a real, accepted mypy limitation here, not a real type error;
# same "accepted, documented gap" treatment as this project's other
# untyped third-party SDKs.
class _RESP2Channel(kombu_redis.Channel):  # type: ignore[misc]
    connection_class = _RESP2Connection


class Transport(kombu_redis.Transport):  # type: ignore[misc]
    Channel = _RESP2Channel


class ResultBackend(RedisBackend):  # type: ignore[misc]
    """`celery.backends.redis.RedisBackend` builds its own connection
    kwargs entirely independently of kombu's `Channel` above (a separate
    class hierarchy, not routed through `TRANSPORT_ALIASES` at all) — so
    the result backend needs its own, separate RESP2 fix: inject the same
    `connection_class` override into `self.connparams` right after the
    real `RedisBackend.__init__` builds it."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.connparams["connection_class"] = _RESP2Connection


# Registers the `redis2://` URL scheme for both the broker (kombu transport
# alias) and the result backend (Celery's own, separate alias registry) —
# see module docstring for why this is a distinct opt-in scheme rather than
# overriding the existing `redis`/`rediss` aliases in place.
TRANSPORT_ALIASES["redis2"] = f"{__name__}:Transport"
BACKEND_ALIASES["redis2"] = f"{__name__}:ResultBackend"
