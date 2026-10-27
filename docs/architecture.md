# ProjectPulse architecture

## Purpose

ProjectPulse is a locally deployed planning and analysis application for multiple organizations, workspaces, projects, and users. The first release targets projects of about 1,000 tasks and does not provide live co-editing.

## Architecture

Use a modular monolith: one Flask application, one SQLite database, and one React/TypeScript frontend. Keep scheduling and analytics as deterministic Python modules that do not depend on Flask request state. Route handlers validate/authenticate/authorize requests and call services; services coordinate repositories, persistence, scheduling, and analytics.

```text
Browser (React + TypeScript)
        | versioned JSON HTTP API
Flask application
  auth and permissions | project/task services | integrations
        |                    |                    |
     SQLite          scheduling + analytics     ICS export
```

SQLite is appropriate for local academic deployment and modest concurrent use. Use transactions and optimistic project versions. Do not promise live simultaneous editing. Consider another database only if measured needs require it.

## Initial module boundaries

- `backend/app/api`: thin versioned route handlers for auth, health, organizations, workspaces, projects, tasks, and dependencies.
- `backend/app/models`: SQLAlchemy persistence mappings for identity, tenancy, and planning.
- `backend/app/services`: identity, tenancy/authorization, planning operations, and demo seeding.
- `backend/app/scheduling`: implemented graph validation, timezone-aware calendar arithmetic, constraint handling, and CPM.
- `backend/app/analytics`: planned resource load, leveling preview, and risk simulation; the old prototype route file remains dormant.
- `frontend/src`: auth, state-based planning workspace, schedule summary, calendar editor, read-only SVG Gantt, API client, and tests; resources/analytics are future work.
- `docs`: architecture, API contract, scheduling assumptions, and user guide.

## Tenant access

Users are global identities. Organizations own workspaces; workspaces own projects. Organization membership is the only tenant access boundary in the first release; there are no workspace memberships. A membership carries one of `owner`, `admin`, `editor`, or `viewer`. Every workspace, project, task, and dependency read or mutation verifies membership through the owning organization and checks the role required for the action. Non-members receive `404` so resource existence is not exposed; members without sufficient role receive `403`. IDs supplied by the browser are never proof of access.

## Persistence and audit conventions

Persistence uses Flask-SQLAlchemy models, with Flask-Migrate/Alembic as the only schema-change path. Run `flask db upgrade` from `backend`; use batch mode for SQLite `ALTER` operations. Do not edit applied migrations.

Use integer primary keys, foreign keys, unique membership pairs, and ISO 8601 dates/timestamps. Store audit timestamps in UTC. Enable SQLite foreign-key enforcement on every connection. Store schedule inputs separately from calculated dates. Store a project version and require expected-version checks for edits that can affect a schedule. Save analysis kind, input project version, parameters, summary, creator, and timestamp for reproducibility.

The implemented data model includes users, organizations, organization memberships, workspaces, projects, project calendars, tasks, and dependencies. Resources, assignments, analysis runs, and audit events remain target-model entities for later milestones. Each project receives one default UTC calendar with Monday-Friday 09:00-17:00 weekly rules and an exceptions list. M4 exposes calendar editing and computes CPM schedules on demand; derived schedule dates are not stored. Cross-project resource pooling is out of scope.

## API conventions

Expose JSON under `/api/v1`. Use consistent errors with stable machine-readable codes and readable messages. Paginate list endpoints. Keep frontend and API same-origin in local deployment where practical; use cookie sessions and CSRF protection for state-changing requests if session authentication is selected. Keep secrets and deployment configuration outside source control.

## Delivery order

1. Agree on requirements and scheduling conventions. Done.
2. Establish React/Flask/SQLite local skeleton and health route. Done (M0).
3. Add identity, organizations, workspaces, and permission checks. Done (M1-M2).
4. Add project/task/dependency CRUD and default calendars. Done (M3).
5. Add calendar editing, calendar-aware CPM scheduling, critical path, and float. Done (M4).
6. Add a custom SVG Gantt timeline and read-only schedule visualization. Done (M5).
7. Add resource analysis, then risk simulation. Planned (M6-M7).
8. Add ICS export and polish. Planned (M8).
9. Evaluate scenarios and performance near 1,000 tasks; document measured limits. Planned.

## Boundaries

The initial release excludes live co-editing, advanced portfolio optimization, cross-project resource pooling, enterprise SSO, two-way calendar synchronization, and claims of globally optimal resource leveling. Resource leveling is an explainable preview users accept or reject. Deadline confidence is conditional on the duration estimates and model assumptions.
