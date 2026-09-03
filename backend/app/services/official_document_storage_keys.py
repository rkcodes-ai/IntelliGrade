"""
Object-storage key builders for `OfficialExamDocument` (Module 06).

Parallel to `app.services.storage_service`'s `build_original_key`/
`build_page_key` (Module 05, not modified — ADR-036), using the same
`StorageService` and the same MinIO bucket, just a different key prefix
(`official-exam-documents/` instead of the bare institution/script
prefix) so the two document families never collide.
"""

import uuid


def build_official_document_key(
    institution_id: uuid.UUID, document_id: uuid.UUID, filename: str
) -> str:
    return f"official-exam-documents/{institution_id}/{document_id}/original/{filename}"


def build_official_document_page_key(
    institution_id: uuid.UUID, document_id: uuid.UUID, page_number: int, extension: str
) -> str:
    return (
        f"official-exam-documents/{institution_id}/{document_id}/pages/"
        f"{page_number:04d}.{extension.lstrip('.')}"
    )
