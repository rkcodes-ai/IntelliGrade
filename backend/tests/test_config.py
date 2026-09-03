"""Regression tests for `app.core.config.Settings`."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_development_allows_the_default_secret_key() -> None:
    # `_env_file=None` bypasses any real `.env` a developer may have created
    # on disk, so this test asserts the Python-level default deterministically.
    settings = Settings(_env_file=None, ENVIRONMENT="development")
    assert settings.SECRET_KEY == "dev-only-insecure-secret-change-me"


def test_production_rejects_the_default_secret_key() -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        Settings(ENVIRONMENT="production")


def test_production_rejects_the_env_example_placeholder() -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="change_me_generate_with_openssl_rand_hex_32",
        )


def test_production_rejects_a_short_secret_key() -> None:
    with pytest.raises(ValidationError, match="at least"):
        Settings(ENVIRONMENT="production", SECRET_KEY="too-short")


def test_production_accepts_a_real_secret_key() -> None:
    settings = Settings(ENVIRONMENT="production", SECRET_KEY="a" * 40)
    assert settings.is_production is True


def test_cors_origins_accepts_comma_separated_string() -> None:
    settings = Settings(CORS_ORIGINS="http://a.com, http://b.com")
    assert settings.CORS_ORIGINS == ["http://a.com", "http://b.com"]


def test_sqlalchemy_database_uri_uses_asyncpg_driver() -> None:
    settings = Settings()
    assert settings.SQLALCHEMY_DATABASE_URI.startswith("postgresql+asyncpg://")


def test_celery_urls_use_distinct_redis_databases() -> None:
    settings = Settings()
    assert settings.CELERY_BROKER_URL != settings.CELERY_RESULT_BACKEND
