"""
OCR provider benchmark endpoint (Module 12) — runs one uploaded page image
through every requested OCR provider and reports comparable accuracy/
confidence/performance metrics for each. See
`app.services.ocr_benchmark_service.OCRBenchmarkService` for the actual
run/measurement logic; this router only handles the multipart upload and
temp-file lifecycle.

Gated behind `OCR_PROVIDERS_UPDATE` (not `_READ`) -- unlike every other
Module 05 OCR endpoint, this one actually executes live OCR engines (real
compute, real cloud-API calls against credentials-gated providers), so it
gets the same "administrative action" permission level as enabling/
disabling a provider, not a read-only permission.

Nothing here is persisted -- see the service module's docstring for why.
"""

import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps import DbSession
from app.core.constants import PermissionCode
from app.core.rbac import require_permissions
from app.core.tenancy import CurrentInstitutionDep
from app.schemas.ocr_benchmark import BenchmarkReportRead
from app.services.ocr_benchmark_service import OCRBenchmarkService

router = APIRouter(prefix="/ocr-providers", tags=["OCR Providers"])


@router.post(
    "/benchmark",
    response_model=BenchmarkReportRead,
    dependencies=[Depends(require_permissions(PermissionCode.OCR_PROVIDERS_UPDATE))],
)
async def run_ocr_benchmark(
    db: DbSession,
    institution_id: CurrentInstitutionDep,
    file: Annotated[UploadFile, File()],
    language: Annotated[str, Form()] = "eng",
    provider_codes: Annotated[str | None, Form()] = None,
    reference_text: Annotated[str | None, Form()] = None,
) -> BenchmarkReportRead:
    """`provider_codes` is an optional comma-separated list (e.g.
    `"tesseract,easyocr"`); omitted means every registered provider.
    `reference_text` is an optional human-verified transcription of the
    uploaded page -- supplying it enables word/character accuracy scoring,
    otherwise those fields are `null` (never fabricated)."""
    del db, institution_id  # resolved for auth/consistency only -- no tenant data is touched

    codes = (
        [code.strip() for code in provider_codes.split(",") if code.strip()]
        if provider_codes
        else None
    )

    suffix = Path(file.filename or "").suffix or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        service = OCRBenchmarkService()
        report = service.run(
            tmp_path,
            language=language,
            provider_codes=codes,
            reference_text=reference_text,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return BenchmarkReportRead.model_validate(report)
