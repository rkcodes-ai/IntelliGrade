"""
Shared pytest fixtures for the backend test suite.

Database strategy: an in-memory SQLite database per test function, not a
real PostgreSQL instance. This is a deliberate, documented trade-off (see
`ARCHITECTURE_DECISIONS.md` and `KNOWN_LIMITATIONS.md`) — `app.models.base`
uses SQLAlchemy's dialect-agnostic `Uuid`/`JSON` types specifically so the
exact same model definitions work against both SQLite (here) and
PostgreSQL (production), verified to produce identical DDL on PostgreSQL.
`StaticPool` is required so every connection within a test shares the same
in-memory database instead of each getting its own empty one.
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - registers all models on Base.metadata
from app.core.constants import DEFAULT_ROLE_PERMISSIONS, PermissionCode, Role
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app as fastapi_app
from app.middleware.rate_limit import limiter
from app.models.password_history import PasswordHistory
from app.models.permission import Permission
from app.models.role import Role as RoleModel
from app.models.role_permission import RolePermission
from app.models.user import User
from app.models.user_role import UserRole
from app.services.storage_service import StorageObjectMeta, StorageService, compute_sha256

#: In-memory stand-in for the MinIO bucket, keyed by object key. Module 05
#: only — no Docker/MinIO server is available in this sandbox (same
#: constraint as Postgres, see `KNOWN_LIMITATIONS.md`), so `_fake_storage`
#: below monkeypatches `StorageService`'s sync core to read/write this dict
#: instead of making a real network call, for every test in the suite.
_FAKE_BUCKET: dict[str, bytes] = {}


@pytest.fixture(autouse=True)
def _fake_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    _FAKE_BUCKET.clear()

    def put_bytes_sync(
        self: StorageService, key: str, data: bytes, content_type: str
    ) -> StorageObjectMeta:
        _FAKE_BUCKET[key] = data
        return StorageObjectMeta(
            key=key,
            size_bytes=len(data),
            checksum_sha256=compute_sha256(data),
            content_type=content_type,
        )

    def get_bytes_sync(self: StorageService, key: str) -> bytes:
        return _FAKE_BUCKET[key]

    def object_exists_sync(self: StorageService, key: str) -> bool:
        return key in _FAKE_BUCKET

    def delete_sync(self: StorageService, key: str) -> None:
        _FAKE_BUCKET.pop(key, None)

    def copy_sync(self: StorageService, source_key: str, dest_key: str) -> None:
        _FAKE_BUCKET[dest_key] = _FAKE_BUCKET[source_key]

    def presigned_get_url_sync(self: StorageService, key: str, expires_seconds: int = 3600) -> str:
        return f"http://fake-storage.test/{key}?expires={expires_seconds}"

    monkeypatch.setattr(StorageService, "put_bytes_sync", put_bytes_sync)
    monkeypatch.setattr(StorageService, "get_bytes_sync", get_bytes_sync)
    monkeypatch.setattr(StorageService, "object_exists_sync", object_exists_sync)
    monkeypatch.setattr(StorageService, "delete_sync", delete_sync)
    monkeypatch.setattr(StorageService, "copy_sync", copy_sync)
    monkeypatch.setattr(StorageService, "presigned_get_url_sync", presigned_get_url_sync)


@pytest.fixture(autouse=True)
def _disable_rate_limiter():
    """
    The rate limiter is a module-level singleton (by design — see
    `app/middleware/rate_limit.py`) with in-memory fallback storage whose
    counters persist for the life of the process — `Limiter.reset()`
    resets the *primary* (Redis) storage, not the fallback that's actually
    active once Redis is unreachable (as it is in this test environment),
    so counters would otherwise leak across every test hitting
    `/auth/login` from the same "127.0.0.1" test client address. Disabled
    by default; `test_security.py`'s rate-limit test re-enables it
    deliberately within its own scope.
    """
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession]:
    session_factory = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
async def seed_rbac(db_session: AsyncSession) -> dict[str, RoleModel]:
    """Seed the same baseline roles/permissions as migration 0003, via the ORM
    (not the migration itself) — fast, and exercises the same constants the
    real seed data is built from."""
    permissions_by_code: dict[PermissionCode, Permission] = {}
    for code in PermissionCode:
        perm = Permission(
            code=code.value, resource=code.value.split(":")[0], action=code.value.split(":")[1]
        )
        db_session.add(perm)
        permissions_by_code[code] = perm
    await db_session.flush()

    roles_by_name: dict[str, RoleModel] = {}
    for role in Role:
        role_row = RoleModel(name=role.value, description=f"{role.value} role", is_system=True)
        db_session.add(role_row)
        roles_by_name[role.value] = role_row
    await db_session.flush()

    for role, perms in DEFAULT_ROLE_PERMISSIONS.items():
        for perm_code in perms:
            db_session.add(
                RolePermission(
                    role_id=roles_by_name[role.value].id,
                    permission_id=permissions_by_code[perm_code].id,
                )
            )
    await db_session.flush()
    await db_session.commit()
    return roles_by_name


async def create_test_user(
    db_session: AsyncSession,
    *,
    email: str | None = None,
    username: str = "testuser",
    password: str = "CorrectHorse9!",
    full_name: str = "Test User",
    is_active: bool = True,
    role: RoleModel | None = None,
) -> User:
    """
    Test helper: create a persisted user, optionally with one role assigned.
    `email` defaults to `f"{username}@example.com"` — derived from
    `username` rather than a fixed literal, so tests creating several users
    in the same (per-test, isolated) database don't collide on the unique
    email constraint just because they only bothered to vary `username`.

    Also records the initial password in `password_history`, mirroring
    `UserService.create_user` — without this, a test's "try to reuse your
    current password" scenario would trivially (and misleadingly) pass,
    since there'd be no history for `PasswordService.assert_not_reused` to
    compare against.
    """
    hashed = hash_password(password)
    user = User(
        email=email or f"{username}@example.com",
        username=username,
        hashed_password=hashed,
        full_name=full_name,
        is_active=is_active,
        timezone="UTC",
        language="en",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(PasswordHistory(user_id=user.id, hashed_password=hashed))

    if role is not None:
        db_session.add(UserRole(user_id=user.id, role_id=role.id))
        await db_session.flush()

    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def client(db_engine) -> AsyncGenerator[AsyncClient]:
    """
    Async HTTP client wired to the ASGI app, with `get_db_session`
    overridden to use the per-test SQLite engine instead of the real
    PostgreSQL configuration. Health-check endpoints are unaffected — they
    use the module-level `app.db.session.engine` directly, not this
    dependency, so `/health/ready` still (correctly) reports the real
    configured database as unreachable in this environment.
    """
    session_factory = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    fastapi_app.dependency_overrides[get_db_session] = override_get_db_session
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:10]}@example.com"


def unique_username() -> str:
    return f"user_{uuid.uuid4().hex[:10]}"
