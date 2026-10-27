"""Legacy storage retained for existing database and migration compatibility."""

from app.extensions import db
from app.models.base import IntPKMixin


class Notification(IntPKMixin, db.Model):
    __tablename__ = "notifications"

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    task_id = db.Column(
        db.Integer,
        db.ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=True,
    )
    kind = db.Column(db.String(40), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    read_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, index=True
    )



class WorkspaceInvitation(IntPKMixin, db.Model):
    __tablename__ = "workspace_invitations"

    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email = db.Column(
        db.String(320, collation="NOCASE"), nullable=False, index=True
    )
    role = db.Column(db.String(16), nullable=False, default="viewer")
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    invited_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    accepted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, index=True
    )

    __table_args__ = (
        db.CheckConstraint(
            "role IN ('admin', 'editor', 'viewer')",
            name="invitation_role",
        ),
    )
