# Scheduling assumptions and decisions

This document records the first-release defaults for ProjectPulse. These conventions must be applied consistently in the API, scheduling engine, UI, and evaluation scenarios. If a requirement changes one, update this document before changing implementation.

## Dates and time

- API dates use ISO 8601 calendar dates (`YYYY-MM-DD`); audit timestamps use UTC ISO 8601 timestamps.
- A task's schedule is represented internally by start and finish event times. The finish event is an exclusive boundary: a one-working-day task starting at the beginning of a workday finishes at the end of that day's working interval. The UI may display the last occupied date, but conversion must be explicit.
- Project schedules use one project calendar in the first release. Projects start with a `UTC` calendar using Monday-Friday 09:00-17:00 working intervals and an empty exception list. M4 makes the calendar editable by editor, admin, and owner roles; the frontend edits one working window per day, while the API accepts multiple non-overlapping intervals per day.
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

M4 calculates schedules on demand from the current project version and does not persist derived dates. When the project has no start date, use today in the calendar timezone and return a warning. Move a nonworking project start to the next working instant and report the adjustment. Hard constraint conflicts return `422 schedule_infeasible`; never silently move a must-start or must-finish date. The forward and backward passes apply the same FS/SS/FF/SF event rules.

## Calendars

Calendar operations include adding/subtracting working minutes and measuring working minutes between event times. Work intervals, holidays, and exceptions are applied using the project's configured timezone. Working windows are built as timezone-aware local datetimes and converted to UTC; arithmetic is performed on UTC instants, so daylight-saving transitions do not silently treat local wall-clock minutes as elapsed UTC minutes. Tests cover a spring-forward transition.

Calendar validation requires an IANA timezone, all seven day keys (`mon` through `sun`), at least one working interval, `HH:MM` clock values, positive-duration intervals, and no overlaps. Exceptions are unique by date: a nonworking exception has no intervals, while a working exception replaces that date's weekly rule and needs at least one interval.

## Resources and leveling

Resource capacity and assignment units are compared over working intervals. Overload results identify the resource, interval, assigned load, capacity, and contributing tasks. A leveling preview preserves dependency and fixed-date constraints, ranks movable tasks by lower priority first, then larger available float, then stable task ID, and proposes changes for user acceptance. It is a heuristic, not an optimal solution. The preview may extend the project finish when a proposal requires it, but only while the simulated finish remains on or before `target_finish`; otherwise the proposal is rejected.

## Risk simulation

Optimistic, most-likely, and pessimistic durations are explicit user inputs. The PERT mean is `(a + 4m + b) / 6`; beta-PERT sampling is the distribution. A task uses the beta-PERT sample only when all three estimates are present and `0 <= a <= m <= b`; otherwise it keeps its deterministic duration in every iteration. A run records its random seed, iteration count, target deadline, project version, and distribution assumptions. Report median/percentile finish dates, deadline-hit probability, and per-task critical frequency with the assumptions; results are planning estimates, not guarantees. Iterations default to 2,000 and are limited to 100-10,000, and the endpoint runs synchronously.

## Decisions

Resolved for the first release:

- Organization membership alone grants access; workspace membership is not used.
- Roles are `owner`, `admin`, `editor`, and `viewer`.
- M4 enforces all seven task constraints during scheduling. Must-start/must-finish conflicts are hard errors; no-earlier/no-later bounds and target finish are applied explicitly.
- M4 supports editable timezones, weekly rules, and date exceptions. The default remains UTC Monday-Friday 09:00-17:00.
- The Gantt uses a custom SVG implementation with no new charting dependency; the current version is read-only.
- Schedules, resource workloads, leveling previews, and risk simulations are computed on demand and are not persisted; simulations return the seed, project version, and assumptions needed to reproduce them.
- Seeded local password accounts are sufficient for the demo; invitation delivery uses SMTP when configured and otherwise logs in development.

Still open:

- Drag/resize Gantt editing and the exact interaction set for the academic evaluation.
