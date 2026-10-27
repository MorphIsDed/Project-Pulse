"""add planning

Revision ID: 7a2b3c4d5e6f
Revises: 6f1a2b3c4d5e
Create Date: 2026-10-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "7a2b3c4d5e6f"
down_revision = "6f1a2b3c4d5e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "projects",
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120, collation="NOCASE"), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("target_finish", sa.Date(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'on_hold', 'completed', 'archived')",
            name="ck_projects_status",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_projects_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_projects_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
        sa.UniqueConstraint(
            "workspace_id", "name", name="uq_projects_workspace_name"
        ),
    )
    op.create_index(
        op.f("ix_projects_created_by"), "projects", ["created_by"], unique=False
    )
    op.create_index(
        op.f("ix_projects_workspace_id"), "projects", ["workspace_id"], unique=False
    )

    op.create_table(
        "project_calendars",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("weekly_rules", sa.JSON(), nullable=False),
        sa.Column("exceptions", sa.JSON(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_calendars_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_calendars")),
        sa.UniqueConstraint(
            "project_id", name="uq_project_calendars_project_id"
        ),
    )

    op.create_table(
        "tasks",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("parent_task_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("duration_work_minutes", sa.Integer(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("constraint_type", sa.String(length=32), nullable=False),
        sa.Column("constraint_date", sa.Date(), nullable=True),
        sa.Column("estimate_optimistic", sa.Integer(), nullable=True),
        sa.Column("estimate_most_likely", sa.Integer(), nullable=True),
        sa.Column("estimate_pessimistic", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('not_started', 'in_progress', 'blocked', 'completed')",
            name="ck_tasks_status",
        ),
        sa.CheckConstraint(
            "duration_work_minutes >= 0", name="ck_tasks_duration_nonnegative"
        ),
        sa.CheckConstraint(
            "progress BETWEEN 0 AND 100", name="ck_tasks_progress_range"
        ),
        sa.CheckConstraint(
            "priority BETWEEN 1 AND 5", name="ck_tasks_priority_range"
        ),
        sa.CheckConstraint(
            "constraint_type IN ('none', 'start_no_earlier_than', "
            "'start_no_later_than', 'must_start_on', 'finish_no_earlier_than', "
            "'finish_no_later_than', 'must_finish_on')",
            name="ck_tasks_constraint_type",
        ),
        sa.CheckConstraint(
            "(constraint_type = 'none' AND constraint_date IS NULL) OR "
            "(constraint_type <> 'none' AND constraint_date IS NOT NULL)",
            name="ck_tasks_constraint_date",
        ),
        sa.CheckConstraint(
            "(estimate_optimistic IS NULL AND estimate_most_likely IS NULL "
            "AND estimate_pessimistic IS NULL) OR "
            "(estimate_optimistic >= 0 AND estimate_most_likely >= "
            "estimate_optimistic AND estimate_pessimistic >= "
            "estimate_most_likely)",
            name="ck_tasks_estimates",
        ),
        sa.CheckConstraint(
            "parent_task_id IS NULL OR parent_task_id <> id",
            name="ck_tasks_parent_not_self",
        ),
        sa.ForeignKeyConstraint(
            ["parent_task_id"],
            ["tasks.id"],
            name=op.f("fk_tasks_parent_task_id_tasks"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_tasks_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
    )
    op.create_index(
        op.f("ix_tasks_parent_task_id"), "tasks", ["parent_task_id"], unique=False
    )
    op.create_index(
        op.f("ix_tasks_project_id"), "tasks", ["project_id"], unique=False
    )

    op.create_table(
        "dependencies",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("predecessor_task_id", sa.Integer(), nullable=False),
        sa.Column("successor_task_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=2), nullable=False),
        sa.Column("lag_work_minutes", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "type IN ('FS', 'SS', 'FF', 'SF')", name="ck_dependencies_type"
        ),
        sa.CheckConstraint(
            "predecessor_task_id <> successor_task_id",
            name="ck_dependencies_not_self",
        ),
        sa.ForeignKeyConstraint(
            ["predecessor_task_id"],
            ["tasks.id"],
            name=op.f("fk_dependencies_predecessor_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_dependencies_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["successor_task_id"],
            ["tasks.id"],
            name=op.f("fk_dependencies_successor_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dependencies")),
        sa.UniqueConstraint(
            "project_id",
            "predecessor_task_id",
            "successor_task_id",
            "type",
            name="uq_dependencies_link",
        ),
    )
    op.create_index(
        op.f("ix_dependencies_predecessor_task_id"),
        "dependencies",
        ["predecessor_task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dependencies_project_id"),
        "dependencies",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dependencies_successor_task_id"),
        "dependencies",
        ["successor_task_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_dependencies_successor_task_id"),
        table_name="dependencies",
    )
    op.drop_index(
        op.f("ix_dependencies_project_id"), table_name="dependencies"
    )
    op.drop_index(
        op.f("ix_dependencies_predecessor_task_id"),
        table_name="dependencies",
    )
    op.drop_table("dependencies")
    op.drop_index(op.f("ix_tasks_project_id"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_parent_task_id"), table_name="tasks")
    op.drop_table("tasks")
    op.drop_table("project_calendars")
    op.drop_index(op.f("ix_projects_workspace_id"), table_name="projects")
    op.drop_index(op.f("ix_projects_created_by"), table_name="projects")
    op.drop_table("projects")
