# Architecture

ProjectPulse is a modular monolith: React/TypeScript calls a same-origin Flask JSON API under `/api/v1`; SQLAlchemy persists inputs in SQLite. Alembic manages schema history. NumPy and pandas provide compact analytics without a worker, cache, or new datastore.

## Backend

API modules handle authentication, health, organizations, workspaces, projects, tasks, dependencies, schedules, and ICS export. Service modules contain identity, tenancy, planning, scheduling, summary, export, and demo-seeding behavior. Calendar arithmetic, graph validation, and CPM remain independent of Flask request state.

The project summary service reads task status/duration columns, constructs a pandas DataFrame, aggregates status counts, and uses NumPy for positive-duration mean/median/p90. Schedules and summaries are computed on demand; neither overwrites planning inputs. The obsolete analytics prototype has been deleted.

## Access and storage

Users are global identities. Organizations own workspaces, which own projects. Organization membership is the access boundary, with owner/admin/editor/viewer roles. Every project endpoint, including summary, verifies membership; non-members receive 404 and insufficient roles receive 403. Session mutations require CSRF. Project and calendar edits retain optimistic version checks.

Active models are users, organizations, memberships, workspaces, projects, calendars, tasks, and dependencies. Legacy resources, assignments, notifications, invitations, and task estimates remain mapped solely for database compatibility. No migration or existing data is rewritten by feature retirement. Normal explicit parent deletion retains existing foreign-key cascade semantics.

## Frontend

App handles session restoration and login. WorkspacePage owns selected organization/workspace/project, retained mutation handlers, and Tasks/Timeline/Settings navigation. Dialog supplies native modal behavior and focus restoration. Task and calendar forms preserve drafts on failure. GanttChart remains a custom read-only SVG. Summary failure is isolated from task loading/editing, and project changes discard stale selection. CSS variables provide system light/dark themes and responsive top navigation.

## Limits

SQLite only; no live co-editing, background jobs, drag/resize Gantt, risk simulation, resource leveling, email delivery, or account self-service tools. The basic calendar form edits one interval per day and preserves existing exceptions; the API supports multiple intervals and date exceptions. List endpoints retain their existing pagination contract; the frontend follows task/dependency pages to load the complete plan.
