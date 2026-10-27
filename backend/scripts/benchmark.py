"""Reproduce the M9 schedule and risk-simulation measurements."""

import argparse
import json
import platform
import statistics
import tempfile
import time
from datetime import date
from pathlib import Path

from app import create_app
from app.extensions import db
from app.models.planning import (
    Dependency,
    Project,
    ProjectCalendar,
    Task,
    default_weekly_rules,
)
from app.models.tenancy import Organization, Workspace
from app.scheduling.calendar import WorkingCalendar
from app.scheduling.cpm import DependencyInput, TaskInput, compute_schedule
from app.services.risk import simulate_project_risk

TASK_COUNT = 1000
CHAIN_LENGTH = 10


def build_cases():
    tasks = [
        TaskInput(id=index + 1, name=f"Task {index + 1}", duration_work_minutes=480)
        for index in range(TASK_COUNT)
    ]
    dependencies = []
    for chain_start in range(0, TASK_COUNT, CHAIN_LENGTH):
        for offset in range(CHAIN_LENGTH - 1):
            dependencies.append(
                DependencyInput(
                    predecessor_task_id=chain_start + offset + 1,
                    successor_task_id=chain_start + offset + 2,
                    type="FS",
                )
            )
    return tasks, dependencies


def measure_schedule(runs: int) -> list[float]:
    tasks, dependencies = build_cases()
    calendar = WorkingCalendar("UTC", default_weekly_rules(), [])
    start = date(2026, 1, 5)
    compute_schedule(tasks, dependencies, calendar, start)
    timings = []
    for _ in range(runs):
        started = time.perf_counter()
        compute_schedule(tasks, dependencies, calendar, start)
        timings.append(time.perf_counter() - started)
    return timings


def measure_risk(database_path: Path, iterations: int) -> float:
    app = create_app(
        "testing",
        {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}"},
    )
    with app.app_context():
        db.create_all()
        organization = Organization(name="Benchmark organization")
        workspace = Workspace(
            organization=organization, name="Benchmark workspace"
        )
        project = Project(
            workspace=workspace,
            name="Benchmark project",
            start_date=date(2026, 1, 5),
        )
        project.calendar = ProjectCalendar(
            name="Standard calendar",
            timezone="UTC",
            weekly_rules=default_weekly_rules(),
            exceptions=[],
        )
        db.session.add(project)
        db.session.flush()
        tasks = [
            Task(
                project_id=project.id,
                name=f"Task {index + 1}",
                duration_work_minutes=480,
                estimate_optimistic=240,
                estimate_most_likely=480,
                estimate_pessimistic=720,
            )
            for index in range(TASK_COUNT)
        ]
        db.session.add_all(tasks)
        db.session.flush()
        db.session.add_all(
            [
                Dependency(
                    project_id=project.id,
                    predecessor_task_id=tasks[
                        chain_start + offset
                    ].id,
                    successor_task_id=tasks[
                        chain_start + offset + 1
                    ].id,
                    type="FS",
                )
                for chain_start in range(0, TASK_COUNT, CHAIN_LENGTH)
                for offset in range(CHAIN_LENGTH - 1)
            ]
        )
        db.session.commit()

        try:
            started = time.perf_counter()
            simulate_project_risk(
                project, {"iterations": iterations, "seed": 42}
            )
            return time.perf_counter() - started
        finally:
            db.session.remove()
            db.engine.dispose()


def summarize(values: list[float]) -> dict:
    return {
        "runs": len(values),
        "median_seconds": round(statistics.median(values), 4),
        "min_seconds": round(min(values), 4),
        "max_seconds": round(max(values), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=100)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as temporary:
        database_path = Path(temporary) / "benchmark.sqlite3"
        risk_seconds = measure_risk(database_path, args.iterations)

    result = {
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "processor": platform.processor(),
        },
        "shape": {
            "tasks": TASK_COUNT,
            "chains": TASK_COUNT // CHAIN_LENGTH,
            "chain_length": CHAIN_LENGTH,
            "dependencies": TASK_COUNT - (TASK_COUNT // CHAIN_LENGTH),
            "risk_iterations": args.iterations,
        },
        "schedule": summarize(measure_schedule(args.runs)),
        "risk_simulation_seconds": round(risk_seconds, 4),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
