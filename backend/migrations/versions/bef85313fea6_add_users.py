"""add users

Revision ID: bef85313fea6
Revises: 348fca5be192
Create Date: 2026-10-23 18:25:42.543822

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'bef85313fea6'
down_revision = '348fca5be192'
branch_labels = None
depends_on = None


def upgrade():
    # Some SQLite installs created the application tables before Alembic was
    # introduced. Adopt that existing users table in place instead of trying
    # to create it again, while adding the columns expected by the ORM.
    inspector = inspect(op.get_bind())
    if "users" not in inspector.get_table_names():
        op.create_table(
            "users",
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("display_name", sa.String(length=80), nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        )
    else:
        columns = {column["name"] for column in inspector.get_columns("users")}
        if "is_active" not in columns:
            op.add_column(
                "users",
                sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
            )
        if "updated_at" not in columns:
            # SQLite can't add a non-constant CURRENT_TIMESTAMP default to an
            # existing table. Backfill existing rows and let ORM defaults
            # populate it for subsequent ORM-created rows.
            op.add_column("users", sa.Column("updated_at", sa.DateTime(), nullable=True))
            op.execute("UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")

    indexes = {index["name"] for index in inspect(op.get_bind()).get_indexes("users")}
    if "ix_users_email" not in indexes:
        op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade():
    # This revision may have adopted a pre-Alembic table containing user data.
    # Keep that table and its data on downgrade; the later core-schema revision
    # owns destructive teardown for a full reset.
    indexes = {index["name"] for index in inspect(op.get_bind()).get_indexes("users")}
    if "ix_users_email" in indexes:
        op.drop_index("ix_users_email", table_name="users")
