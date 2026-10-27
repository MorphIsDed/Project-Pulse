"""add resources

Revision ID: 8b3c4d5e6f7a
Revises: 7a2b3c4d5e6f
Create Date: 2026-10-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "8b3c4d5e6f7a"
down_revision = "7a2b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "resources",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column(
            "name",
            sa.String(length=120, collation="NOCASE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=120), nullable=False),
        sa.Column(
            "capacity_work_minutes_per_day",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "capacity_work_minutes_per_day > 0 AND "
            "capacity_work_minutes_per_day <= 1440",
            name="ck_resources_capacity_range",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_resources_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resources")),
        sa.UniqueConstraint(
            "project_id",
            "name",
            name="uq_resources_project_name",
        ),
    )
    op.create_index(
        op.f("ix_resources_project_id"),
        "resources",
        ["project_id"],
        unique=False,
    )

    op.create_table(
        "assignments",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("allocation_percent", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "allocation_percent BETWEEN 1 AND 100",
            name="ck_assignments_allocation_range",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_assignments_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["resources.id"],
            name=op.f("fk_assignments_resource_id_resources"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_assignments_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assignments")),
        sa.UniqueConstraint(
            "project_id",
            "resource_id",
            "task_id",
            name="uq_assignments_resource_task",
        ),
    )
    op.create_index(
        op.f("ix_assignments_project_id"),
        "assignments",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assignments_resource_id"),
        "assignments",
        ["resource_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assignments_task_id"),
        "assignments",
        ["task_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_assignments_task_id"), table_name="assignments"
    )
    op.drop_index(
        op.f("ix_assignments_resource_id"), table_name="assignments"
    )
    op.drop_index(
        op.f("ix_assignments_project_id"), table_name="assignments"
    )
    op.drop_table("assignments")
    op.drop_index(
        op.f("ix_resources_project_id"), table_name="resources"
    )
    op.drop_table("resources")
