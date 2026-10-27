"""Measure scheduling and compact summary computation for 1,000 tasks."""

import argparse
import json
import platform
import statistics
import time
from datetime import date

from app.models.planning import default_weekly_rules
from app.scheduling.calendar import WorkingCalendar
from app.scheduling.cpm import DependencyInput, TaskInput, compute_schedule
from app.services.summary import summarize_tasks

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


def measure_summary(runs: int) -> list[float]:
    records = [("completed" if i % 3 == 0 else "not_started", 60 + i % 480)
               for i in range(TASK_COUNT)]
    summarize_tasks(records, 1)
    timings = []
    for _ in range(runs):
        started = time.perf_counter()
        summarize_tasks(records, 1)
        timings.append(time.perf_counter() - started)
    return timings


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
    args = parser.parse_args()

    if args.runs < 1:
        parser.error("--runs must be positive")

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
        },
        "schedule": summarize(measure_schedule(args.runs)),
        "summary_computation": summarize(measure_summary(args.runs)),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
