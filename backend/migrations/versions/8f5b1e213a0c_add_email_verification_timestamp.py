"""add email verification timestamp

Revision ID: 8f5b1e213a0c
Revises: bef85313fea6
Create Date: 2026-10-27
"""

from alembic import op
import sqlalchemy as sa


revision = "8f5b1e213a0c"
down_revision = "bef85313fea6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("users", "email_verified_at")
