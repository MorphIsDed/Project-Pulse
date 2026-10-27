# Project report brief

## Purpose and implemented modules

ProjectPulse is a local academic planning application: React/TypeScript frontend, Flask API, SQLite persistence, pandas status aggregation, and NumPy duration statistics. Its core contribution is dependency-aware scheduling with working calendars, CPM/float, and a read-only Gantt, supported by project/task management and compact descriptive analytics.

Authentication uses cookie sessions and CSRF; organization membership controls owner/admin/editor/viewer access. The UI uses focused Tasks, Timeline, and Settings views, management dialogs, a responsive top navigation, and system light/dark appearance. ICS export is implemented using standard Python.

## Analytics interpretation

Completion percentage counts completed tasks, including milestones, rather than weighting by duration or averaging progress. pandas groups task statuses. NumPy calculates mean, median, and p90 duration over positive-duration tasks. These are descriptive task statistics, not project-duration predictions. Empty and milestone-only projects have null duration statistics.

## Retired modules and compatibility

Resource/assignment management, overload/leveling, risk simulation, invitations, notifications, and account export/deletion are removed. Existing legacy tables, schema migrations, and estimate fields are retained to preserve databases. The old unregistered analytics prototype is deleted. Do not describe retired modules as active features.

## Evidence and limits

Use docs/evaluation.md for current test and benchmark evidence, docs/api-conventions.md for supported interfaces, and docs/scheduling-assumptions.md for schedule rules. The Gantt is read-only; SQLite is the supported database; calendar UI supports one interval per day while the API supports multiple intervals/exceptions. No human user study or production deployment validation is claimed.

## Suggested report structure

1. Problem and academic objectives.
2. Current functional requirements and roles.
3. Architecture, active schema, and compatibility storage.
4. Calendar arithmetic, dependency graph, CPM, and float.
5. pandas/NumPy descriptive analytics and edge cases.
6. Responsive interface and accessible interaction design.
7. Automated testing, measured performance, and limitations.
