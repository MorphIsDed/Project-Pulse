from datetime import date, datetime, timezone

import pytest

from app.models.planning import default_weekly_rules
from app.scheduling.calendar import WorkingCalendar
from app.scheduling.errors import ScheduleError


def make_calendar(**overrides):
    data = {
        "timezone": "UTC",
        "weekly_rules": default_weekly_rules(),
        "exceptions": [],
    }
    data.update(overrides)
    return WorkingCalendar.from_dict(data)


def test_working_minutes_skip_weekends_and_holidays():
    calendar = make_calendar(
        exceptions=[
            {
                "date": "2026-01-05",
                "name": "Holiday",
                "working": False,
            }
        ]
    )
    origin = calendar.first_start_on_or_after(date(2026, 1, 2))

    assert calendar.local_date(origin) == date(2026, 1, 2)
    assert calendar.add_working_minutes(origin, 60) == datetime(
        2026, 1, 2, 10, 0, tzinfo=timezone.utc
    )
    assert calendar.add_working_minutes(origin, 480) == datetime(
        2026, 1, 2, 17, 0, tzinfo=timezone.utc
    )
    assert calendar.add_working_minutes(origin, 540) == datetime(
        2026, 1, 6, 10, 0, tzinfo=timezone.utc
    )


def test_working_time_spans_multiple_intervals_and_negative_direction():
    calendar = make_calendar(
        weekly_rules={
            "mon": [["09:00", "11:00"], ["13:00", "17:00"]],
            "tue": [["09:00", "11:00"], ["13:00", "17:00"]],
            "wed": [["09:00", "11:00"], ["13:00", "17:00"]],
            "thu": [["09:00", "11:00"], ["13:00", "17:00"]],
            "fri": [["09:00", "11:00"], ["13:00", "17:00"]],
            "sat": [],
            "sun": [],
        }
    )
    origin = calendar.first_start_on_or_after(date(2026, 1, 5))

    assert calendar.add_working_minutes(origin, 120) == datetime(
        2026, 1, 5, 11, 0, tzinfo=timezone.utc
    )
    assert calendar.add_working_minutes(origin, 180) == datetime(
        2026, 1, 5, 14, 0, tzinfo=timezone.utc
    )
    assert calendar.add_working_minutes(origin, -60) == datetime(
        2026, 1, 2, 16, 0, tzinfo=timezone.utc
    )


def test_dst_dates_keep_the_configured_local_working_window():
    calendar = make_calendar(timezone="America/New_York")
    origin = calendar.first_start_on_or_after(date(2026, 3, 6))

    finish = calendar.add_working_minutes(origin, 960)

    assert calendar.local_date(finish) == date(2026, 3, 9)
    assert calendar.local_datetime(finish).hour == 17
    assert calendar.working_minutes_between(origin, finish) == 960


def test_calendar_validation_rejects_overlap_and_bad_exceptions():
    with pytest.raises(ScheduleError) as overlap:
        make_calendar(
            weekly_rules={
                "mon": [["09:00", "12:00"], ["11:00", "17:00"]],
                "tue": [],
                "wed": [],
                "thu": [],
                "fri": [],
                "sat": [],
                "sun": [],
            }
        )
    assert overlap.value.code == "invalid_calendar"

    with pytest.raises(ScheduleError) as holiday:
        make_calendar(
            exceptions=[
                {
                    "date": "2026-01-01",
                    "working": False,
                    "intervals": [["09:00", "12:00"]],
                }
            ]
        )
    assert holiday.value.code == "invalid_exception"

    with pytest.raises(ScheduleError) as timezone_error:
        make_calendar(timezone="Not/AZone")
    assert timezone_error.value.code == "invalid_timezone"
