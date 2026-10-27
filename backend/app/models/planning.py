from copy import deepcopy

from app.extensions import db
from app.models.base import IntPKMixin, TimestampMixin, iso_date, iso_utc

PROJECT_STATUSES = ("active", "on_hold", "completed", "archived")
TASK_STATUSES = ("not_started", "in_progress", "blocked", "completed")
CONSTRAINT_TYPES = (
    "none",
    "start_no_earlier_than",
    "start_no_later_than",
    "must_start_on",
    "finish_no_earlier_than",
    "finish_no_later_than",
    "must_finish_on",
)
DEPENDENCY_TYPES = ("FS", "SS", "FF", "SF")

DEFAULT_WEEKLY_RULES = {
    "mon": [["09:00", "17:00"]],
    "tue": [["09:00", "17:00"]],
    "wed": [["09:00", "17:00"]],
    "thu": [["09:00", "17:00"]],
    "fri": [["09:00", "17:00"]],
    "sat": [],
    "sun": [],
}


def default_weekly_rules() -> dict:
    return deepcopy(DEFAULT_WEEKLY_RULES)


class Project(IntPKMixin, TimestampMixin, db.Model):
    __tablename__ = "projects"

    workspace_id = db.Column(
        db.Integer,
        db.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(120, collation="NOCASE"), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="active")
    start_date = db.Column(db.Date, nullable=True)
    target_finish = db.Column(db.Date, nullable=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    workspace = db.relationship("Workspace", back_populates="projects")
    calendar = db.relationship(
        "ProjectCalendar",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tasks = db.relationship(
        "Task",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    dependencies = db.relationship(
        "Dependency",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    resources = db.relationship(
        "Resource",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    assignments = db.relationship(
        "Assignment",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    creator = db.relationship("User")

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('active', 'on_hold', 'completed', 'archived')",
            name="status",
        ),
        db.UniqueConstraint(
            "workspace_id",
            "name",
            name="uq_projects_workspace_name",
        ),
    )

    def to_dict(self, role: str | None = None) -> dict:
        data = {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "status": self.status,
            "start_date": iso_date(self.start_date),
            "target_finish": iso_date(self.target_finish),
            "version": self.version,
            "calendar_id": self.calendar.id if self.calendar is not None else None,
            "created_by": self.created_by,
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
        }
        if role is not None:
            data["role"] = role
        return data

    def __repr__(self) -> str:
        return f"<Project {self.name}>"


class ProjectCalendar(IntPKMixin, TimestampMixin, db.Model):
    __tablename__ = "project_calendars"

    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = db.Column(db.String(120), nullable=False, default="Standard calendar")
    timezone = db.Column(db.String(64), nullable=False, default="UTC")
    weekly_rules = db.Column(
        db.JSON, nullable=False, default=default_weekly_rules
    )
    exceptions = db.Column(db.JSON, nullable=False, default=list)

    project = db.relationship("Project", back_populates="calendar")

    __table_args__ = (
        db.UniqueConstraint(
            "project_id",
            name="uq_project_calendars_project_id",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "timezone": self.timezone,
            "weekly_rules": self.weekly_rules,
            "exceptions": self.exceptions,
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
        }


class Task(IntPKMixin, TimestampMixin, db.Model):
    __tablename__ = "tasks"

    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_task_id = db.Column(
        db.Integer,
        db.ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.String(16), nullable=False, default="not_started")
    duration_work_minutes = db.Column(db.Integer, nullable=False, default=0)
    progress = db.Column(db.Integer, nullable=False, default=0)
    priority = db.Column(db.Integer, nullable=False, default=3)
    constraint_type = db.Column(db.String(32), nullable=False, default="none")
    constraint_date = db.Column(db.Date, nullable=True)
    estimate_optimistic = db.Column(db.Integer, nullable=True)
    estimate_most_likely = db.Column(db.Integer, nullable=True)
    estimate_pessimistic = db.Column(db.Integer, nullable=True)

    project = db.relationship("Project", back_populates="tasks")
    parent = db.relationship(
        "Task",
        remote_side="Task.id",
        back_populates="children",
    )
    children = db.relationship(
        "Task",
        back_populates="parent",
        passive_deletes=True,
    )
    assignments = db.relationship(
        "Assignment",
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('not_started', 'in_progress', 'blocked', 'completed')",
            name="status",
        ),
        db.CheckConstraint(
            "duration_work_minutes >= 0",
            name="duration_nonnegative",
        ),
        db.CheckConstraint(
            "progress BETWEEN 0 AND 100",
            name="progress_range",
        ),
        db.CheckConstraint(
            "priority BETWEEN 1 AND 5",
            name="priority_range",
        ),
        db.CheckConstraint(
            "constraint_type IN ('none', 'start_no_earlier_than', "
            "'start_no_later_than', 'must_start_on', 'finish_no_earlier_than', "
            "'finish_no_later_than', 'must_finish_on')",
            name="constraint_type",
        ),
        db.CheckConstraint(
            "(constraint_type = 'none' AND constraint_date IS NULL) OR "
            "(constraint_type <> 'none' AND constraint_date IS NOT NULL)",
            name="constraint_date",
        ),
        db.CheckConstraint(
            "(estimate_optimistic IS NULL AND estimate_most_likely IS NULL "
            "AND estimate_pessimistic IS NULL) OR "
            "(estimate_optimistic >= 0 AND estimate_most_likely >= "
            "estimate_optimistic AND estimate_pessimistic >= "
            "estimate_most_likely)",
            name="estimates",
        ),
        db.CheckConstraint(
            "parent_task_id IS NULL OR parent_task_id <> id",
            name="parent_not_self",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "parent_task_id": self.parent_task_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "duration_work_minutes": self.duration_work_minutes,
            "progress": self.progress,
            "priority": self.priority,
            "constraint_type": self.constraint_type,
            "constraint_date": iso_date(self.constraint_date),
            "estimate_optimistic": self.estimate_optimistic,
            "estimate_most_likely": self.estimate_most_likely,
            "estimate_pessimistic": self.estimate_pessimistic,
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
        }

    def __repr__(self) -> str:
        return f"<Task {self.name}>"


class Dependency(IntPKMixin, TimestampMixin, db.Model):
    __tablename__ = "dependencies"

    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    predecessor_task_id = db.Column(
        db.Integer,
        db.ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    successor_task_id = db.Column(
        db.Integer,
        db.ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = db.Column(db.String(2), nullable=False, default="FS")
    lag_work_minutes = db.Column(db.Integer, nullable=False, default=0)

    project = db.relationship("Project", back_populates="dependencies")
    predecessor = db.relationship(
        "Task", foreign_keys=[predecessor_task_id]
    )
    successor = db.relationship("Task", foreign_keys=[successor_task_id])

    __table_args__ = (
        db.CheckConstraint(
            "type IN ('FS', 'SS', 'FF', 'SF')",
            name="type",
        ),
        db.CheckConstraint(
            "predecessor_task_id <> successor_task_id",
            name="not_self",
        ),
        db.UniqueConstraint(
            "project_id",
            "predecessor_task_id",
            "successor_task_id",
            "type",
            name="uq_dependencies_link",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "predecessor_task_id": self.predecessor_task_id,
            "successor_task_id": self.successor_task_id,
            "type": self.type,
            "lag_work_minutes": self.lag_work_minutes,
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
        }

    def __repr__(self) -> str:
        return f"<Dependency {self.predecessor_task_id}->{self.successor_task_id}>"
