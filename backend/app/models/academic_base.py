"""
Multi-tenancy mixin for the Academic Domain (Module 03).

New file — does not modify `app/models/base.py` or any Module 02 model.
Every academic table composes `InstitutionOwnedMixin` alongside the
existing Module 02 mixins, e.g.:

    class Campus(
        UUIDPrimaryKeyMixin, InstitutionOwnedMixin, TimestampMixin,
        AuditActorMixin, SoftDeleteMixin, Base,
    ):
        ...

See ADR-016 (`ARCHITECTURE_DECISIONS.md`) for why `institution_id` is
denormalized onto every academic table directly, rather than derived
transitively through each entity's parent chain.
"""

import uuid

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column


class InstitutionOwnedMixin:
    """
    Adds a mandatory, indexed `institution_id` FK to `institutions.id`.

    Every Module 03 table except `Institution` itself (the tenant root)
    and `UserInstitution` (which references `institution_id` explicitly
    for its own join-table reasons) composes this mixin. Repositories
    built on `TenantScopedRepository` filter every query by this column —
    see `app/repositories/tenant_repository.py`.
    """

    institution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
