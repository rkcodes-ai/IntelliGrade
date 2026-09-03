"""Global Search endpoint (Module 07, Feature 9)."""

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.schemas.search import SearchResults
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["Search"])


@router.get(
    "",
    response_model=SearchResults,
    dependencies=[Depends(require_permissions(PermissionCode.SEARCH_READ))],
)
async def global_search(
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    q: str = Query(min_length=1, max_length=200),
) -> SearchResults:
    service = SearchService(db)
    results = await service.search(institution_id, q)
    return SearchResults(query=q, results=results)
