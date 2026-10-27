from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError

from app.analytics.workload import build_workload
from app.errors import ApiError
from app.extensions import db
from app.models.base import utcnow
from app.models.planning import Task
from app.models.resources import Assignment, Resource
from app.scheduling.calendar import WorkingCalendar
from app.services.scheduling import build_schedule


RESOURCE_FIELDS = {"name", "role", "capacity_work_minutes_per_day"}
MAX_LEVELING_PROPOSALS = 12


def _reject_unknown(data: dict, allowed: set[str]) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ApiError(
            "unsupported_field",
            "One or more fields cannot be updated.",
            400,
            {"fields": unknown},
        )


def _clean_text(value, label: str, max_length: int, required: bool) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ApiError("invalid_name", f"{label} must be text.", 400)
    text = value.strip()
    if required and not text:
        raise ApiError("invalid_name", f"{label} is required.", 400)
    if len(text) > max_length:
        raise ApiError(
            "invalid_name",
            f"{label} must be {max_length} characters or fewer.",
            400,
        )
    return text


def _validate_int(
    value, field: str, minimum: int, maximum: int, code: str
) -> int:
    if type(value) is not int or value < minimum or value > maximum:
        raise ApiError(
            code,
            f"{field} must be an integer from {minimum} to {maximum}.",
            400,
            {"field": field},
        )
    return value


def _bump_project_version(project) -> None:
    project.version = (project.version or 0) + 1
    project.updated_at = utcnow()


def list_resources(
    project_id: int, limit: int, offset: int
) -> list[dict]:
    resources = db.session.scalars(
        db.select(Resource)
        .where(Resource.project_id == project_id)
        .order_by(Resource.name, Resource.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [resource.to_dict() for resource in resources]


def create_resource(project, data: dict) -> Resource:
    _reject_unknown(data, RESOURCE_FIELDS)
    name = _clean_text(data.get("name"), "Resource name", 120, True)
    role = _clean_text(data.get("role", ""), "Resource role", 120, False)
    capacity = _validate_int(
        data.get("capacity_work_minutes_per_day", 480),
        "capacity_work_minutes_per_day",
        1,
        1440,
        "invalid_capacity",
    )
    resource = Resource(
        project_id=project.id,
        name=name,
        role=role,
        capacity_work_minutes_per_day=capacity,
    )
    db.session.add(resource)
    _bump_project_version(project)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError(
            "resource_conflict",
            "A resource with that name already exists in this project.",
            409,
        ) from None
    return resource


def update_resource(project, resource: Resource, data: dict) -> Resource:
    if not data:
        raise ApiError("empty_update", "Send resource fields to update.", 400)
    _reject_unknown(data, RESOURCE_FIELDS)
    if "name" in data:
        resource.name = _clean_text(
            data["name"], "Resource name", 120, True
        )
    if "role" in data:
        resource.role = _clean_text(
            data["role"], "Resource role", 120, False
        )
    if "capacity_work_minutes_per_day" in data:
        resource.capacity_work_minutes_per_day = _validate_int(
            data["capacity_work_minutes_per_day"],
            "capacity_work_minutes_per_day",
            1,
            1440,
            "invalid_capacity",
        )
    resource.updated_at = utcnow()
    _bump_project_version(project)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError(
            "resource_conflict",
            "A resource with that name already exists in this project.",
            409,
        ) from None
    return resource


def delete_resource(project, resource: Resource) -> None:
    db.session.delete(resource)
    _bump_project_version(project)
    db.session.commit()


def list_assignments(
    project_id: int, limit: int, offset: int
) -> list[dict]:
    assignments = db.session.scalars(
        db.select(Assignment)
        .where(Assignment.project_id == project_id)
        .order_by(Assignment.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [assignment.to_dict() for assignment in assignments]


def _validate_assignment_members(
    project_id: int, resource_id: int, task_id: int
) -> None:
    resource = db.session.get(Resource, resource_id)
    if resource is None or resource.project_id != project_id:
        raise ApiError(
            "invalid_resource",
            "Choose a resource from this project.",
            400,
        )
    task = db.session.get(Task, task_id)
    if task is None or task.project_id != project_id:
        raise ApiError(
            "invalid_task",
            "Choose a task from this project.",
            400,
        )


def create_assignment(project, data: dict) -> Assignment:
    _reject_unknown(
        data,
        {"resource_id", "task_id", "allocation_percent"},
    )
    missing = [
        field
        for field in ("resource_id", "task_id")
        if data.get(field) is None
    ]
    if missing:
        raise ApiError(
            "validation_error",
            "Required fields are missing.",
            400,
            {"fields": missing},
        )
    resource_id = _validate_int(
        data["resource_id"],
        "resource_id",
        1,
        2_147_483_647,
        "invalid_resource",
    )
    task_id = _validate_int(
        data["task_id"],
        "task_id",
        1,
        2_147_483_647,
        "invalid_task",
    )
    allocation = _validate_int(
        data.get("allocation_percent", 100),
        "allocation_percent",
        1,
        100,
        "invalid_allocation",
    )
    _validate_assignment_members(project.id, resource_id, task_id)

    existing = db.session.execute(
        db.select(Assignment).where(
            Assignment.project_id == project.id,
            Assignment.resource_id == resource_id,
            Assignment.task_id == task_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ApiError(
            "duplicate_assignment",
            "That resource is already assigned to this task.",
            409,
        )

    assignment = Assignment(
        project_id=project.id,
        resource_id=resource_id,
        task_id=task_id,
        allocation_percent=allocation,
    )
    db.session.add(assignment)
    _bump_project_version(project)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError(
            "duplicate_assignment",
            "That resource is already assigned to this task.",
            409,
        ) from None
    return assignment


def update_assignment(
    project, assignment: Assignment, data: dict
) -> Assignment:
    if not data:
        raise ApiError("empty_update", "Send assignment fields to update.", 400)
    _reject_unknown(data, {"allocation_percent"})
    assignment.allocation_percent = _validate_int(
        data["allocation_percent"],
        "allocation_percent",
        1,
        100,
        "invalid_allocation",
    )
    assignment.updated_at = utcnow()
    _bump_project_version(project)
    db.session.commit()
    return assignment


def delete_assignment(project, assignment: Assignment) -> None:
    db.session.delete(assignment)
    _bump_project_version(project)
    db.session.commit()


def _schedule_workload(project, schedule=None):
    schedule = schedule or build_schedule(project)
    resources = db.session.scalars(
        db.select(Resource)
        .where(Resource.project_id == project.id)
        .order_by(Resource.name, Resource.id)
    ).all()
    assignments = db.session.scalars(
        db.select(Assignment)
        .where(Assignment.project_id == project.id)
        .order_by(Assignment.id)
    ).all()
    calendar = WorkingCalendar.from_dict(schedule["calendar"])
    workload = build_workload(
        calendar,
        [resource.to_dict() for resource in resources],
        [assignment.to_dict() for assignment in assignments],
        schedule["tasks"],
    )
    return schedule, workload


def get_project_workload(project) -> dict:
    schedule, workload = _schedule_workload(project)
    return {
        "project_id": project.id,
        "project_version": schedule["project_version"],
        "project_start": schedule["project_start"],
        "project_finish": schedule["project_finish"],
        "calendar": schedule["calendar"],
        "resources": workload["resources"],
        "overloads": workload["overloads"],
        "summary": workload["summary"],
    }


def _overload_candidates(overload: dict, tasks: dict[int, dict], used: set):
    candidates = []
    for contribution in overload["tasks"]:
        task = tasks.get(contribution["task_id"])
        if task is None or task["id"] in used:
            continue
        if task["total_float_work_minutes"] <= 0:
            continue
        if task["constraint_type"] != "none":
            continue
        candidates.append(task)
    candidates.sort(
        key=lambda task: (
            -task["priority"],
            -task["total_float_work_minutes"],
            task["id"],
        )
    )
    return candidates


def get_leveling_preview(project) -> dict:
    schedule, workload = _schedule_workload(project)
    calendar = WorkingCalendar.from_dict(schedule["calendar"])
    tasks = {task["id"]: task for task in schedule["tasks"]}
    initial_excess = workload["summary"]["excess_work_minutes"]
    initial_overload_count = workload["summary"]["overload_count"]
    initial_finish = schedule["project_finish"]
    proposals = []
    notes = []
    overrides = {}
    used = set()

    if initial_excess == 0:
        notes.append("No resource overloads were detected.")
    else:
        for _ in range(MAX_LEVELING_PROPOSALS):
            overload = next(
                (
                    item
                    for item in workload["overloads"]
                    if item["excess_work_minutes"] > 0
                ),
                None,
            )
            if overload is None:
                break
            candidates = _overload_candidates(overload, tasks, used)
            if not candidates:
                notes.append(
                    "No float-bearing task without a fixed date could "
                    "relieve the remaining overloads."
                )
                break

            overload_day = date.fromisoformat(overload["date"])
            target_day = calendar.local_date(
                calendar.first_start_on_or_after(
                    overload_day + timedelta(days=1)
                )
            )
            accepted = False
            for task in candidates:
                overrides[task["id"]] = (
                    "start_no_earlier_than",
                    target_day,
                )
                try:
                    candidate_schedule = build_schedule(project, overrides)
                except ApiError:
                    overrides.pop(task["id"], None)
                    continue
                _candidate_schedule, candidate_workload = _schedule_workload(
                    project, candidate_schedule
                )
                candidate_excess = candidate_workload["summary"][
                    "excess_work_minutes"
                ]
                target_finish = (
                    project.target_finish.isoformat()
                    if project.target_finish is not None
                    else None
                )
                if (
                    (
                        target_finish is not None
                        and candidate_schedule["project_finish"] > target_finish
                    )
                    or candidate_excess >= workload["summary"][
                        "excess_work_minutes"
                    ]
                ):
                    overrides.pop(task["id"], None)
                    continue

                updated_task = next(
                    item
                    for item in candidate_schedule["tasks"]
                    if item["id"] == task["id"]
                )
                proposals.append(
                    {
                        "resource_id": overload["resource_id"],
                        "resource_name": overload["resource_name"],
                        "task_id": task["id"],
                        "task_name": task["name"],
                        "overloaded_date": overload["date"],
                        "current_start": task["early_start"],
                        "proposed_start": updated_task["early_start"],
                        "proposed_constraint_type": "start_no_earlier_than",
                        "proposed_constraint_date": target_day.isoformat(),
                        "float_work_minutes": task[
                            "total_float_work_minutes"
                        ],
                        "remaining_float_work_minutes": updated_task[
                            "total_float_work_minutes"
                        ],
                        "rationale": (
                            f"Delay {task['name']} to free "
                            f"{overload['resource_name']} on "
                            f"{overload['date']}."
                        ),
                    }
                )
                used.add(task["id"])
                schedule = candidate_schedule
                workload = candidate_workload
                accepted = True
                break
            if not accepted:
                notes.append(
                    "No candidate delay reduced overloads without extending "
                    "the project finish."
                )
                break

    notes.append(
        "This is an explainable preview, not an automatic schedule change."
    )
    return {
        "project_id": project.id,
        "project_version": schedule["project_version"],
        "before": {
            "project_finish": initial_finish,
            "overload_count": initial_overload_count,
            "excess_work_minutes": initial_excess,
        },
        "after": {
            "project_finish": schedule["project_finish"],
            "overload_count": workload["summary"]["overload_count"],
            "excess_work_minutes": workload["summary"][
                "excess_work_minutes"
            ],
        },
        "proposals": proposals,
        "remaining_overloads": workload["overloads"],
        "notes": notes,
    }
