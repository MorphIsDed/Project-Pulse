"""SQLAlchemy models.

Import model modules here so Alembic autogenerate can discover their tables.
"""

from app.models.collaboration import Notification, WorkspaceInvitation
from app.models.planning import (
    Dependency,
    Project,
    ProjectCalendar,
    Task,
)
from app.models.resources import Assignment, Resource
from app.models.tenancy import (
    Organization,
    OrganizationMembership,
    Workspace,
)
from app.models.user import User

__all__ = [
    "Assignment",
    "Dependency",
    "Notification",
    "Organization",
    "OrganizationMembership",
    "Project",
    "ProjectCalendar",
    "Resource",
    "Task",
    "User",
    "Workspace",
    "WorkspaceInvitation",
]
