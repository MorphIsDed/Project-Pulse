import math
import random
from collections import Counter
from datetime import date

from app.errors import ApiError
from app.extensions import db
from app.models.planning import Dependency, Task
from app.scheduling.calendar import WorkingCalendar
from app.scheduling.cpm import DependencyInput, TaskInput, compute_schedule
from app.scheduling.errors import ScheduleError
from app.services.planning import get_calendar


DEFAULT_ITERATIONS = 2000
MAX_ITERATIONS = 10000
MIN_ITERATIONS = 100


def simulate_project_risk(project, data: dict) -> dict:
    iterations = _iterations(data.get("iterations"))
    seed = _seed(data.get("seed"))

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
    dependency_inputs = [
        DependencyInput(
            predecessor_task_id=item.predecessor_task_id,
            successor_task_id=item.successor_task_id,
            type=item.type,
            lag_work_minutes=item.lag_work_minutes,
        )
        for item in dependencies
    ]
    requested_start = project.start_date or calendar.today()
    base_inputs = [_task_input(task) for task in tasks]
    estimate_map = {task.id: _estimates(task) for task in tasks}

    try:
        baseline = compute_schedule(
            base_inputs,
            dependency_inputs,
            calendar,
            requested_start,
        )
    except ScheduleError as exc:
        raise ApiError(
            exc.code, exc.message, exc.status, exc.details
        ) from None

    rng = random.Random(seed)
    finish_dates: list[date] = []
    critical_counts = Counter()
    duration_samples: dict[int, list[int]] = {
        task.id: [] for task in tasks
    }

    for _index in range(iterations):
        task_inputs = []
        for task in base_inputs:
            estimates = estimate_map[task.id]
            duration = _sample_duration(rng, task.duration_work_minutes, estimates)
            duration_samples[task.id].append(duration)
            task_inputs.append(
                TaskInput(
                    id=task.id,
                    name=task.name,
                    duration_work_minutes=duration,
                    constraint_type=task.constraint_type,
                    constraint_date=task.constraint_date,
                )
            )
        try:
            result = compute_schedule(
                task_inputs,
                dependency_inputs,
                calendar,
                requested_start,
            )
        except ScheduleError as exc:
            raise ApiError(
                "risk_simulation_infeasible",
                "A simulated duration produced an infeasible schedule.",
                422,
                {"reason": exc.message, "code": exc.code},
            ) from None

        finish = calendar.local_date(
            calendar.add_working_minutes(result.origin, result.project_finish)
        )
        finish_dates.append(finish)
        for task_id, schedule in result.tasks.items():
            if schedule.critical:
                critical_counts[task_id] += 1

    baseline_finish = calendar.local_date(
        calendar.add_working_minutes(
            baseline.origin, baseline.project_finish
        )
    )
    ordered_finishes = sorted(finish_dates)
    percentiles = {
        f"p{percent}": _date_percentile(ordered_finishes, percent).isoformat()
        for percent in (10, 50, 80, 90, 95)
    }
    target_probability = None
    if project.target_finish is not None:
        target_probability = round(
            sum(
                1
                for finish in finish_dates
                if finish <= project.target_finish
            )
            / iterations,
            4,
        )

    task_risks = []
    for task in tasks:
        samples = sorted(duration_samples[task.id])
        estimates = estimate_map[task.id]
        task_risks.append(
            {
                "task_id": task.id,
                "task_name": task.name,
                "duration_work_minutes": task.duration_work_minutes,
                "estimates": estimates,
                "p10_work_minutes": _value_percentile(samples, 10),
                "p50_work_minutes": _value_percentile(samples, 50),
                "p90_work_minutes": _value_percentile(samples, 90),
                "critical_frequency": round(
                    critical_counts[task.id] / iterations, 4
                ),
            }
        )
    task_risks.sort(
        key=lambda item: (-item["critical_frequency"], item["task_id"])
    )

    return {
        "project_id": project.id,
        "project_version": project.version,
        "iterations": iterations,
        "seed": seed,
        "target_finish": (
            project.target_finish.isoformat()
            if project.target_finish is not None
            else None
        ),
        "deterministic_finish": baseline_finish.isoformat(),
        "finish_percentiles": percentiles,
        "target_probability": target_probability,
        "tasks": task_risks,
        "warnings": baseline.warnings,
        "assumptions": [
            "Task durations use PERT beta distributions when all three "
            "estimates are present and ordered.",
            "Tasks without complete estimates use their deterministic "
            "duration in every iteration.",
            "Only task durations vary; dependencies, constraints, and the "
            "working calendar stay fixed.",
        ],
    }


def _iterations(value) -> int:
    if value is None:
        return DEFAULT_ITERATIONS
    if type(value) is not int:
        raise ApiError(
            "validation_error",
            "Iterations must be an integer.",
            400,
            {"fields": ["iterations"]},
        )
    if value < MIN_ITERATIONS or value > MAX_ITERATIONS:
        raise ApiError(
            "validation_error",
            f"Iterations must be between {MIN_ITERATIONS} and "
            f"{MAX_ITERATIONS}.",
            400,
            {"fields": ["iterations"]},
        )
    return value


def _seed(value) -> int:
    if value is None:
        return random.SystemRandom().randint(1, 2_147_483_647)
    if type(value) is not int:
        raise ApiError(
            "validation_error",
            "Seed must be an integer.",
            400,
            {"fields": ["seed"]},
        )
    return value


def _task_input(task: Task) -> TaskInput:
    return TaskInput(
        id=task.id,
        name=task.name,
        duration_work_minutes=task.duration_work_minutes,
        constraint_type=task.constraint_type,
        constraint_date=task.constraint_date,
    )


def _estimates(task: Task) -> dict | None:
    values = (
        task.estimate_optimistic,
        task.estimate_most_likely,
        task.estimate_pessimistic,
    )
    if any(value is None for value in values):
        return None
    optimistic, most_likely, pessimistic = values
    if not (0 <= optimistic <= most_likely <= pessimistic):
        return None
    return {
        "optimistic": optimistic,
        "most_likely": most_likely,
        "pessimistic": pessimistic,
    }


def _sample_duration(rng: random.Random, fallback: int, estimates) -> int:
    if estimates is None:
        return fallback
    optimistic = estimates["optimistic"]
    most_likely = estimates["most_likely"]
    pessimistic = estimates["pessimistic"]
    if optimistic == pessimistic:
        return optimistic
    mean = (optimistic + 4 * most_likely + pessimistic) / 6
    std = (pessimistic - optimistic) / 6
    if std <= 0:
        return int(round(mean))
    spread = pessimistic - optimistic
    alpha = ((mean - optimistic) / spread) * (
        ((mean - optimistic) * (pessimistic - mean)) / (std**2) - 1
    )
    beta = ((pessimistic - mean) / spread) * (
        ((mean - optimistic) * (pessimistic - mean)) / (std**2) - 1
    )
    if alpha <= 0 or beta <= 0:
        return int(round(mean))
    sample = optimistic + spread * rng.betavariate(alpha, beta)
    return max(0, int(round(sample)))


def _date_percentile(values: list[date], percent: int) -> date:
    index = max(0, math.ceil(percent / 100 * len(values)) - 1)
    return values[min(index, len(values) - 1)]


def _value_percentile(values: list[int], percent: int) -> int:
    if not values:
        return 0
    index = max(0, math.ceil(percent / 100 * len(values)) - 1)
    return values[min(index, len(values) - 1)]
