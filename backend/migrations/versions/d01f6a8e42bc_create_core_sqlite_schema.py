"""create the SQLite application schema through Alembic

Revision ID: d01f6a8e42bc
Revises: 8f5b1e213a0c
Create Date: 2026-10-27
"""

from alembic import op
import sqlite3


revision = "d01f6a8e42bc"
down_revision = "8f5b1e213a0c"
branch_labels = None
depends_on = None


def upgrade():
    # The existing SQLite schema contains triggers and legacy-compatible
    # ALTERs that cannot be represented by model autogeneration. Run the
    # idempotent schema initializer on Alembic's connection so the revision
    # records the entire application schema in one place.
    from app import init_db

    connection = op.get_bind().connection.driver_connection
    previous_row_factory = connection.row_factory
    try:
        connection.row_factory = sqlite3.Row
        init_db(connection)
    finally:
        connection.row_factory = previous_row_factory


def downgrade():
    # Downgrading past the application schema is a destructive operation,
    # matching the behavior of dropping the tables created by this revision.
    for table in (
        "guest_imports",
        "notifications",
        "workspace_invitations",
        "account_tokens",
        "auth_rate_limits",
        "assignments",
        "resources",
        "dependencies",
        "analysis_runs",
        "tasks",
        "projects",
        "calendars",
        "workspaces",
        "organization_memberships",
        "audit_events",
        "organizations",
        "schema_meta",
    ):
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
