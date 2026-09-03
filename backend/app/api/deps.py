"""
Shared FastAPI dependencies re-exported for convenient endpoint imports.

Auth-related dependencies (`get_current_user`, `require_roles`,
`require_permissions`) live in `app/core/rbac.py` and are re-exported here
so endpoint modules only need one import path: `from app.api import deps`.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import CurrentUser, get_current_user, require_permissions, require_roles
from app.db.session import get_db_session

__all__ = [
    "CurrentUser",
    "DbSession",
    "CurrentUserDep",
    "get_current_user",
    "require_permissions",
    "require_roles",
]

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
