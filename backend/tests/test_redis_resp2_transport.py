"""Unit tests for `app.tasks.redis_resp2_transport` (Six-Provider OCR
milestone, Phase 18) — verifies the `redis2://` transport/backend alias
registration and that the custom connection class actually forces RESP2 +
disables maintenance notifications, without requiring a live broker (the
real end-to-end proof — a genuine live Celery worker connecting to the
actual local Redis instance and processing a real task — was performed
manually during this milestone's real-infrastructure verification; this
test only guards the registration/connection-kwargs logic against
regressing silently)."""

from celery.app.backends import BACKEND_ALIASES
from kombu.transport import TRANSPORT_ALIASES

from app.tasks import redis_resp2_transport
from app.tasks.redis_resp2_transport import _RESP2Connection


def test_redis2_transport_alias_is_registered() -> None:
    assert TRANSPORT_ALIASES["redis2"] == f"{redis_resp2_transport.__name__}:Transport"


def test_redis2_backend_alias_is_registered() -> None:
    assert BACKEND_ALIASES["redis2"] == f"{redis_resp2_transport.__name__}:ResultBackend"


def test_resp2_connection_forces_protocol_2_regardless_of_input(monkeypatch) -> None:
    captured: dict = {}

    def fake_init(self, *args, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "redis.Connection.__init__", fake_init, raising=True
    )

    _RESP2Connection(protocol=3, maint_notifications_config="anything")

    assert captured["protocol"] == 2
    assert captured["maint_notifications_config"] is None


def test_channel_and_transport_use_resp2_connection_class() -> None:
    assert redis_resp2_transport._RESP2Channel.connection_class is _RESP2Connection
    assert redis_resp2_transport.Transport.Channel is redis_resp2_transport._RESP2Channel
