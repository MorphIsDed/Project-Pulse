# Scheduling assumptions and decisions

This document records the first-release defaults for ProjectPulse. These conventions must be applied consistently in the API, scheduling engine, UI, and evaluation scenarios. If a requirement changes one, update this document before changing implementation.

## Dates and time

- API dates use ISO 8601 calendar dates (`YYYY-MM-DD`); audit timestamps use UTC ISO 8601 timestamps.
- A task's schedule is represented internally by start and finish event times. The finish event is an exclusive boundary: a one-working-day task starting at the beginning of a workday finishes at the end of that day's working interval. The UI may display the last occupied date, but conversion must be explicit.
- Project schedules use one project calendar in the first release. The calendar defines timezone, weekly work intervals, holidays, and dated exceptions.
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

For unconstrained projects, project finish is the latest task finish. If a target finish or explicit deadline is selected as the backward-pass boundary, use that boundary and make it visible in the result. Total float is the working-time distance between earliest and latest start (equivalently finish under consistent event-time semantics). Zero total float is critical. Free float is the interval before the task would constrain any successor event.

## Calendars

Calendar operations must include adding/subtracting working minutes and measuring working minutes between event times. Work intervals, holidays, and exceptions are applied using the project's configured timezone. Calendar behavior around daylight-saving transitions must be specified by the implementation and covered by scenarios before release; internal arithmetic should avoid silently treating local wall-clock minutes as elapsed UTC minutes.

## Resources and leveling

Resource capacity and assignment units are compared over working intervals. Overload results identify the resource, interval, assigned load, capacity, and contributing tasks. A leveling preview preserves dependency and fixed-date constraints, ranks movable tasks by lower priority first, then larger available float, then stable task ID, and proposes changes for user acceptance. It is a heuristic, not an optimal solution.

## Risk simulation

Optimistic, most-likely, and pessimistic durations are explicit user inputs. The PERT mean is `(a + 4m + b) / 6`; beta-PERT sampling is the initial distribution. Tasks without estimate ranges remain deterministic. A run records its random seed, iteration count, target deadline, project version, and distribution settings. Report median/percentile finish dates and deadline-hit probability with the assumptions; results are planning estimates, not guarantees.

## Open decisions to confirm during requirements review

- Whether workspace membership is mandatory or organization membership alone grants project access.
- The exact roles and which actions each role may perform.
- Whether task constraints are hard or advisory, and which constraint types ship first.
- Whether users can choose project timezone and working intervals, or begin with a fixed weekday calendar.
- Which Gantt interactions and library are required for the academic evaluation.
- Whether password login is required for the first demo or a seeded local account is sufficient.
