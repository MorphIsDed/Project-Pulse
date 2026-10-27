from datetime import date

import pytest

from app.models.planning import default_weekly_rules
from app.scheduling.calendar import WorkingCalendar
from app.scheduling.cpm import (
    DependencyInput,
    TaskInput,
    compute_schedule,
)
from app.scheduling.errors import ScheduleError


MONDAY = date(2026, 1, 5)


def calendar():
    return WorkingCalendar.from_dict(
        {
            "timezone": "UTC",
            "weekly_rules": default_weekly_rules(),
            "exceptions": [],
        }
    )


def test_forward_and_backward_pass_with_float():
    tasks = [
        TaskInput(1, "A", 480),
        TaskInput(2, "B", 480),
        TaskInput(3, "C", 480),
    ]
    dependencies = [
        DependencyInput(1, 2, "FS"),
    ]

    result = compute_schedule(tasks, dependencies, calendar(), MONDAY)

    assert result.project_finish == 960
    assert result.tasks[1].early_start == 0
    assert result.tasks[2].early_start == 480
    assert result.tasks[3].early_start == 0
    assert result.tasks[1].total_float == 0
    assert result.tasks[2].total_float == 0
    assert result.tasks[3].total_float == 480
    assert result.tasks[3].free_float == 480
    assert result.critical_path == [1, 2]


def test_all_dependency_types():
    tasks = [
        TaskInput(1, "A", 480),
        TaskInput(2, "B", 240),
    ]
    expected = {
        "FS": 480,
        "SS": 0,
        "FF": 240,
    }
    for dependency_type, start in expected.items():
        result = compute_schedule(
            tasks,
            [DependencyInput(1, 2, dependency_type)],
            calendar(),
            MONDAY,
        )
        assert result.tasks[2].early_start == start

    result = compute_schedule(
        tasks,
        [DependencyInput(1, 2, "SF", lag_work_minutes=120)],
        calendar(),
        MONDAY,
    )
    assert result.tasks[2].early_start == 0


def test_milestone_has_no_duration():
    result = compute_schedule(
        [TaskInput(1, "Milestone", 0)],
        [],
        calendar(),
        MONDAY,
    )
    assert result.tasks[1].early_start == 0
    assert result.tasks[1].early_finish == 0


def test_constraints_are_applied_as_working_day_boundaries():
    start_constraint = compute_schedule(
        [
            TaskInput(
                1,
                "Starts Wednesday",
                480,
                "start_no_earlier_than",
                date(2026, 1, 7),
            )
        ],
        [],
        calendar(),
        MONDAY,
    )
    assert start_constraint.tasks[1].early_start == 960

    finish_constraint = compute_schedule(
        [
            TaskInput(
                1,
                "Finishes by Wednesday",
                480,
                "finish_no_later_than",
                date(2026, 1, 7),
            )
        ],
        [],
        calendar(),
        MONDAY,
        target_finish=date(2026, 1, 7),
    )
    assert finish_constraint.tasks[1].late_start == 960
    assert finish_constraint.tasks[1].total_float == 960

    must_finish = compute_schedule(
        [
            TaskInput(
                1,
                "Must finish Tuesday",
                480,
                "must_finish_on",
                date(2026, 1, 6),
            )
        ],
        [],
        calendar(),
        MONDAY,
    )
    assert must_finish.tasks[1].early_start == 480
    assert must_finish.tasks[1].total_float == 0

    finish_floor = compute_schedule(
        [
            TaskInput(
                1,
                "No earlier than last week",
                960,
                "finish_no_earlier_than",
                date(2025, 12, 29),
            )
        ],
        [],
        calendar(),
        MONDAY,
    )
    assert finish_floor.tasks[1].early_start == 0
    assert finish_floor.tasks[1].early_finish == 960


def test_unknown_constraint_type_is_rejected():
    with pytest.raises(ScheduleError) as exc:
        compute_schedule(
            [TaskInput(1, "Bad", 60, "unknown_constraint")],
            [],
            calendar(),
            MONDAY,
        )
    assert exc.value.code == "invalid_constraint"


def test_must_start_can_be_infeasible_with_dependencies():
    tasks = [
        TaskInput(1, "A", 480),
        TaskInput(
            2,
            "B",
            480,
            "must_start_on",
            date(2026, 1, 5),
        ),
    ]
    with pytest.raises(ScheduleError) as exc:
        compute_schedule(
            tasks,
            [DependencyInput(1, 2, "FS")],
            calendar(),
            MONDAY,
        )
    assert exc.value.code == "schedule_infeasible"
    assert exc.value.details == {"task_id": 2}


def test_target_finish_missed_produces_negative_float_and_warning():
    result = compute_schedule(
        [TaskInput(1, "Two days", 960)],
        [],
        calendar(),
        MONDAY,
        target_finish=date(2026, 1, 5),
    )
    assert result.project_finish == 960
    assert result.tasks[1].total_float == -480
    assert result.tasks[1].critical is True
    assert result.warnings[0]["code"] == "target_finish_missed"


def test_required_start_on_nonworking_day_is_invalid():
    with pytest.raises(ScheduleError) as exc:
        compute_schedule(
            [
                TaskInput(
                    1,
                    "Weekend start",
                    480,
                    "must_start_on",
                    date(2026, 1, 3),
                )
            ],
            [],
            calendar(),
            MONDAY,
        )
    assert exc.value.code == "invalid_constraint_date"
