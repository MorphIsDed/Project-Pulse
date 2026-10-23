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

- `backend/app/api`: thin versioned route handlers.
- `backend/app/models` and `repositories`: persistence mapping and queries.
- `backend/app/services`: project/task operations and authorization.
- `backend/app/scheduling`: graph validation, calendar arithmetic, constraints, CPM.
- `backend/app/analytics`: resource load, leveling preview, risk simulation.
- `frontend/src`: navigation, project/task editing, Gantt, resources, analytics.
- `docs`: architecture, API contract, scheduling assumptions, and user guide.

## Tenant access

Users are global identities. Organizations own workspaces; workspaces own projects. Organization membership grants the base organization boundary. Workspace membership, when enabled, narrows access. Every project read and mutation must verify the caller's membership through the owning organization and any applicable workspace rule. IDs supplied by the browser are never proof of access.

## Persistence and audit conventions

Persistence uses Flask-SQLAlchemy models, with Flask-Migrate/Alembic as the only schema-change path. Run `flask db upgrade` from `backend`; use batch mode for SQLite `ALTER` operations. Do not edit applied migrations.

Use integer primary keys, foreign keys, unique membership pairs, and ISO 8601 dates/timestamps. Store audit timestamps in UTC. Enable SQLite foreign-key enforcement on every connection. Store schedule inputs separately from calculated dates. Store a project version and require expected-version checks for edits that can affect a schedule. Save analysis kind, input project version, parameters, summary, creator, and timestamp for reproducibility.

The initial data model includes organizations, users, organization/workspace memberships, workspaces, projects, tasks, dependencies, project calendars, resources, assignments, analysis runs, and lightweight audit events. Project calendars are the first-release calendar policy; cross-project resource pooling is out of scope.

## API conventions

Expose JSON under `/api/v1`. Use consistent errors with stable machine-readable codes and readable messages. Paginate list endpoints. Keep frontend and API same-origin in local deployment where practical; use cookie sessions and CSRF protection for state-changing requests if session authentication is selected. Keep secrets and deployment configuration outside source control.

## Delivery order

1. Agree on requirements and scheduling conventions.
2. Establish React/Flask/SQLite local skeleton and health route.
3. Add identity, organizations, workspaces, and permission checks.
4. Add project/task/dependency CRUD.
5. Add calendar-aware scheduling, Gantt, critical path, and float.
6. Add resource analysis, then risk simulation.
7. Add ICS export and polish.
8. Evaluate scenarios and performance near 1,000 tasks; document measured limits.

## Boundaries

The initial release excludes live co-editing, advanced portfolio optimization, cross-project resource pooling, enterprise SSO, two-way calendar synchronization, and claims of globally optimal resource leveling. Resource leveling is an explainable preview users accept or reject. Deadline confidence is conditional on the duration estimates and model assumptions.
