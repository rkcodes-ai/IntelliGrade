"""Response schemas for the health/readiness/liveness/version endpoints."""

from typing import Literal

from app.schemas.base import BaseSchema


class HealthResponse(BaseSchema):
    status: Literal["ok"]
    environment: str


class LivenessResponse(BaseSchema):
    status: Literal["alive"]


class ComponentStatus(BaseSchema):
    name: str
    healthy: bool


class ReadinessResponse(BaseSchema):
    status: Literal["ready", "not_ready"]
    components: list[ComponentStatus]


class VersionResponse(BaseSchema):
    name: str
    version: str
    environment: str
