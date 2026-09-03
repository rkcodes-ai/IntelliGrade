"""
Tenant (Institution) resolution for the Academic Domain (Module 03).

New file — does NOT modify `app/core/rbac.py` or `app/api/deps.py`. Builds
entirely on top of the existing, unmodified `CurrentUserDep`. See ADR-015
in `ARCHITECTURE_DECISIONS.md` for the full rationale: per-resource/tenant
authorization is explicitly documented (`docs/rbac.md`, written in Module
02) as something that belongs here — an additional service/dependency
layer check — rather than inside `CurrentUser`/`require_permissions`,
which stay global, role/permission-only checks.

Every Module 03 endpoint that touches academic data depends on
`CurrentInstitutionDep` to resolve the tenant, then passes that
`institution_id` explicitly into its service call — never trusting a
client-supplied `institution_id` field inside a request body.
"""

import uuid
from typing import Annotated

from fastapi import Depends, Header

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import Role
from app.core.exceptions import ForbiddenError, ValidationAppError
from app.repositories.user_institution_repository import UserInstitutionRepository

INSTITUTION_HEADER = "X-Institution-Id"


async def get_current_institution_id(
    db: DbSession,
    current_user: CurrentUserDep,
    x_institution_id: Annotated[str | None, Header(alias=INSTITUTION_HEADER)] = None,
) -> uuid.UUID:
    """
    Resolve and authorize the institution (tenant) for this request.

    - Missing/malformed header -> 422 (client error, not a security event).
    - `super_admin` may address any institution ID without an explicit
      membership row (a global role check via the unmodified
      `CurrentUser.has_role`, consistent with `docs/rbac.md`).
    - Every other role must hold an active `UserInstitution` membership for
      the requested institution, or the request fails closed with 403.
    """
    if not x_institution_id:
        raise ValidationAppError(f"The '{INSTITUTION_HEADER}' header is required.")
    try:
        institution_id = uuid.UUID(x_institution_id)
    except ValueError as exc:
        raise ValidationAppError(f"'{INSTITUTION_HEADER}' must be a valid UUID.") from exc

    if current_user.has_role(Role.SUPER_ADMIN):
        return institution_id

    membership = await UserInstitutionRepository(db).get_membership(current_user.id, institution_id)
    if membership is None:
        raise ForbiddenError("You do not have access to this institution.")
    return institution_id


CurrentInstitutionDep = Annotated[uuid.UUID, Depends(get_current_institution_id)]
