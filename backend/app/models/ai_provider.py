"""AIProvider — global AI evaluation engine catalog (Module 06).

Mirrors `app.models.ocr_provider.OCRProvider` exactly (see ADR-041): a
provider catalog is system/technical data, identical across every
institution, not per-tenant content — this does NOT compose
`InstitutionOwnedMixin`, and reuses the same `GlobalRepository`/
`GlobalService` base classes Module 05 introduced for `OCRProvider`.
"""

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import AuditActorMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AIProvider(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    AuditActorMixin,
    SoftDeleteMixin,
    Base,
):
    """
    Catalog entry for one AI evaluation engine (e.g. `"lexical_heuristic"`,
    a future `"anthropic"`). Rows are seeded by migration, not created via
    the API — the router only exposes `GET`/`PATCH`, identical convention
    to `OCRProvider`: `code`/`name`/`is_implemented` are immutable after
    seeding; only `is_enabled`/`is_default` are patchable, with the same
    "at most one default" / "enabled requires implemented" service-layer
    invariants as `OCRProviderService.update`.
    """

    __tablename__ = "ai_providers"

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_implemented: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AIProvider id={self.id} code={self.code!r}>"
