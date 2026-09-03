"""Persistence access for `AttendancePolicy`."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance_policy import AttendancePolicy
from app.repositories.tenant_repository import TenantScopedRepository


class AttendancePolicyRepository(TenantScopedRepository[AttendancePolicy]):
    search_fields = ("name",)
    sortable_fields = ("name", "created_at", "updated_at")

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AttendancePolicy, session)
