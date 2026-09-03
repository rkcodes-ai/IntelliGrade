"""
Centralized application configuration.

All runtime configuration is sourced from environment variables (with sane
development defaults) via `pydantic-settings`. Never hardcode secrets here —
this module only defines *shape* and *defaults*, real values come from `.env`
or the process environment (see `backend/.env.example`).
"""

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, PostgresDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Known placeholder values that appear in this repo's own defaults/examples.
# A production deploy that copies an .env.example verbatim without editing
# it should still be caught — see `_reject_insecure_secret_in_production`.
_INSECURE_DEFAULT_SECRET_KEY = "dev-only-insecure-secret-change-me"
_KNOWN_INSECURE_SECRET_KEYS = {
    _INSECURE_DEFAULT_SECRET_KEY,
    "change_me_generate_with_openssl_rand_hex_32",
}
_MIN_PRODUCTION_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    """Application settings, loaded once and cached via `get_settings()`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- General ---
    PROJECT_NAME: str = "IntelliGrade"
    PROJECT_DESCRIPTION: str = "AI Answer Script Evaluation System"
    VERSION: str = "1.0.1"
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # --- Security / JWT ---
    SECRET_KEY: str = Field(
        default=_INSECURE_DEFAULT_SECRET_KEY,
        description="Used to sign JWTs. MUST be overridden in staging/production.",
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- Account lockout ---
    ACCOUNT_LOCKOUT_MAX_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_DURATION_MINUTES: int = 15

    # --- Password policy ---
    PASSWORD_HISTORY_DEPTH: int = 5
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # --- Refresh token cookie ---
    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"
    REFRESH_TOKEN_COOKIE_PATH: str = "/api/v1/auth"

    # --- CORS ---
    CORS_ORIGINS: list[AnyHttpUrl] | list[str] = ["http://localhost:5173"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # --- Database (async PostgreSQL) ---
    POSTGRES_USER: str = "intelligrade"
    POSTGRES_PASSWORD: str = "change_me_dev_only"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "intelligrade"
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    # Recycle pooled connections before a managed DB/load balancer silently
    # drops an idle one out from under us (a common failure mode behind
    # e.g. RDS/Cloud SQL/pgbouncer, which enforce their own idle timeouts) —
    # 1800s is a conservative default well under typical 3600s+ timeouts.
    DATABASE_POOL_RECYCLE_SECONDS: int = 1800
    # Any query taking longer than this is logged as `slow_query` (see
    # `app/db/session.py`) — 0 disables slow-query logging entirely.
    SLOW_QUERY_THRESHOLD_MS: int = 200
    # Bounds how long a *new* connection attempt (not a pooled one) may take
    # — asyncpg has no default here, so with the DB unreachable the
    # `/health/ready` probe was observed hanging for several seconds on plain
    # OS/DNS connect-timeout behavior before failing. Keep this comfortably
    # under any load-balancer/orchestrator probe timeout (docker-compose.prod.yml
    # uses 5s for the backend healthcheck).
    DATABASE_CONNECT_TIMEOUT_SECONDS: int = 3

    # --- Redis ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_DB: int = 0
    # Same rationale as DATABASE_CONNECT_TIMEOUT_SECONDS above — bounds the
    # readiness probe's Redis check when Redis is unreachable.
    REDIS_CONNECT_TIMEOUT_SECONDS: int = 3

    # --- Celery ---
    CELERY_BROKER_DB: int = 1
    CELERY_RESULT_BACKEND_DB: int = 2

    # --- Object storage (MinIO / S3-compatible) ---
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "intelligrade"
    MINIO_SECRET_KEY: str = "change_me_dev_only"
    MINIO_BUCKET_NAME: str = "intelligrade-uploads"
    MINIO_SECURE: bool = False

    # --- Answer Script upload / OCR pipeline (Module 05) ---
    UPLOAD_MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB per file
    UPLOAD_MAX_PAGE_COUNT: int = 60
    UPLOAD_CHUNK_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB — chunked/resumable upload unit
    UPLOAD_ALLOWED_MIME_TYPES: list[str] = [
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/tiff",
        "image/bmp",
        "image/webp",
    ]
    UPLOAD_TEMP_DIR: str = "/tmp/intelligrade-uploads"
    # `None` relies on the `tesseract` binary being on PATH (true in a
    # production Docker image that `apt install`s `tesseract-ocr`). Set
    # explicitly for local/dev environments where it isn't (e.g. a Windows
    # dev machine that installed it via winget to a non-PATH location).
    TESSERACT_CMD: str | None = None
    # Step 4.2 milestone: additional Indian-language `.traineddata` packs
    # live here (`backend/.tessdata/`) since the system Tesseract install's
    # own `tessdata/` directory (under `Program Files` on this dev machine)
    # isn't writable without elevation. `None` = use Tesseract's own
    # default tessdata search path (English/OSD only, unless the system
    # install has more packs).
    TESSERACT_TESSDATA_DIR: str | None = None
    OCR_MAX_RETRY_ATTEMPTS: int = 3
    OCR_TASK_SOFT_TIME_LIMIT_SECONDS: int = 300

    # --- Multi-OCR Platform (Module 12) ---
    # Optional global override for provider selection — the pipeline's
    # existing per-institution `OCRConfiguration` DB row still takes
    # priority when one exists; this only matters as a fallback (see
    # `app.tasks.ocr_tasks._resolve_provider_code`). `None` preserves the
    # pre-Module-12 behavior exactly (catalog default, then "tesseract").
    OCR_PROVIDER: str | None = None

    # EasyOCR (PyTorch-backed, local — no credentials, just a model download)
    OCR_EASYOCR_GPU: bool = False
    OCR_EASYOCR_LANGUAGES: list[str] = ["en"]
    OCR_EASYOCR_MODEL_DIR: str | None = None  # None = EasyOCR's own default (~/.EasyOCR)

    # PaddleOCR (local — no credentials, just a model download)
    OCR_PADDLEOCR_GPU: bool = False
    OCR_PADDLEOCR_LANGUAGE: str = "en"
    OCR_PADDLEOCR_DET_THRESHOLD: float = 0.3
    OCR_PADDLEOCR_REC_THRESHOLD: float = 0.5

    # Isolated OCR runtime bridge (Surya/docTR/TrOCR milestone) — each of
    # these three engines runs in its own venv (`.venv-surya`/`.venv-doctr`/
    # `.venv-trocr`, next to the pre-existing `.venv-paddleocr`) invoked via
    # `app.services.ocr.isolated_runtime`, never imported into the main
    # venv. `None` resolves to that default venv location relative to
    # `backend/` — see `isolated_runtime.default_isolated_python()`.
    OCR_ISOLATED_RUNTIME_STARTUP_TIMEOUT_SECONDS: float = 60.0
    OCR_ISOLATED_RUNTIME_INFERENCE_TIMEOUT_SECONDS: float = 300.0
    OCR_SURYA_PYTHON: str | None = None
    OCR_DOCTR_PYTHON: str | None = None
    OCR_TROCR_PYTHON: str | None = None
    OCR_TROCR_GPU: bool = False
    # PaddleOCR (Section 16 re-investigation): now also bridged through the
    # isolated runtime rather than imported in-process — see
    # `providers/paddleocr_provider.py`'s module docstring for why.
    OCR_PADDLEOCR_PYTHON: str | None = None

    # Math recognition (Step 4 milestone) — pix2tex (LaTeX-OCR, MIT
    # licensed) in its own `.venv-math`, same isolated-runtime bridge as
    # the OCR providers above. See `document_intelligence/math_recognition.py`.
    MATH_PYTHON: str | None = None

    # Language Quality Intelligence (Step 4.1 milestone) — local
    # LanguageTool (LGPL-2.1-or-later), the first non-Python isolated
    # runtime in this pipeline (Java, not a venv). `None` for either path
    # resolves via `language_quality._resolve_java_path`/`_resolve_jar_path`
    # (checks the known Temurin install location, then `backend/.languagetool/`).
    LANGUAGE_QUALITY_ENABLED: bool = True
    LANGUAGETOOL_JAVA_PATH: str | None = None
    LANGUAGETOOL_JAR_PATH: str | None = None
    LANGUAGETOOL_TIMEOUT_SECONDS: float = 30.0

    # Indian Multilingual Document Intelligence (Step 4.2 milestone) --
    # fastText lid.176 language identification, isolated in `.venv-langid`
    # (Python 3.12, not 3.13 -- see `isolated_runners/fasttext_runner.py`'s
    # docstring for why). `None` resolves via `default_isolated_python()`.
    LANGID_ENABLED: bool = True
    LANGID_PYTHON: str | None = None

    # AI Reference Answer Builder — local LLM extension (Step 5
    # milestone) -- llama-cpp-python (MIT) + Qwen2.5-1.5B-Instruct GGUF
    # (Apache 2.0), isolated in `.venv-reference-ai` (Python 3.12, same
    # universal-wheel/isolation rationale as `.venv-langid`). `None`
    # resolves via `default_isolated_python()`.
    REFERENCE_LLM_ENABLED: bool = True
    REFERENCE_LLM_PYTHON: str | None = None
    REFERENCE_LLM_TIMEOUT_SECONDS: float = 120.0

    # Google Cloud Vision — service-account JSON path, same shape as any
    # other Google Cloud SDK client (`GOOGLE_APPLICATION_CREDENTIALS` env
    # var is the SDK's own fallback if this is left unset).
    GOOGLE_VISION_CREDENTIALS_PATH: str | None = None
    GOOGLE_VISION_PROJECT_ID: str | None = None

    # Azure AI Document Intelligence
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str | None = None
    AZURE_DOCUMENT_INTELLIGENCE_API_KEY: str | None = None

    # AWS Textract — explicit keys are optional; boto3 already falls back
    # to the standard credential chain (IAM role, ~/.aws/credentials, env
    # vars) when these are left unset, exactly like the AWS CLI does.
    AWS_TEXTRACT_REGION: str | None = None
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_SESSION_TOKEN: str | None = None

    # --- Module 06 AI providers: OpenAI / Anthropic (AI Reference Answer
    # Builder milestone) — same "explicit key optional, real error if
    # neither present" shape as the OCR cloud providers above. ---
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-3-5-haiku-20241022"

    # --- Rate limiting ---
    RATE_LIMIT_DEFAULT: str = "100/minute"

    # --- Logging ---
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )

    @property
    def REDIS_URI(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}?protocol=2"

    def redis_uri_for_db(self, db: int) -> str:
        # `redis2://` (not `redis://`) opts into the RESP2-pinned transport
        # registered by `app.tasks.redis_resp2_transport` — kombu's redis
        # Channel builds its connection kwargs from a fixed dict with no
        # `protocol` key, so (unlike `REDIS_URI` below, which talks to
        # real redis-py directly and accepts `?protocol=2` as a plain query
        # param) Celery's broker/backend connections need this dedicated
        # transport alias instead. See that module's docstring for the full
        # rationale (RESP2 is the safe default for any Redis server this
        # app might point at, not just a workaround for one old install).
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis2://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{db}"

    @property
    def CELERY_BROKER_URL(self) -> str:
        return self.redis_uri_for_db(self.CELERY_BROKER_DB)

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return self.redis_uri_for_db(self.CELERY_RESULT_BACKEND_DB)

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @model_validator(mode="after")
    def _reject_insecure_secret_in_production(self) -> "Settings":
        # Fail fast at process startup rather than silently signing JWTs
        # with a known/weak key once this app is exposed to real users.
        # Checks both known placeholder strings AND a minimum-length
        # heuristic, since a careless deploy could set SECRET_KEY to
        # something short and guessable without using either placeholder.
        if not self.is_production:
            return self
        if self.SECRET_KEY in _KNOWN_INSECURE_SECRET_KEYS:
            raise ValueError(
                "SECRET_KEY is still a placeholder value from .env.example — set "
                "a real secret (e.g. `openssl rand -hex 32`) via the SECRET_KEY "
                "environment variable before running with ENVIRONMENT=production."
            )
        if len(self.SECRET_KEY) < _MIN_PRODUCTION_SECRET_KEY_LENGTH:
            raise ValueError(
                f"SECRET_KEY must be at least {_MIN_PRODUCTION_SECRET_KEY_LENGTH} "
                "characters in production (e.g. `openssl rand -hex 32`)."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance (read once per process)."""
    return Settings()
