from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

from app.scheduling.calendar import WorkingCalendar
from app.scheduling.errors import ScheduleError
from app.scheduling.graph import topological_order


@dataclass(frozen=True)
class TaskInput:
    id: int
    name: str
    duration_work_minutes: int
    constraint_type: str = "none"
    constraint_date: date | None = None


@dataclass(frozen=True)
class DependencyInput:
    predecessor_task_id: int
    successor_task_id: int
    type: str = "FS"
    lag_work_minutes: int = 0


@dataclass(frozen=True)
class TaskSchedule:
    task_id: int
    early_start: int
    early_finish: int
    late_start: int
    late_finish: int
    total_float: int
    free_float: int
    critical: bool


@dataclass
class ScheduleResult:
    origin: datetime
    project_finish: int
    tasks: dict[int, TaskSchedule]
    critical_path: list[int] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)


def compute_schedule(
    tasks: list[TaskInput],
    dependencies: list[DependencyInput],
    calendar: WorkingCalendar,
    project_start: date,
    target_finish: date | None = None,
) -> ScheduleResult:
    if not tasks:
        origin = calendar.first_start_on_or_after(project_start)
        return ScheduleResult(origin=origin, project_finish=0, tasks={})

    task_by_id = {task.id: task for task in tasks}
    if len(task_by_id) != len(tasks):
        raise ScheduleError(
            "invalid_task", "Task identifiers must be unique.", 422
        )
    for task in tasks:
        if type(task.duration_work_minutes) is not int:
            raise ScheduleError(
                "invalid_duration", "Task durations must be integers.", 422
            )
        if task.duration_work_minutes < 0:
            raise ScheduleError(
                "invalid_duration",
                "Task durations must be non-negative.",
                422,
            )
        if task.constraint_type not in (
            "none",
            "start_no_earlier_than",
            "start_no_later_than",
            "must_start_on",
            "finish_no_earlier_than",
            "finish_no_later_than",
            "must_finish_on",
        ):
            raise ScheduleError(
                "invalid_constraint",
                f"Task '{task.name}' has an unsupported constraint.",
                422,
                {"task_id": task.id},
            )

    order = topological_order(
        [task.id for task in tasks], dependencies
    )
    origin = calendar.first_start_on_or_after(project_start)
    offset = lambda instant: calendar.working_minutes_between(origin, instant)

    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    for dependency in dependencies:
        if dependency.type not in ("FS", "SS", "FF", "SF"):
            raise ScheduleError(
                "invalid_dependency_type",
                "Choose FS, SS, FF, or SF.",
                422,
            )
        incoming[dependency.successor_task_id].append(dependency)
        outgoing[dependency.predecessor_task_id].append(dependency)

    early_start = {}
    early_finish = {}
    for task_id in order:
        task = task_by_id[task_id]
        start = 0
        for dependency in incoming[task_id]:
            predecessor = dependency.predecessor_task_id
            lag = dependency.lag_work_minutes
            if dependency.type == "FS":
                bound = early_finish[predecessor] + lag
            elif dependency.type == "SS":
                bound = early_start[predecessor] + lag
            elif dependency.type == "FF":
                bound = early_finish[predecessor] + lag - task.duration_work_minutes
            else:
                bound = early_start[predecessor] + lag - task.duration_work_minutes
            start = max(start, bound)

        start = max(0, start)
        if task.constraint_type == "start_no_earlier_than":
            start = max(start, _start_boundary(task, calendar, origin, offset))
        elif task.constraint_type == "finish_no_earlier_than":
            finish = _finish_boundary(task, calendar, origin, offset)
            start = max(start, finish - task.duration_work_minutes)
        elif task.constraint_type == "must_start_on":
            fixed = _required_start(task, calendar, origin, offset)
            if fixed < 0:
                _raise_constraint(task, "starts before the project start")
            if start > fixed:
                _raise_constraint(task, "cannot meet its required start date")
            start = fixed
        elif task.constraint_type == "must_finish_on":
            fixed_finish = _required_finish(task, calendar, origin, offset)
            fixed_start = fixed_finish - task.duration_work_minutes
            if fixed_start < 0:
                _raise_constraint(task, "finishes before the project start")
            if start > fixed_start:
                _raise_constraint(task, "cannot meet its required finish date")
            start = fixed_start

        start = max(0, start)
        early_start[task_id] = start
        early_finish[task_id] = start + task.duration_work_minutes

    project_finish = max(early_finish.values(), default=0)
    target_offset = None
    warnings = []
    if target_finish is not None:
        target_offset = offset(calendar.first_end_on_or_after(target_finish))
        if target_offset < project_finish:
            warnings.append(
                {
                    "code": "target_finish_missed",
                    "message": "The calculated project finish is after the target finish.",
                    "target_finish": target_finish.isoformat(),
                    "project_finish": calendar.local_date(
                        calendar.add_working_minutes(origin, project_finish)
                    ).isoformat(),
                }
            )

    backward_boundary = (
        target_offset if target_offset is not None else project_finish
    )
    late_finish = {task_id: backward_boundary for task_id in task_by_id}
    late_start = {}

    for task_id in reversed(order):
        task = task_by_id[task_id]
        for dependency in outgoing[task_id]:
            successor = dependency.successor_task_id
            lag = dependency.lag_work_minutes
            if dependency.type == "FS":
                bound = late_start[successor] - lag
            elif dependency.type == "SS":
                bound = (
                    late_start[successor]
                    - lag
                    + task.duration_work_minutes
                )
            elif dependency.type == "FF":
                bound = late_finish[successor] - lag
            else:
                bound = (
                    late_finish[successor]
                    - lag
                    + task.duration_work_minutes
                )
            late_finish[task_id] = min(late_finish[task_id], bound)

        if task.constraint_type == "start_no_later_than":
            latest = _latest_start_boundary(
                task, calendar, origin, offset
            )
            late_finish[task_id] = min(
                late_finish[task_id],
                latest + task.duration_work_minutes,
            )
        elif task.constraint_type == "finish_no_later_than":
            latest = _latest_finish_boundary(
                task, calendar, origin, offset
            )
            late_finish[task_id] = min(late_finish[task_id], latest)
        elif task.constraint_type == "must_start_on":
            latest = _required_start(task, calendar, origin, offset)
            late_finish[task_id] = min(
                late_finish[task_id],
                latest + task.duration_work_minutes,
            )
        elif task.constraint_type == "must_finish_on":
            latest = _required_finish(task, calendar, origin, offset)
            late_finish[task_id] = min(late_finish[task_id], latest)

        late_start[task_id] = (
            late_finish[task_id] - task.duration_work_minutes
        )

    for task in tasks:
        task_id = task.id
        if task.constraint_type == "start_no_later_than":
            latest = _latest_start_boundary(
                task, calendar, origin, offset
            )
            if early_start[task_id] > latest:
                _raise_constraint(
                    task, "cannot meet its latest start date"
                )
        elif task.constraint_type == "finish_no_later_than":
            latest = _latest_finish_boundary(
                task, calendar, origin, offset
            )
            if early_finish[task_id] > latest:
                _raise_constraint(
                    task, "cannot meet its latest finish date"
                )

        if (
            target_offset is None
            and late_start[task_id] < early_start[task_id]
        ):
            _raise_constraint(
                task, "has conflicting date or dependency constraints"
            )

    schedules = {}
    for task in tasks:
        task_id = task.id
        total_float = late_start[task_id] - early_start[task_id]
        free_float = _free_float(
            task,
            outgoing[task_id],
            early_start,
            early_finish,
            project_finish,
        )
        schedules[task_id] = TaskSchedule(
            task_id=task_id,
            early_start=early_start[task_id],
            early_finish=early_finish[task_id],
            late_start=late_start[task_id],
            late_finish=late_finish[task_id],
            total_float=total_float,
            free_float=max(0, free_float),
            critical=total_float <= 0,
        )

    critical_path = [
        task.id
        for task in sorted(
            tasks,
            key=lambda item: (
                schedules[item.id].early_start,
                schedules[item.id].early_finish,
                item.id,
            ),
        )
        if schedules[task.id].critical
    ]
    return ScheduleResult(
        origin=origin,
        project_finish=project_finish,
        tasks=schedules,
        critical_path=critical_path,
        warnings=warnings,
    )


def _free_float(task, dependencies, early_start, early_finish, project_finish):
    if not dependencies:
        return project_finish - early_finish[task.id]
    values = []
    for dependency in dependencies:
        successor = dependency.successor_task_id
        lag = dependency.lag_work_minutes
        if dependency.type == "FS":
            values.append(
                early_start[successor] - (early_finish[task.id] + lag)
            )
        elif dependency.type == "SS":
            values.append(
                early_start[successor] - (early_start[task.id] + lag)
            )
        elif dependency.type == "FF":
            values.append(
                early_finish[successor] - (early_finish[task.id] + lag)
            )
        else:
            values.append(
                early_finish[successor] - (early_start[task.id] + lag)
            )
    return min(values)


def _constraint_date(task: TaskInput) -> date:
    if task.constraint_date is None:
        raise ScheduleError(
            "invalid_constraint_date",
            f"Task '{task.name}' has a constraint without a date.",
            422,
        )
    return task.constraint_date


def _start_boundary(task, calendar, origin, offset) -> int:
    day = _constraint_date(task)
    return offset(calendar.first_start_on_or_after(day))


def _finish_boundary(task, calendar, origin, offset) -> int:
    day = _constraint_date(task)
    return offset(calendar.first_end_on_or_after(day))


def _latest_start_boundary(task, calendar, origin, offset) -> int:
    day = _constraint_date(task)
    return offset(calendar.last_start_on_or_before(day))


def _latest_finish_boundary(task, calendar, origin, offset) -> int:
    day = _constraint_date(task)
    return offset(calendar.last_end_on_or_before(day))


def _required_start(task, calendar, origin, offset) -> int:
    day = _constraint_date(task)
    if not calendar.has_work_on(day):
        raise ScheduleError(
            "invalid_constraint_date",
            f"Task '{task.name}' has a required start date on a nonworking day.",
            422,
            {"task_id": task.id, "constraint_date": day.isoformat()},
        )
    return offset(calendar.first_start_on_or_after(day))


def _required_finish(task, calendar, origin, offset) -> int:
    day = _constraint_date(task)
    if not calendar.has_work_on(day):
        raise ScheduleError(
            "invalid_constraint_date",
            f"Task '{task.name}' has a required finish date on a nonworking day.",
            422,
            {"task_id": task.id, "constraint_date": day.isoformat()},
        )
    return offset(calendar.first_end_on_or_after(day))


def _raise_constraint(task: TaskInput, reason: str) -> None:
    raise ScheduleError(
        "schedule_infeasible",
        f"Task '{task.name}' {reason}.",
        422,
        {"task_id": task.id},
    )
