"""Base schema classes shared across all API contracts."""

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base for all API schemas: ORM-friendly, strict extra-field handling."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra="forbid")


class ErrorDetail(BaseSchema):
    code: str
    message: str
    details: dict = {}


class ErrorResponse(BaseSchema):
    error: ErrorDetail
