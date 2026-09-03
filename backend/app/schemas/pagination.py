"""
Shared pagination/filtering/sorting contract for the Academic Domain.

No pagination convention existed anywhere in the codebase before this
module (Module 02's `list_users` used bare `limit`/`offset` with no
envelope) — see ADR-018. `PageParams` is a FastAPI dependency every
Module 03 list endpoint declares; `Page[T]` is the generic response
envelope every Module 03 list endpoint returns.
"""

from enum import StrEnum

from fastapi import Query
from pydantic import Field

from app.schemas.base import BaseSchema

MAX_PAGE_SIZE = 200


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class PageParams:
    """
    Query-param dependency: `?page=1&page_size=25&search=foo&sort_by=name&sort_order=asc`.

    Usage in an endpoint:

        async def list_campuses(params: Annotated[PageParams, Depends()]) -> Page[CampusRead]:
            ...
    """

    def __init__(
        self,
        page: int = Query(default=1, ge=1, description="1-indexed page number"),
        page_size: int = Query(default=25, ge=1, le=MAX_PAGE_SIZE),
        search: str | None = Query(default=None, max_length=200),
        sort_by: str | None = Query(default=None, max_length=64),
        sort_order: SortOrder = Query(default=SortOrder.ASC),
    ) -> None:
        self.page = page
        self.page_size = page_size
        self.search = search
        self.sort_by = sort_by
        self.sort_order = sort_order

    @property
    def limit(self) -> int:
        return self.page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class Page[T](BaseSchema):
    """Generic paginated response envelope."""

    items: list[T] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def create(cls, items: list[T], *, total: int, params: PageParams) -> "Page[T]":
        total_pages = (total + params.page_size - 1) // params.page_size if params.page_size else 0
        return cls(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=max(total_pages, 1) if total > 0 else 0,
        )
