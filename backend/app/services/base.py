"""Base service class establishing the application-service pattern."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger


class BaseService:
    """
    Base for application services.

    Services depend on repositories (never directly on `Request`/HTTP
    concerns) and own transaction boundaries via the injected session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.logger = get_logger(self.__class__.__name__)
