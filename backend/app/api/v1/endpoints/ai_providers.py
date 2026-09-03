"""
AI provider (evaluation engine) catalog endpoints — global, non-tenant-scoped.

Read + update only — rows are seeded by migration, not created via the API,
and `code`/`name`/`is_implemented` are immutable after seeding (see
`app/schemas/ai_provider.py`). `X-Institution-Id` is still required (via
`CurrentInstitutionDep`) for consistency with every other Module 06
endpoint, even though it isn't used to filter the query -- every institution
sees the same global catalog.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUserDep, DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.models.ai_provider import AIProvider
from app.schemas.ai_provider import AIProviderRead, AIProviderUpdate
from app.schemas.pagination import Page, PageParams
from app.services.ai_provider_service import AIProviderService

router = APIRouter(prefix="/ai-providers", tags=["AI Providers"])


def _to_read(entity: AIProvider) -> AIProviderRead:
    return AIProviderRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[AIProviderRead],
    dependencies=[Depends(require_permissions(PermissionCode.AI_PROVIDERS_READ))],
)
async def list_ai_providers(
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    params: Annotated[PageParams, Depends()],
) -> Page[AIProviderRead]:
    del institution_id  # resolved for auth/consistency only -- global catalog, not tenant-filtered
    service = AIProviderService(db)
    items, total = await service.list_paginated(params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/{entity_id}",
    response_model=AIProviderRead,
    dependencies=[Depends(require_permissions(PermissionCode.AI_PROVIDERS_READ))],
)
async def get_ai_provider(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> AIProviderRead:
    del institution_id  # resolved for auth/consistency only -- global catalog, not tenant-filtered
    service = AIProviderService(db)
    entity = await service.get_by_id(entity_id)
    return _to_read(entity)


@router.patch(
    "/{entity_id}",
    response_model=AIProviderRead,
    dependencies=[Depends(require_permissions(PermissionCode.AI_PROVIDERS_UPDATE))],
)
async def update_ai_provider(
    entity_id: uuid.UUID,
    body: AIProviderUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> AIProviderRead:
    del institution_id  # resolved for auth/consistency only -- global catalog, not tenant-filtered
    service = AIProviderService(db)
    entity = await service.update(entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)
