"""
Declarative base for all ORM models.

Every model in `app/models/` inherits from `Base`. Alembic's `env.py` imports
this metadata to autogenerate migrations — new models must be imported in
`app/db/base.py` (or an aggregator module) to be picked up.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all persistence models."""
