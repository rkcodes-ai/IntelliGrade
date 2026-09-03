"""Persistence access for `UploadJob`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.upload_job import UploadJob
from app.repositories.tenant_repository import TenantScopedRepository


class UploadJobRepository(TenantScopedRepository[UploadJob]):
    sortable_fields = ("status", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(UploadJob, session)

    async def get_by_token(self, institution_id: uuid.UUID, token: str) -> UploadJob | None:
        query = select(UploadJob).where(
            UploadJob.institution_id == institution_id,
            UploadJob.upload_session_token == token,
            UploadJob.deleted_at.is_(None),
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
