"""SQLAlchemy models.

Import model modules here so Alembic autogenerate can discover their tables.
"""

from app.models.user import User

__all__ = ["User"]
