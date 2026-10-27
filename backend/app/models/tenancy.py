from app.extensions import db
from app.models.base import IntPKMixin, TimestampMixin, iso_utc

ORGANIZATION_ROLES = ("owner", "admin", "editor", "viewer")


class Organization(IntPKMixin, TimestampMixin, db.Model):
    __tablename__ = "organizations"

    name = db.Column(db.String(120), nullable=False, index=True)

    memberships = db.relationship(
        "OrganizationMembership",
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    workspaces = db.relationship(
        "Workspace",
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def to_dict(self, role: str | None = None) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
        }
        if role is not None:
            data["role"] = role
        return data

    def __repr__(self) -> str:
        return f"<Organization {self.name}>"


class OrganizationMembership(TimestampMixin, db.Model):
    __tablename__ = "organization_memberships"

    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    role = db.Column(db.String(16), nullable=False, default="viewer")

    organization = db.relationship("Organization", back_populates="memberships")
    user = db.relationship("User")

    __table_args__ = (
        db.CheckConstraint(
            "role IN ('owner', 'admin', 'editor', 'viewer')",
            name="role",
        ),
    )

    def to_dict(self, include_user: bool = False) -> dict:
        data = {
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "role": self.role,
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
        }
        if include_user and self.user is not None:
            data["user"] = self.user.to_dict()
        return data


class Workspace(IntPKMixin, TimestampMixin, db.Model):
    __tablename__ = "workspaces"

    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(120, collation="NOCASE"), nullable=False)

    organization = db.relationship("Organization", back_populates="workspaces")
    projects = db.relationship(
        "Project",
        back_populates="workspace",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "organization_id",
            "name",
            name="uq_workspaces_organization_name",
        ),
    )

    def to_dict(self, role: str | None = None) -> dict:
        data = {
            "id": self.id,
            "organization_id": self.organization_id,
            "name": self.name,
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
        }
        if role is not None:
            data["role"] = role
        return data

    def __repr__(self) -> str:
        return f"<Workspace {self.name}>"
