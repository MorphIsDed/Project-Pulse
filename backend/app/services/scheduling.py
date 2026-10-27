from app.errors import ApiError
from app.extensions import db
from app.models.base import utcnow
from app.models.planning import Dependency, Task
from app.scheduling.calendar import (
    WorkingCalendar,
    parse_exceptions,
    parse_timezone,
    parse_weekly_rules,
)
from app.scheduling.cpm import DependencyInput, TaskInput, compute_schedule
from app.scheduling.errors import ScheduleError
from app.services.planning import get_calendar


CALENDAR_FIELDS = {"version", "name", "timezone", "weekly_rules", "exceptions"}


def update_calendar(project, data: dict):
    if not data:
        raise ApiError("empty_update", "Send calendar fields to update.", 400)
    unknown = sorted(set(data) - CALENDAR_FIELDS)
    if unknown:
        raise ApiError(
            "unsupported_field",
            "One or more fields cannot be updated.",
            400,
            {"fields": unknown},
        )
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

    updates = set(data) - {"version"}
    if not updates:
        raise ApiError("empty_update", "Send calendar fields to update.", 400)

    calendar = get_calendar(project)
    name = calendar.name
    timezone_name = calendar.timezone
    weekly_rules = calendar.weekly_rules
    exceptions = calendar.exceptions

    if "name" in data:
        if not isinstance(data["name"], str) or not data["name"].strip():
            raise ApiError("invalid_name", "Calendar name is required.", 400)
        name = data["name"].strip()
        if len(name) > 120:
            raise ApiError(
                "invalid_name",
                "Calendar name must be 120 characters or fewer.",
                400,
            )
    try:
        if "timezone" in data:
            timezone_name = parse_timezone(data["timezone"])
        if "weekly_rules" in data:
            weekly_rules = parse_weekly_rules(data["weekly_rules"])
        if "exceptions" in data:
            exceptions = parse_exceptions(data["exceptions"])
        WorkingCalendar(timezone_name, weekly_rules, exceptions)
    except ScheduleError as exc:
        raise ApiError(
            exc.code, exc.message, exc.status, exc.details
        ) from None

    calendar.name = name
    calendar.timezone = timezone_name
    calendar.weekly_rules = weekly_rules
    calendar.exceptions = exceptions
    calendar.updated_at = utcnow()
    project.version += 1
    project.updated_at = utcnow()
    db.session.commit()
    return calendar, project


def build_schedule(project, constraint_overrides=None) -> dict:
    calendar_model = get_calendar(project)
    calendar = WorkingCalendar(
        calendar_model.timezone,
        calendar_model.weekly_rules,
        calendar_model.exceptions,
    )
    tasks = db.session.scalars(
        db.select(Task)
        .where(Task.project_id == project.id)
        .order_by(Task.id)
    ).all()
    dependencies = db.session.scalars(
        db.select(Dependency)
        .where(Dependency.project_id == project.id)
        .order_by(Dependency.id)
    ).all()

    requested_start = project.start_date or calendar.today()
    start_source = "project" if project.start_date else "today_default"
    overrides = constraint_overrides or {}
    task_inputs = []
    for task in tasks:
        constraint_type = task.constraint_type
        constraint_date = task.constraint_date
        if task.id in overrides:
            constraint_type, constraint_date = overrides[task.id]
        task_inputs.append(
            TaskInput(
                id=task.id,
                name=task.name,
                duration_work_minutes=task.duration_work_minutes,
                constraint_type=constraint_type,
                constraint_date=constraint_date,
            )
        )
    dependency_inputs = [
        DependencyInput(
            predecessor_task_id=dependency.predecessor_task_id,
            successor_task_id=dependency.successor_task_id,
            type=dependency.type,
            lag_work_minutes=dependency.lag_work_minutes,
        )
        for dependency in dependencies
    ]

    try:
        result = compute_schedule(
            task_inputs,
            dependency_inputs,
            calendar,
            requested_start,
            project.target_finish,
        )
    except ScheduleError as exc:
        raise ApiError(
            exc.code, exc.message, exc.status, exc.details
        ) from None

    origin = result.origin
    warnings = list(result.warnings)
    actual_start = calendar.local_date(origin)
    if start_source == "today_default":
        warnings.insert(
            0,
            {
                "code": "project_start_defaulted",
                "message": "The project has no start date; today was used.",
                "start_date": actual_start.isoformat(),
            },
        )
    elif actual_start != requested_start:
        warnings.insert(
            0,
            {
                "code": "project_start_adjusted",
                "message": "The project start moved to the next working day.",
                "requested_start": requested_start.isoformat(),
                "start_date": actual_start.isoformat(),
            },
        )

    scheduled_tasks = []
    for task in tasks:
        schedule = result.tasks[task.id]
        data = task.to_dict()
        data.update(
            _schedule_fields(schedule, task, calendar, origin)
        )
        scheduled_tasks.append(data)

    finish_at = calendar.add_working_minutes(origin, result.project_finish)
    return {
        "project_id": project.id,
        "project_version": project.version,
        "project_start": actual_start.isoformat(),
        "requested_start": requested_start.isoformat(),
        "start_source": start_source,
        "target_finish": (
            project.target_finish.isoformat()
            if project.target_finish is not None
            else None
        ),
        "project_finish": calendar.local_date(finish_at).isoformat(),
        "project_finish_at": calendar.local_datetime(finish_at).isoformat(
            timespec="minutes"
        ),
        "calendar": calendar_model.to_dict(),
        "tasks": scheduled_tasks,
        "dependencies": [
            dependency.to_dict() for dependency in dependencies
        ],
        "critical_path": result.critical_path,
        "warnings": warnings,
    }


def _schedule_fields(schedule, task, calendar, origin) -> dict:
    early_start = _start_at(calendar, origin, schedule.early_start)
    early_finish = _finish_at(
        calendar, origin, schedule.early_finish, task.duration_work_minutes
    )
    late_start = _start_at(calendar, origin, schedule.late_start)
    late_finish = _finish_at(
        calendar, origin, schedule.late_finish, task.duration_work_minutes
    )
    return {
        "early_start": calendar.local_date(early_start).isoformat(),
        "early_finish": calendar.local_date(early_finish).isoformat(),
        "early_start_at": calendar.local_datetime(early_start).isoformat(
            timespec="minutes"
        ),
        "early_finish_at": calendar.local_datetime(early_finish).isoformat(
            timespec="minutes"
        ),
        "late_start": calendar.local_date(late_start).isoformat(),
        "late_finish": calendar.local_date(late_finish).isoformat(),
        "late_start_at": calendar.local_datetime(late_start).isoformat(
            timespec="minutes"
        ),
        "late_finish_at": calendar.local_datetime(late_finish).isoformat(
            timespec="minutes"
        ),
        "total_float_work_minutes": schedule.total_float,
        "free_float_work_minutes": schedule.free_float,
        "critical": schedule.critical,
    }


def _start_at(calendar, origin, offset):
    return calendar.next_working_instant(
        calendar.add_working_minutes(origin, offset)
    )


def _finish_at(calendar, origin, offset, duration):
    if duration == 0:
        return _start_at(calendar, origin, offset)
    return calendar.add_working_minutes(origin, offset)
