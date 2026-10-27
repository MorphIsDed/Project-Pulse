from collections import defaultdict
from datetime import date

from sqlalchemy.exc import IntegrityError

from app.errors import ApiError
from app.extensions import db
from app.models.base import utcnow
from app.models.planning import (
    CONSTRAINT_TYPES,
    DEPENDENCY_TYPES,
    PROJECT_STATUSES,
    TASK_STATUSES,
    Dependency,
    Project,
    ProjectCalendar,
    Task,
    default_weekly_rules,
)
from app.models.tenancy import Workspace


TASK_CREATE_FIELDS = {
    "name",
    "description",
    "status",
    "duration_work_minutes",
    "progress",
    "priority",
    "parent_task_id",
    "constraint_type",
    "constraint_date",
    "estimate_optimistic",
    "estimate_most_likely",
    "estimate_pessimistic",
}
TASK_UPDATE_FIELDS = TASK_CREATE_FIELDS
ESTIMATE_FIELDS = (
    "estimate_optimistic",
    "estimate_most_likely",
    "estimate_pessimistic",
)


def _clean_name(value, label: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise ApiError("invalid_name", f"{label} name is required.", 400)
    name = value.strip()
    if not name:
        raise ApiError("invalid_name", f"{label} name is required.", 400)
    if len(name) > max_length:
        raise ApiError(
            "invalid_name",
            f"{label} name must be {max_length} characters or fewer.",
            400,
        )
    return name


def _parse_date(value, field: str, code: str = "invalid_date") -> date | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ApiError(code, f"{field} must use YYYY-MM-DD.", 400)
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ApiError(
            code, f"{field} must use YYYY-MM-DD.", 400
        ) from None


def _validate_date_range(start_date, target_finish) -> None:
    if start_date is not None and target_finish is not None:
        if target_finish < start_date:
            raise ApiError(
                "invalid_date_range",
                "Target finish must be on or after the project start date.",
                400,
            )


def _reject_unknown(data: dict, allowed: set[str]) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ApiError(
            "unsupported_field",
            "One or more fields cannot be updated.",
            400,
            {"fields": unknown},
        )


def _validate_int(
    value,
    field: str,
    code: str,
    message: str,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if type(value) is not int:
        raise ApiError(code, message, 400, {"field": field})
    if minimum is not None and value < minimum:
        raise ApiError(code, message, 400, {"field": field})
    if maximum is not None and value > maximum:
        raise ApiError(code, message, 400, {"field": field})
    return value


def _parse_estimates(values) -> tuple[int | None, int | None, int | None]:
    if all(value is None for value in values):
        return None, None, None
    if any(type(value) is not int or value < 0 for value in values):
        raise ApiError(
            "invalid_estimates",
            "Provide optimistic, most likely, and pessimistic estimates "
            "in ascending order.",
            400,
        )
    optimistic, likely, pessimistic = values
    if not optimistic <= likely <= pessimistic:
        raise ApiError(
            "invalid_estimates",
            "Provide optimistic, most likely, and pessimistic estimates "
            "in ascending order.",
            400,
        )
    return optimistic, likely, pessimistic


def _validate_parent(
    project_id: int,
    parent_task_id,
    task_id: int | None = None,
) -> int | None:
    if parent_task_id is None:
        return None
    if type(parent_task_id) is not int:
        raise ApiError(
            "invalid_parent",
            "Parent task ID must be an integer.",
            400,
        )
    if task_id is not None and parent_task_id == task_id:
        raise ApiError(
            "invalid_parent",
            "A task cannot be its own parent.",
            400,
        )

    parent = db.session.get(Task, parent_task_id)
    if parent is None or parent.project_id != project_id:
        raise ApiError(
            "invalid_parent",
            "Parent task must belong to this project.",
            400,
        )

    if task_id is not None:
        seen = set()
        cursor = parent
        while cursor is not None and cursor.id not in seen:
            if cursor.id == task_id:
                raise ApiError(
                    "parent_cycle",
                    "That parent would create a task hierarchy cycle.",
                    400,
                )
            seen.add(cursor.id)
            cursor = (
                db.session.get(Task, cursor.parent_task_id)
                if cursor.parent_task_id is not None
                else None
            )
    return parent_task_id


def _validate_constraint(
    constraint_type,
    constraint_date,
) -> tuple[str, date | None]:
    if constraint_type not in CONSTRAINT_TYPES:
        raise ApiError(
            "invalid_constraint",
            "Choose a supported task constraint.",
            400,
        )
    parsed_date = constraint_date
    if not isinstance(parsed_date, date):
        parsed_date = _parse_date(
            parsed_date, "constraint_date", "invalid_constraint_date"
        )
    if constraint_type == "none":
        if parsed_date is not None:
            raise ApiError(
                "invalid_constraint_date",
                "A constraint date is not allowed when the constraint is none.",
                400,
            )
        return constraint_type, None
    if parsed_date is None:
        raise ApiError(
            "invalid_constraint_date",
            "Choose a constraint date for this constraint type.",
            400,
        )
    return constraint_type, parsed_date


def _bump_project_version(project: Project) -> None:
    project.version = (project.version or 0) + 1
    project.updated_at = utcnow()


def list_projects(
    workspace_id: int,
    role: str,
    limit: int,
    offset: int,
) -> list[dict]:
    projects = db.session.scalars(
        db.select(Project)
        .where(Project.workspace_id == workspace_id)
        .order_by(Project.name, Project.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [project.to_dict(role=role) for project in projects]


def create_project(workspace: Workspace, user_id: int, data: dict) -> Project:
    _reject_unknown(data, {"name", "start_date", "target_finish"})
    name = _clean_name(data.get("name"), "Project", 120)
    start_date = _parse_date(data.get("start_date"), "start_date")
    target_finish = _parse_date(data.get("target_finish"), "target_finish")
    _validate_date_range(start_date, target_finish)

    project = Project(
        workspace_id=workspace.id,
        name=name,
        status="active",
        start_date=start_date,
        target_finish=target_finish,
        version=1,
        created_by=user_id,
    )
    project.calendar = ProjectCalendar(
        weekly_rules=default_weekly_rules(),
        exceptions=[],
    )
    db.session.add(project)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError(
            "project_conflict",
            "A project with that name already exists in this workspace.",
            409,
        ) from None
    return project


def update_project(project: Project, data: dict) -> Project:
    if not data:
        raise ApiError("empty_update", "Send project fields to update.", 400)
    _reject_unknown(data, {"version", "name", "status", "start_date", "target_finish"})

    expected_version = data.get("version")
    if type(expected_version) is not int:
        raise ApiError(
            "validation_error",
            "Project version is required.",
            400,
            {"fields": ["version"]},
        )
    if expected_version != project.version:
        raise ApiError(
            "stale_project",
            "The project changed since it was loaded. Refresh and try again.",
            409,
        )

    updates = {}
    if "name" in data:
        updates["name"] = _clean_name(data["name"], "Project", 120)
    if "status" in data:
        if data["status"] not in PROJECT_STATUSES:
            raise ApiError(
                "invalid_status",
                "Choose active, on_hold, completed, or archived.",
                400,
            )
        updates["status"] = data["status"]

    for field in ("start_date", "target_finish"):
        if field in data:
            updates[field] = _parse_date(data[field], field)

    if not updates:
        raise ApiError("empty_update", "Send project fields to update.", 400)

    final_start = updates.get("start_date", project.start_date)
    final_target = updates.get("target_finish", project.target_finish)
    _validate_date_range(final_start, final_target)

    updated = db.session.execute(
        db.update(Project)
        .where(Project.id == project.id, Project.version == expected_version)
        .values(
            **updates,
            version=Project.version + 1,
            updated_at=utcnow(),
        )
    )
    if updated.rowcount == 0:
        db.session.rollback()
        raise ApiError(
            "stale_project",
            "The project changed since it was loaded. Refresh and try again.",
            409,
        )
    db.session.commit()
    db.session.refresh(project)
    return project


def delete_project(project: Project) -> None:
    db.session.delete(project)
    db.session.commit()


def get_calendar(project: Project) -> ProjectCalendar:
    calendar = project.calendar
    if calendar is None:
        calendar = ProjectCalendar(
            project=project,
            weekly_rules=default_weekly_rules(),
            exceptions=[],
        )
        db.session.add(calendar)
        db.session.commit()
    return calendar


def list_tasks(
    project_id: int,
    limit: int,
    offset: int,
    status: str | None = None,
    parent_task_id: int | None = None,
) -> list[dict]:
    statement = db.select(Task).where(Task.project_id == project_id)
    if status is not None:
        if status not in TASK_STATUSES:
            raise ApiError(
                "invalid_status",
                "Choose not_started, in_progress, blocked, or completed.",
                400,
            )
        statement = statement.where(Task.status == status)
    if parent_task_id is not None:
        statement = statement.where(Task.parent_task_id == parent_task_id)
    tasks = db.session.scalars(
        statement.order_by(Task.id).limit(limit).offset(offset)
    ).all()
    return [task.to_dict() for task in tasks]


def create_task(project: Project, data: dict) -> Task:
    _reject_unknown(data, TASK_CREATE_FIELDS)
    name = _clean_name(data.get("name"), "Task", 200)
    description = data.get("description", "")
    if not isinstance(description, str):
        raise ApiError("invalid_description", "Description must be text.", 400)

    status = data.get("status", "not_started")
    if status not in TASK_STATUSES:
        raise ApiError(
            "invalid_status",
            "Choose not_started, in_progress, blocked, or completed.",
            400,
        )
    duration = _validate_int(
        data.get("duration_work_minutes", 0),
        "duration_work_minutes",
        "invalid_duration",
        "Duration must be a non-negative integer in working minutes.",
        minimum=0,
    )
    progress = _validate_int(
        data.get("progress", 0),
        "progress",
        "invalid_progress",
        "Progress must be an integer from 0 to 100.",
        minimum=0,
        maximum=100,
    )
    priority = _validate_int(
        data.get("priority", 3),
        "priority",
        "invalid_priority",
        "Priority must be an integer from 1 to 5.",
        minimum=1,
        maximum=5,
    )
    parent_task_id = _validate_parent(
        project.id, data.get("parent_task_id")
    )
    constraint_type, constraint_date = _validate_constraint(
        data.get("constraint_type", "none"),
        data.get("constraint_date"),
    )
    estimates = [
        data.get(field) for field in ESTIMATE_FIELDS
    ]
    optimistic, likely, pessimistic = _parse_estimates(estimates)

    task = Task(
        project_id=project.id,
        parent_task_id=parent_task_id,
        name=name,
        description=description,
        status=status,
        duration_work_minutes=duration,
        progress=progress,
        priority=priority,
        constraint_type=constraint_type,
        constraint_date=constraint_date,
        estimate_optimistic=optimistic,
        estimate_most_likely=likely,
        estimate_pessimistic=pessimistic,
    )
    db.session.add(task)
    _bump_project_version(project)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError(
            "task_creation_failed",
            "Could not create the task.",
            400,
        ) from None
    return task


def update_task(project: Project, task: Task, data: dict) -> Task:
    if not data:
        raise ApiError("empty_update", "Send task fields to update.", 400)
    _reject_unknown(data, TASK_UPDATE_FIELDS)

    updates = {}
    if "name" in data:
        updates["name"] = _clean_name(data["name"], "Task", 200)
    if "description" in data:
        if not isinstance(data["description"], str):
            raise ApiError("invalid_description", "Description must be text.", 400)
        updates["description"] = data["description"]
    if "status" in data:
        if data["status"] not in TASK_STATUSES:
            raise ApiError(
                "invalid_status",
                "Choose not_started, in_progress, blocked, or completed.",
                400,
            )
        updates["status"] = data["status"]
    if "duration_work_minutes" in data:
        updates["duration_work_minutes"] = _validate_int(
            data["duration_work_minutes"],
            "duration_work_minutes",
            "invalid_duration",
            "Duration must be a non-negative integer in working minutes.",
            minimum=0,
        )
    if "progress" in data:
        updates["progress"] = _validate_int(
            data["progress"],
            "progress",
            "invalid_progress",
            "Progress must be an integer from 0 to 100.",
            minimum=0,
            maximum=100,
        )
    if "priority" in data:
        updates["priority"] = _validate_int(
            data["priority"],
            "priority",
            "invalid_priority",
            "Priority must be an integer from 1 to 5.",
            minimum=1,
            maximum=5,
        )
    if "parent_task_id" in data:
        updates["parent_task_id"] = _validate_parent(
            project.id, data["parent_task_id"], task.id
        )

    if {"constraint_type", "constraint_date"} & data.keys():
        final_type = data.get("constraint_type", task.constraint_type)
        if "constraint_date" in data:
            requested_date = data["constraint_date"]
            final_date = _parse_date(
                requested_date,
                "constraint_date",
                "invalid_constraint_date",
            )
            if final_type == "none" and final_date is not None:
                raise ApiError(
                    "invalid_constraint_date",
                    "A constraint date is not allowed when the constraint is none.",
                    400,
                )
        else:
            final_date = (
                None if final_type == "none" else task.constraint_date
            )
        constraint_type, constraint_date = _validate_constraint(
            final_type, final_date
        )
        updates["constraint_type"] = constraint_type
        updates["constraint_date"] = constraint_date

    if any(field in data for field in ESTIMATE_FIELDS):
        values = [
            data.get(field, getattr(task, field)) for field in ESTIMATE_FIELDS
        ]
        optimistic, likely, pessimistic = _parse_estimates(values)
        updates.update(
            {
                "estimate_optimistic": optimistic,
                "estimate_most_likely": likely,
                "estimate_pessimistic": pessimistic,
            }
        )

    if not updates:
        raise ApiError("empty_update", "Send task fields to update.", 400)

    for field, value in updates.items():
        setattr(task, field, value)
    _bump_project_version(project)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError(
            "task_update_failed",
            "Could not update the task.",
            400,
        ) from None
    return task


def delete_task(project: Project, task: Task) -> None:
    db.session.delete(task)
    _bump_project_version(project)
    db.session.commit()


def list_dependencies(
    project_id: int,
    limit: int,
    offset: int,
) -> list[dict]:
    dependencies = db.session.scalars(
        db.select(Dependency)
        .where(Dependency.project_id == project_id)
        .order_by(Dependency.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [dependency.to_dict() for dependency in dependencies]


def _path_exists(adjacency, start: int, target: int) -> bool:
    stack = [start]
    seen = set()
    while stack:
        node = stack.pop()
        if node == target:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency.get(node, ()))
    return False


def create_dependency(project: Project, data: dict) -> Dependency:
    _reject_unknown(
        data,
        {
            "predecessor_task_id",
            "successor_task_id",
            "type",
            "lag_work_minutes",
        },
    )
    missing = [
        field
        for field in ("predecessor_task_id", "successor_task_id")
        if data.get(field) is None
    ]
    if missing:
        raise ApiError(
            "validation_error",
            "Required fields are missing.",
            400,
            {"fields": missing},
        )

    predecessor_id = _validate_int(
        data["predecessor_task_id"],
        "predecessor_task_id",
        "invalid_task",
        "Choose two tasks from this project.",
    )
    successor_id = _validate_int(
        data["successor_task_id"],
        "successor_task_id",
        "invalid_task",
        "Choose two tasks from this project.",
    )
    dependency_type = data.get("type", "FS")
    if dependency_type not in DEPENDENCY_TYPES:
        raise ApiError(
            "invalid_dependency_type",
            "Choose FS, SS, FF, or SF.",
            400,
        )
    lag = _validate_int(
        data.get("lag_work_minutes", 0),
        "lag_work_minutes",
        "invalid_lag",
        "Lag must be an integer number of working minutes.",
    )

    if predecessor_id == successor_id:
        raise ApiError(
            "self_dependency",
            "A task cannot depend on itself.",
            400,
        )

    predecessor = db.session.get(Task, predecessor_id)
    successor = db.session.get(Task, successor_id)
    if predecessor is None or successor is None:
        raise ApiError(
            "invalid_task",
            "Choose two tasks from this project.",
            400,
        )
    if (
        predecessor.project_id != project.id
        or successor.project_id != project.id
    ):
        raise ApiError(
            "cross_project_dependency",
            "Dependencies must connect tasks in the same project.",
            400,
        )

    existing = db.session.execute(
        db.select(Dependency).where(
            Dependency.project_id == project.id,
            Dependency.predecessor_task_id == predecessor_id,
            Dependency.successor_task_id == successor_id,
            Dependency.type == dependency_type,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ApiError(
            "duplicate_dependency",
            "That dependency already exists.",
            409,
        )

    adjacency = defaultdict(list)
    for dependency in db.session.scalars(
        db.select(Dependency).where(Dependency.project_id == project.id)
    ).all():
        adjacency[dependency.predecessor_task_id].append(
            dependency.successor_task_id
        )
    if _path_exists(adjacency, successor_id, predecessor_id):
        raise ApiError(
            "dependency_cycle",
            "That dependency would create a cycle.",
            409,
        )

    dependency = Dependency(
        project_id=project.id,
        predecessor_task_id=predecessor_id,
        successor_task_id=successor_id,
        type=dependency_type,
        lag_work_minutes=lag,
    )
    db.session.add(dependency)
    _bump_project_version(project)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError(
            "duplicate_dependency",
            "That dependency already exists.",
            409,
        ) from None
    return dependency


def delete_dependency(project: Project, dependency: Dependency) -> None:
    db.session.delete(dependency)
    _bump_project_version(project)
    db.session.commit()
