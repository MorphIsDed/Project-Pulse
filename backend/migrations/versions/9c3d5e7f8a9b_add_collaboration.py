"""add collaboration notifications and invitations

Revision ID: 9c3d5e7f8a9b
Revises: 8b3c4d5e6f7a
Create Date: 2026-10-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "9c3d5e7f8a9b"
down_revision = "8b3c4d5e6f7a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notifications",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_notifications_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_notifications_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_notifications_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(
        op.f("ix_notifications_created_at"),
        "notifications",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_organization_id"),
        "notifications",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_project_id"),
        "notifications",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_user_id"),
        "notifications",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "workspace_invitations",
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column(
            "email",
            sa.String(length=320, collation="NOCASE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by", sa.Integer(), nullable=True),
        sa.Column(
            "expires_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "role IN ('admin', 'editor', 'viewer')",
            name=op.f("ck_workspace_invitations_invitation_role"),
        ),
        sa.ForeignKeyConstraint(
            ["invited_by"],
            ["users.id"],
            name=op.f(
                "fk_workspace_invitations_invited_by_users"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f(
                "fk_workspace_invitations_organization_id_organizations"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id", name=op.f("pk_workspace_invitations")
        ),
        sa.UniqueConstraint(
            "token_hash", name=op.f("uq_workspace_invitations_token_hash")
        ),
    )
    op.create_index(
        op.f("ix_workspace_invitations_created_at"),
        "workspace_invitations",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workspace_invitations_email"),
        "workspace_invitations",
        ["email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workspace_invitations_organization_id"),
        "workspace_invitations",
        ["organization_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_workspace_invitations_organization_id"),
        table_name="workspace_invitations",
    )
    op.drop_index(
        op.f("ix_workspace_invitations_email"),
        table_name="workspace_invitations",
    )
    op.drop_index(
        op.f("ix_workspace_invitations_created_at"),
        table_name="workspace_invitations",
    )
    op.drop_table("workspace_invitations")
    op.drop_index(
        op.f("ix_notifications_user_id"), table_name="notifications"
    )
    op.drop_index(
        op.f("ix_notifications_project_id"), table_name="notifications"
    )
    op.drop_index(
        op.f("ix_notifications_organization_id"),
        table_name="notifications",
    )
    op.drop_index(
        op.f("ix_notifications_created_at"), table_name="notifications"
    )
    op.drop_table("notifications")
