"""
OCR provider (engine) catalog endpoints — global, non-tenant-scoped (ADR-028).

Read + update only — rows are seeded by migration, not created via the API,
and `code`/`name`/`is_implemented` are immutable after seeding (see
`app/schemas/ocr_provider.py`). `X-Institution-Id` is still required (via
`CurrentInstitutionDep`) for consistency with every other Module 05
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
from app.models.ocr_provider import OCRProvider
from app.schemas.ocr_provider import OCRProviderHealthRead, OCRProviderRead, OCRProviderUpdate
from app.schemas.pagination import Page, PageParams
from app.services.ocr.registry import get_provider_adapter
from app.services.ocr_provider_service import OCRProviderService

router = APIRouter(prefix="/ocr-providers", tags=["OCR Providers"])


def _to_read(entity: OCRProvider) -> OCRProviderRead:
    return OCRProviderRead.model_validate(entity)


@router.get(
    "",
    response_model=Page[OCRProviderRead],
    dependencies=[Depends(require_permissions(PermissionCode.OCR_PROVIDERS_READ))],
)
async def list_ocr_providers(
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    params: Annotated[PageParams, Depends()],
) -> Page[OCRProviderRead]:
    del institution_id  # resolved for auth/consistency only -- global catalog, not tenant-filtered
    service = OCRProviderService(db)
    items, total = await service.list_paginated(params)
    return Page.create([_to_read(i) for i in items], total=total, params=params)


@router.get(
    "/{entity_id}",
    response_model=OCRProviderRead,
    dependencies=[Depends(require_permissions(PermissionCode.OCR_PROVIDERS_READ))],
)
async def get_ocr_provider(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> OCRProviderRead:
    del institution_id  # resolved for auth/consistency only -- global catalog, not tenant-filtered
    service = OCRProviderService(db)
    entity = await service.get_by_id(entity_id)
    return _to_read(entity)


@router.get(
    "/{entity_id}/health",
    response_model=OCRProviderHealthRead,
    dependencies=[Depends(require_permissions(PermissionCode.OCR_PROVIDERS_READ))],
)
async def get_ocr_provider_health(
    entity_id: uuid.UUID, db: DbSession, institution_id: CurrentInstitutionDep
) -> OCRProviderHealthRead:
    """Live, on-demand engine health (installed/version/configured/auth/
    connectivity/GPU/ready) -- never persisted, always a fresh check
    against the real adapter (see `OCRProviderAdapter.health_check()`)."""
    del institution_id  # resolved for auth/consistency only -- global catalog, not tenant-filtered
    service = OCRProviderService(db)
    entity = await service.get_by_id(entity_id)
    adapter = get_provider_adapter(entity.code)
    result = adapter.health_check()
    return OCRProviderHealthRead.model_validate(result)


@router.patch(
    "/{entity_id}",
    response_model=OCRProviderRead,
    dependencies=[Depends(require_permissions(PermissionCode.OCR_PROVIDERS_UPDATE))],
)
async def update_ocr_provider(
    entity_id: uuid.UUID,
    body: OCRProviderUpdate,
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    current_user: CurrentUserDep,
) -> OCRProviderRead:
    del institution_id  # resolved for auth/consistency only -- global catalog, not tenant-filtered
    service = OCRProviderService(db)
    entity = await service.update(entity_id, body, updated_by=current_user.id)
    await db.commit()
    return _to_read(entity)
