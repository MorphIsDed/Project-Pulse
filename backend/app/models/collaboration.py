from app.extensions import db
from app.models.base import IntPKMixin, TimestampMixin, iso_utc


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

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "kind": self.kind,
            "message": self.message,
            "read_at": iso_utc(self.read_at),
            "created_at": iso_utc(self.created_at),
        }


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

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "email": self.email,
            "role": self.role,
            "expires_at": iso_utc(self.expires_at),
            "accepted_at": iso_utc(self.accepted_at),
            "created_at": iso_utc(self.created_at),
        }
