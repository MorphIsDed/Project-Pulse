# Scheduling assumptions and decisions

This document records the first-release defaults for ProjectPulse. These conventions must be applied consistently in the API, scheduling engine, UI, and evaluation scenarios. If a requirement changes one, update this document before changing implementation.

## Dates and time

- API dates use ISO 8601 calendar dates (`YYYY-MM-DD`); audit timestamps use UTC ISO 8601 timestamps.
- A task's schedule is represented internally by start and finish event times. The finish event is an exclusive boundary: a one-working-day task starting at the beginning of a workday finishes at the end of that day's working interval. The UI may display the last occupied date, but conversion must be explicit.
- Project schedules use one project calendar in the first release. Projects start with a `UTC` calendar using Monday-Friday 09:00-17:00 working intervals and an empty exception list. The app makes the calendar editable by editor, admin, and owner roles; the frontend edits one working window per day, while the API accepts multiple non-overlapping intervals per day.
- All durations and lags are integer working minutes. Calendar arithmetic skips nonworking intervals. Negative lag is permitted and moves a bound earlier in working time; it does not bypass dependency-cycle or hard-constraint checks.
- Zero-duration tasks are milestones. They occupy an event time and consume no working minutes.

## Dependencies

A dependency is a directed relation between two distinct tasks in the same project. Duplicate equivalent edges and cycles are rejected. The project calendar controls dependency lag.

- FS: successor start must be at or after predecessor finish plus lag.
- SS: successor start must be at or after predecessor start plus lag.
- FF: successor finish must be at or after predecessor finish plus lag; convert this to a successor-start bound using its duration and calendar.
- SF: successor finish must be at or after predecessor start plus lag; convert this to a successor-start bound using its duration and calendar.

The same event-time rules apply in forward and backward passes. An acyclic graph can still be infeasible when hard constraints conflict; return a readable validation error rather than silently moving fixed dates.

## Inputs and derived values

Persist user-entered duration, estimates, constraints, dependencies, progress, and calendar data as inputs. Persist or return calculated start/finish, earliest/latest dates, total/free float, and critical status as derived values. Derived values must be recalculated from a consistent project snapshot and must not overwrite the underlying estimates or constraints.

For unconstrained projects, project finish is the latest task finish. If a target finish or explicit deadline is selected as the backward-pass boundary, use that boundary and make it visible in the result. A missed target is advisory: return a warning and negative float rather than rejecting the schedule. Total float is the working-time distance between earliest and latest start (equivalently finish under consistent event-time semantics). Zero total float is critical. Free float is the interval before the task would constrain any successor event.

The app calculates schedules on demand from the current project version and does not persist derived dates. When the project has no start date, use today in the calendar timezone and return a warning. Move a nonworking project start to the next working instant and report the adjustment. Hard constraint conflicts return `422 schedule_infeasible`; never silently move a must-start or must-finish date. The forward and backward passes apply the same FS/SS/FF/SF event rules.

## Calendars

Calendar operations include adding/subtracting working minutes and measuring working minutes between event times. Work intervals, holidays, and exceptions are applied using the project's configured timezone. Working windows are built as timezone-aware local datetimes and converted to UTC; arithmetic is performed on UTC instants, so daylight-saving transitions do not silently treat local wall-clock minutes as elapsed UTC minutes. Tests cover a spring-forward transition.

Calendar validation requires an IANA timezone, all seven day keys (`mon` through `sun`), at least one working interval, `HH:MM` clock values, positive-duration intervals, and no overlaps. Exceptions are unique by date: a nonworking exception has no intervals, while a working exception replaces that date's weekly rule and needs at least one interval.

## Compact analytics

Status counts and completion percentage include milestones. Duration mean, median, and p90 exclude zero-duration milestones and use working-minute inputs. These statistics describe individual task durations, not elapsed project length or deadline confidence. Legacy uncertainty estimates are preserved but do not influence summary calculations or scheduling.

## Decisions

Organization membership is the access boundary; roles remain owner/admin/editor/viewer. Gantt is read-only. Scheduling and summaries are computed on demand. There is no resource leveling or risk simulation in the current product.
