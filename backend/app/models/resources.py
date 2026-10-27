from app.extensions import db
from app.models.base import IntPKMixin, TimestampMixin, iso_utc


class Resource(IntPKMixin, TimestampMixin, db.Model):
    __tablename__ = "resources"

    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(120, collation="NOCASE"), nullable=False)
    role = db.Column(db.String(120), nullable=False, default="")
    capacity_work_minutes_per_day = db.Column(
        db.Integer, nullable=False, default=480
    )

    project = db.relationship("Project", back_populates="resources")
    assignments = db.relationship(
        "Assignment",
        back_populates="resource",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        db.CheckConstraint(
            "capacity_work_minutes_per_day > 0 AND "
            "capacity_work_minutes_per_day <= 1440",
            name="capacity_range",
        ),
        db.UniqueConstraint(
            "project_id",
            "name",
            name="uq_resources_project_name",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "role": self.role,
            "capacity_work_minutes_per_day": (
                self.capacity_work_minutes_per_day
            ),
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
        }

    def __repr__(self) -> str:
        return f"<Resource {self.name}>"


class Assignment(IntPKMixin, TimestampMixin, db.Model):
    __tablename__ = "assignments"

    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_id = db.Column(
        db.Integer,
        db.ForeignKey("resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id = db.Column(
        db.Integer,
        db.ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    allocation_percent = db.Column(db.Integer, nullable=False, default=100)

    project = db.relationship("Project", back_populates="assignments")
    resource = db.relationship("Resource", back_populates="assignments")
    task = db.relationship("Task", back_populates="assignments")

    __table_args__ = (
        db.CheckConstraint(
            "allocation_percent BETWEEN 1 AND 100",
            name="allocation_range",
        ),
        db.UniqueConstraint(
            "project_id",
            "resource_id",
            "task_id",
            name="uq_assignments_resource_task",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "resource_id": self.resource_id,
            "task_id": self.task_id,
            "allocation_percent": self.allocation_percent,
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
        }

    def __repr__(self) -> str:
        return f"<Assignment {self.resource_id}->{self.task_id}>"
