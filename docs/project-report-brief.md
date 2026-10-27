# ProjectPulse Report Brief

This document is a source pack for writing a detailed academic report about ProjectPulse. It separates what is actually implemented from what is planned, and it deliberately includes the modules that are **not** implemented so the report does not overstate the project.

- Repository: <https://github.com/MorphIsDed/Project-Pulse>
- Branch: `main`
- Last committed baseline: see `git log -1`; M6-M9, collaboration, and documentation are committed after the M0-M5 baseline.
- Snapshot date: 2026-10-27
- Purpose: implementation evidence, architecture notes, test evidence, limitations, and a suggested report structure.

> **Most important caution:** M0-M8 are implemented and active, including resources/leveling, seeded risk simulation, ICS export, invitations, notifications, and account tools. `backend/app/api/analytics.py` is an old unregistered prototype and should not be counted as active code. Automated evaluation and benchmarks are documented in [evaluation.md](evaluation.md); a human user evaluation was not conducted. See [Dormant and unintegrated code](#10-dormant-and-unintegrated-code).

---

## 1. How to use this brief

Use this document in three ways:

1. Copy verified facts and file references into the report.
2. Use the module status tables to separate completed work from future work.
3. Use the suggested report outline in [Section 14](#14-suggested-report-outline) to structure the final document.

The brief is intentionally explicit about evidence. A feature is counted as implemented only when it is wired into the active Flask app, has a current data model/migration where needed, and has tests or a documented manual verification path.

Status labels used in this document:

| Label | Meaning |
| --- | --- |
| Implemented | Active in the running application and supported by tests or documented verification. |
| Dormant | Code exists in the repository but is not imported, registered, migrated, or tested. Do not claim it as working. |
| Not implemented | No active implementation exists yet; only the target design is documented. |

---

## 2. Executive summary

ProjectPulse is an academic, locally deployed project planning and analytics application. The intended product combines a React + TypeScript frontend, a Flask JSON API, and a SQLite database in a modular monolith. The long-term goal is to support organizations, workspaces, projects, tasks, dependencies, calendars, resource analysis, schedule calculation, risk simulation, and calendar export.

At the snapshot date, the project has completed:

- **M0 - Platform foundation:** application factory, configuration, database and migration setup, error envelope, request IDs, health endpoint, CLI, test fixtures, and CI.
- **M1 - Identity:** user model and migration, password hashing, email normalization, registration policy, login/logout/current-user endpoints, CSRF protection, remember-me, demo-account seeding, and a React sign-in experience with session restore.
- **M2 - Organization/workspace access control:** organization membership and role models, workspaces, owner/admin/editor/viewer permissions, member management with a last-owner guard, organization/workspace/member APIs, and seeded demo tenancy.
- **M3 - Core planning:** projects, default project calendars, task hierarchy, task constraints/PERT inputs, dependencies, CRUD APIs, optimistic project versioning, graph validation, and a state-based React planning workspace.
- **M4 - Calendar editing and CPM scheduling:** timezone-aware working calendars, weekly rules and exception validation, calendar PATCH, on-demand FS/SS/FF/SF scheduling with lag, all seven constraints, target-finish warnings, earliest/latest dates, total/free float, critical path, schedule API, basic calendar editor, and schedule summary.
- **M5 - Gantt visualization:** custom read-only SVG timeline with task bars, dependency links, milestones, critical-path emphasis, float bars, weekend shading, and a schedule legend.
- **M6 - Resource analysis:** project resources, task assignments, workload aggregation, overload detection, and a heuristic leveling preview bounded by `target_finish`.
- **M7 - Risk simulation:** seeded beta-PERT Monte Carlo, deterministic fallback, finish percentiles, target probability, critical frequency, and a risk panel.
- **M8 - ICS export:** authenticated all-day VEVENT export with escaped text and project-named attachments.
- **Collaboration and accounts:** invitation tokens, in-app invitation/task notifications, read state, JSON account export, and password-confirmed account deletion.
- **M9 - Evaluation:** 108 backend tests, 64 frontend tests, full migration-cycle verification, a reproducible benchmark, and documented scenarios and limitations. A human user evaluation was not conducted.

`backend/app/api/analytics.py` remains a dormant artifact from the earlier prototype. The active organization/workspace/project/task/resource routes and services are separate from that file.

---

## 3. Repository snapshot and technology stack

| Area | Technology |
| --- | --- |
| Backend | Python 3.11+, Flask 3.1, Flask-SQLAlchemy, Flask-Migrate/Alembic, Flask-WTF/CSRF, Flask-Login |
| Database | SQLite |
| Frontend | React, TypeScript, Vite |
| Frontend tests | Vitest, jsdom, React Testing Library |
| Backend tests | pytest, pytest-flask |
| CI | GitHub Actions (`.github/workflows/ci.yml`) |
| Authentication | Same-origin cookie sessions with Flask-Login and CSRF tokens |

### Repository map

| Path | Purpose |
| --- | --- |
| `backend/app/__init__.py` | Flask app factory and extension/blueprint registration. |
| `backend/app/config.py` | Environment loading and development/testing/production configuration. |
| `backend/app/extensions.py` | SQLAlchemy, Migrate, LoginManager, CSRF, and SQLite pragmas. |
| `backend/app/errors.py` | Consistent JSON error envelope and exception handlers. |
| `backend/app/request_context.py` | Request IDs, timing, and access logging. |
| `backend/app/api/` | Active auth, health, tenancy, planning, resource, schedule, risk, export, collaboration, and account blueprints. |
| `backend/app/models/` | Active user, tenancy, planning, resource, and collaboration models. |
| `backend/app/services/` | Identity, tenancy/authorization, planning, scheduling, resource, risk, export, collaboration, account, and demo-seeding services. |
| `backend/scripts/benchmark.py` | Reproducible 1,000-task schedule and risk-simulation benchmark. |
| `backend/migrations/` | Alembic baseline plus users, tenancy, planning, resources, and collaboration revisions. |
| `backend/tests/` | Backend test suite covering M0-M8 and seed/demo behavior. |
| `frontend/src/` | React app, auth context, API client, planning workspace, Gantt, resource/risk/collaboration/account panels, and tests. |
| `docs/` | Architecture, API conventions, scheduling assumptions, deployment, evaluation, and this brief. |
| `.github/workflows/ci.yml` | Backend and frontend CI jobs. |


> `backend/Dockerfile` and `docs/deployment.md` describe the current Flask/SQLite/Alembic deployment path. A production deployment, backup drill, and restore drill have not been performed.

---

## 4. Product context, goals, and non-goals

### 4.1 Problem and target user

The project targets a small organization or project team that needs to plan work locally. The planned application helps users:

- organize work into organizations, workspaces, and projects;
- create tasks and dependencies;
- calculate a schedule from working calendars;
- identify critical work and float;
- detect resource overload;
- estimate deadline confidence;
- export project dates to a calendar.

The initial performance target is approximately **1,000 tasks in one project**. Live multi-user co-editing is outside the first release.

### 4.2 Goals

- Provide a working local planning and analysis application.
- Show task timing, dependency effects, critical work, resource overload, and deadline uncertainty.
- Keep scheduling and analytics logic independent of Flask request state.
- Use consistent, testable API and database conventions.
- Evaluate the application with documented scenarios and measured performance.

### 4.3 Non-goals for the initial release

- Live multi-user editing or real-time presence.
- Enterprise single sign-on.
- Portfolio-level optimization or cross-project resource pooling.
- Two-way calendar synchronization or OAuth calendar integrations.
- Globally optimal resource-constrained scheduling.
- Real-time chat or live editing. Email is limited to organization invitations.

The full product plan is in [plan.md](../plan.md).

---

## 5. Implementation status at a glance

| Module | Status | Summary |
| --- | --- | --- |
| M0 - Platform foundation | Implemented | App factory, config, SQLAlchemy, Alembic, CSRF/login scaffolding, error envelope, request IDs, health, CLI, tests, CI. |
| M1 - Identity | Implemented | User model and migration, password hashing, login/logout/me, CSRF, remember-me, demo users, React auth flow. |
| M2 - Organization/workspace access control | Implemented | Organization membership/roles, workspace tenancy, member management, last-owner guard, APIs, and demo tenancy. |
| M3 - Core project/task planning | Implemented | Projects, default calendars, task hierarchy/constraints/PERT fields, dependencies, versioning, validation, APIs, and planning UI. |
| M4 - Calendar editing and CPM scheduling | Implemented | Editable timezone-aware calendars, schedule API, FS/SS/FF/SF propagation, constraints, float, critical path, and basic schedule UI. |
| M5 - Gantt visualization | Implemented | Custom read-only SVG timeline with bars, dependency links, milestones, critical-path emphasis, float bars, and weekend shading. |
| M6 - Resource analytics | Implemented | Project resources/assignments, workload and overloads, heuristic leveling preview, and React panel. |
| M7 - Risk simulation | Implemented | Seeded beta-PERT Monte Carlo with deterministic fallback, percentiles, target probability, critical frequency, and React panel. |
| M8 - ICS export | Implemented | Authenticated all-day VEVENT export with escaping and a workspace action. |
| Collaboration and accounts | Implemented | Invitations, notifications, account export, and account deletion. |
| Phase 8 - Evaluation and final report | Partly complete | Automated tests, migration cycle, benchmark, scenarios, and limitations are documented; no human user evaluation. |


![Implementation status](https://img.shields.io/badge/status-M0%20to%20M8%20implemented-2f6f5e)

---

## 6. Architecture as implemented

### 6.1 Request lifecycle

```mermaid
flowchart LR
    B[Browser: React + TypeScript] -->|JSON over /api/v1| F[Flask app factory]
    F --> R[Request ID and request logging]
    R --> C[CSRF and Flask-Login]
    C --> A[Auth and health blueprints]
    C --> T[Organization/workspace/project/task/dependency blueprints]
    A --> I[Identity service]
    T --> S[Tenancy and planning services]
    I --> D[(SQLite via SQLAlchemy)]
    S --> D
    T --> E[Consistent JSON error envelope]
```

The active backend is a Flask application factory. `create_app()` in `backend/app/__init__.py` loads configuration, validates it, initializes extensions, registers blueprints and CLI commands, registers error handlers, and registers request-context hooks.

### 6.2 Backend components

- **App factory:** `create_app(config_name=None, overrides=None)` in `backend/app/__init__.py`.
- **Configuration:** `backend/app/config.py` loads root `.env` and `backend/.env`, selects development/testing/production configuration, and provides an environment-variable boolean helper.
- **Extensions:** `backend/app/extensions.py` initializes SQLAlchemy with a naming convention, Flask-Migrate with batch mode, Flask-Login, and Flask-WTF CSRF. SQLite foreign keys and a busy timeout are enabled per connection.
- **Blueprints:** `backend/app/api/__init__.py` registers auth, health, organizations, workspaces, projects, tasks, dependencies, resources, schedules, risk, exports, collaboration, and accounts. `analytics.py` remains unregistered.
- **Error handling:** `backend/app/errors.py` converts API errors, CSRF errors, HTTP errors, and unexpected exceptions into one JSON envelope.
- **Request correlation:** `backend/app/request_context.py` assigns or echoes `X-Request-ID`, measures duration, and logs method/path/status/duration/request ID.
- **Health check:** `backend/app/api/health.py` executes `SELECT 1` and returns 200 or 503.
- **CLI:** `backend/app/cli.py` registers `flask seed-demo`, which calls the demo service.
- **Database:** `backend/app/models/` contains `User`, organization/membership/workspace, project/calendar/task/dependency/resource/assignment, notification, and invitation models. Migrations include tenancy, planning, resources, and collaboration revisions; the current head is `9c3d5e7f8a9b`.
- **Services:** `identity.py`, `tenancy.py`, `planning.py`, `scheduling.py`, `resources.py`, `risk.py`, `export.py`, `collaboration.py`, `account.py`, and `demo.py` hold validation, authorization, CRUD, versioning, graph checks, CPM coordination, analytics, export, collaboration, account lifecycle, and idempotent seeding.
- **Scheduling:** `backend/app/scheduling/calendar.py` implements timezone-aware working-time arithmetic; `cpm.py` implements dependency propagation, constraints, floats, and critical path; `graph.py` handles topology/cycle checks.
- **Frontend:** `frontend/src/App.tsx` controls session restore, health display, login, and sign-out. `frontend/src/pages/WorkspacePage.tsx` renders the state-based planning workspace, calendar editor, schedule summary, Gantt, resource, risk, invitation, notification, and account panels; `frontend/src/lib/api.ts` owns CSRF handling and API calls.

### 6.3 Security and API conventions

- Authentication uses same-origin cookie sessions backed by Flask-Login.
- State-changing requests require an `X-CSRFToken` header. The frontend obtains a token from `GET /api/v1/auth/csrf`, retries once on `csrf_error`, and refreshes the token after login/registration.
- Error responses use one envelope:
  ```json
  {
    "error": {
      "code": "validation_error",
      "message": "Required fields are missing.",
      "details": { "fields": ["email"] },
      "request_id": "4f4c12f0a7e14f0f9f5b0d4f3f7d2a1c"
    }
  }
  ```
- `code` is stable and machine-readable; `message` is safe to display; `details` is optional; `request_id` matches the `X-Request-ID` response header and log entry.
- Unhandled exceptions return a generic `internal_error`; stack traces stay in server logs.
- API calendar dates use `YYYY-MM-DD`; audit timestamps use UTC ISO 8601; durations and lags use integer working minutes.
- See [docs/api-conventions.md](api-conventions.md) for the full convention.

---

## 7. Implemented module M0 — Platform foundation

### 7.1 What exists

| Capability | Evidence | Notes |
| --- | --- | --- |
| Flask app factory | `backend/app/__init__.py` | Loads config, initializes extensions, registers blueprints/CLI/errors/request context. |
| Environment configuration | `backend/app/config.py`, `.env.example`, `backend/.flaskenv` | Development, testing, and production classes. Production requires `SECRET_KEY`. |
| SQLAlchemy and Alembic | `backend/app/extensions.py`, `backend/migrations/` | Baseline, users, tenancy, and planning revisions. Batch mode for SQLite. |
| Session/auth scaffolding | `backend/app/__init__.py`, `backend/app/extensions.py` | Flask-Login user loader and unauthorized handler; Flask-WTF CSRF. |
| Error envelope | `backend/app/errors.py`, `docs/api-conventions.md` | API/CSRF/HTTP/unexpected exception handlers. |
| Request IDs and logging | `backend/app/request_context.py` | Generates/echoes `X-Request-ID`; logs method, path, status, duration, request ID. |
| Health endpoint | `backend/app/api/health.py` | Database-aware 200/503 response. |
| Demo seeding CLI | `backend/app/cli.py`, `backend/app/services/demo.py` | Idempotent user and demo-tenant seeding; refuses production unless `--force`. |
| Test fixtures | `backend/tests/conftest.py` | Isolated temporary SQLite database per app; no production/instance database. |
| CI | `.github/workflows/ci.yml` | Backend migrations up/down/up, seed-demo, pytest; frontend npm ci, tests, build. |

### 7.2 Configuration defaults

| Variable | Purpose | Default |
| --- | --- | --- |
| `SECRET_KEY` | Flask session signing key | Development fallback (`development-only-change-me`). |
| `DATABASE_URL` | SQLAlchemy database URI | `sqlite:///projectpulse.sqlite3` (resolves under `backend/instance/`). |
| `APP_ENV` | `development`, `testing`, or `production` | `development`. |
| `ALLOW_PUBLIC_SIGNUP` | Enables public registration | `false`. |
| `DEMO_PASSWORD` | Password assigned by `seed-demo` | `DemoPulse123!`. |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` | `INFO`. |

Production enables secure session and remember cookies and requires a real `SECRET_KEY`.

### 7.3 CI pipeline

The GitHub Actions workflow runs on pushes and pull requests targeting `main`:

**Backend job**
1. Check out the repository and install Python 3.11.
2. Install `requirements.txt`.
3. Run `flask --app wsgi db upgrade`.
4. Run `flask --app wsgi db downgrade base`.
5. Run `flask --app wsgi db upgrade`.
6. Run `flask --app wsgi seed-demo`.
7. Run `python -m pytest -q`.

**Frontend job**
1. Check out the repository and install Node LTS.
2. Run `npm ci`.
3. Run `npm test`.
4. Run `npm run build`.

The migration cycle is important evidence: it checks that the schema can be created, removed, and recreated from Alembic alone.

---

## 8. Implemented module M1 — Identity

### 8.1 Data model

The identity module contributes the `users` table, created by migration `bef85313fea6`.

| Column | Type/constraint | Purpose |
| --- | --- | --- |
| `id` | Integer primary key | Internal user identifier. |
| `email` | String(320), unique, indexed, not null | Normalized login identity. |
| `password_hash` | String(255), not null | Werkzeug password hash; never returned by the API. |
| `display_name` | String(80), not null | Human-readable name. |
| `is_active` | Boolean, not null, default true | Allows accounts to be disabled. |
| `created_at` | Timezone-aware datetime, not null | UTC audit timestamp. |
| `updated_at` | Timezone-aware datetime, not null | UTC audit timestamp. |

The model is in `backend/app/models/user.py`. The migration is in `backend/migrations/versions/bef85313fea6_add_users.py`. `backend/app/models/__init__.py` now imports the user, tenancy, and planning models so Alembic discovers the full schema.

### 8.2 Identity rules

- Email is stripped and lowercased before validation and storage.
- Email must match a simple address pattern and be at most 320 characters.
- Password must be 8–128 characters.
- Display name must be non-empty and at most 80 characters.
- Passwords are hashed with Werkzeug's `generate_password_hash`; login uses `check_password_hash`.
- Unknown email and wrong password both return the same `401 invalid_credentials` message.
- Inactive users cannot log in.
- Duplicate registration returns `409 email_taken`.
- Public registration is disabled by default and returns `403 registration_disabled` unless `ALLOW_PUBLIC_SIGNUP=true`.
- User responses contain `id`, `email`, and `display_name` only; password hashes are never returned.

### 8.3 Authentication endpoints

| Method | Path | Auth | CSRF | Purpose |
| --- | --- | --- | --- | --- |
| `GET` | `/api/v1/auth/csrf` | No | No | Issue a CSRF token. |
| `POST` | `/api/v1/auth/register` | No | Yes | Create an account when public signup is enabled. |
| `POST` | `/api/v1/auth/login` | No | Yes | Start a cookie session. |
| `POST` | `/api/v1/auth/logout` | No (idempotent) | Yes | End the session; idempotent. |
| `GET` | `/api/v1/auth/me` | Session | No | Return the current user. |
| `GET` | `/api/v1/health` | No | No | Check API and database health. |

Login and registration accept JSON with `email` and `password`; registration also needs `display_name`; login optionally accepts `remember`. Successful login/registration return:

```json
{
  "user": { "id": 1, "email": "owner@demo.local", "display_name": "Demo Owner" },
  "csrf_token": "..."
}
```

`remember=true` sets Flask-Login's remember cookie, configured for 14 days. Logout clears the session and returns `{"status": "ok"}`.

### 8.4 Login and CSRF sequence

```mermaid
sequenceDiagram
    participant U as Browser
    participant F as React frontend
    participant A as Flask API
    U->>F: Open app
    F->>A: GET /api/v1/auth/me
    alt session exists
        A-->>F: 200 user
    else no session
        A-->>F: 401 unauthorized
    end
    U->>F: Submit email/password
    F->>A: GET /api/v1/auth/csrf
    A-->>F: csrf_token
    F->>A: POST /api/v1/auth/login + X-CSRFToken
    A-->>F: 200 user + fresh csrf_token
    F-->>U: Signed-in landing state
    U->>F: Sign out
    F->>A: POST /api/v1/auth/logout + X-CSRFToken
    A-->>F: 200 {"status":"ok"}
    F-->>U: Login page
```

### 8.5 Demo accounts and seeding

`flask seed-demo` creates three accounts and a demo tenant idempotently:

| Email | Display name | Demo organization role |
| --- | --- | --- |
| `owner@demo.local` | Demo Owner | owner |
| `editor@demo.local` | Demo Editor | editor |
| `viewer@demo.local` | Demo Viewer | viewer |

The default password is `DemoPulse123!` unless `DEMO_PASSWORD` is set. The command skips existing users and refuses to run in production unless `--force` is passed. It also seeds `Demo Organization`, `Demo Workspace`, `Demo Project`, tasks `Plan launch`, `Build product`, and `Review launch`, plus finish-to-start dependencies between them. The tenant seed is idempotent, and the command still prints the existing user-creation summary followed by a tenant summary.

### 8.6 Frontend auth experience

- `AuthProvider` restores the session on mount by calling `/auth/me`; a 401 quietly clears the user.
- `LoginPage` pre-fills `owner@demo.local`, accepts an optional "keep me signed in" checkbox, disables submit while pending, and shows API error messages.
- The signed-in view shows the display name and sign-out action in the top bar, then renders the planning workspace. The health state is shown on the login screen.
- The API client fetches a CSRF token before unsafe methods, retries once on `csrf_error`, and refreshes the token after login/registration.
- The app shows the API health state and the seeded demo credentials on the login screen.

### 8.7 Test coverage

Backend tests cover identity behavior plus organization/workspace roles and isolation, last-owner protection, member management, project/task/dependency CRUD and validation, dependency/hierarchy cycles, optimistic project versions, CSRF on tenancy mutations, demo-tenant seeding, configuration, errors, request IDs, health, and database isolation.

Frontend tests cover session restore, unauthorized sessions, login/logout success and failure, health states, form accessibility, remember-me, pending states, API errors, auth guards, planning-workspace loading, organization/project/task/dependency creation, calendar updates, schedule rendering, API client planning/schedule calls, and viewer read-only controls.

---

## 9. Actual API and data model

### 9.1 Actual API surface

Active routes under `/api/v1`:

- `GET /health`
- `GET /auth/csrf`; `POST /auth/register`; `POST /auth/login`; `POST /auth/logout`; `GET /auth/me`
- `GET/POST /organizations`; `GET/PATCH/DELETE /organizations/<id>`
- `GET/POST /organizations/<id>/members`; `PATCH/DELETE /organizations/<id>/members/<user_id>`
- `GET/POST /organizations/<id>/workspaces`
- `GET/PATCH/DELETE /workspaces/<id>`
- `GET/POST /workspaces/<id>/projects`
- `GET/PATCH/DELETE /projects/<id>`; `GET/PATCH /projects/<id>/calendar`; `GET /projects/<id>/schedule`
- `GET/POST /projects/<id>/tasks`; `GET/PATCH/DELETE /projects/<id>/tasks/<task_id>`
- `GET/POST /projects/<id>/dependencies`; `DELETE /projects/<id>/dependencies/<dependency_id>`
- `GET/POST /projects/<id>/resources`; `PATCH/DELETE /projects/<id>/resources/<resource_id>`
- `GET/POST /projects/<id>/assignments`; `PATCH/DELETE /projects/<id>/assignments/<assignment_id>`
- `GET /projects/<id>/workload`; `POST /projects/<id>/leveling-preview`
- `POST /projects/<id>/risk-simulation`; `GET /projects/<id>/export.ics`
- `GET /notifications`; `PATCH /notifications/<id>`; `POST /notifications/read-all`
- `GET/POST /organizations/<id>/invitations`; `DELETE /organizations/<id>/invitations/<invitation_id>`; `POST /invitations/accept`
- `GET /account/export`; `DELETE /account`

All routes except health require authentication. Every tenancy/planning route requires organization membership; mutations apply the role rules documented in [docs/api-conventions.md](api-conventions.md). List routes accept `limit` and `offset`.

### 9.2 Actual entity-relationship model

```mermaid
erDiagram
    USERS {
        int id PK
        string email UK
        string password_hash
        string display_name
        boolean is_active
        datetime created_at
        datetime updated_at
    }
    ORGANIZATIONS {
        int id PK
        string name
        datetime created_at
        datetime updated_at
    }
    ORGANIZATION_MEMBERSHIPS {
        int organization_id PK,FK
        int user_id PK,FK
        string role
        datetime created_at
        datetime updated_at
    }
    WORKSPACES {
        int id PK
        int organization_id FK
        string name
        datetime created_at
        datetime updated_at
    }
    PROJECTS {
        int id PK
        int workspace_id FK
        string name
        string status
        date start_date
        date target_finish
        int version
        int created_by FK
        datetime created_at
        datetime updated_at
    }
    PROJECT_CALENDARS {
        int id PK
        int project_id FK,UK
        string name
        string timezone
        json weekly_rules
        json exceptions
        datetime created_at
        datetime updated_at
    }
    TASKS {
        int id PK
        int project_id FK
        int parent_task_id FK
        string name
        string description
        string status
        int duration_work_minutes
        int progress
        int priority
        string constraint_type
        date constraint_date
        int estimate_optimistic
        int estimate_most_likely
        int estimate_pessimistic
        datetime created_at
        datetime updated_at
    }
    DEPENDENCIES {
        int id PK
        int project_id FK
        int predecessor_task_id FK
        int successor_task_id FK
        string type
        int lag_work_minutes
        datetime created_at
        datetime updated_at
    }
    RESOURCES {
        int id PK
        int project_id FK
        string name
        string role
        int capacity_work_minutes_per_day
    }
    ASSIGNMENTS {
        int id PK
        int project_id FK
        int resource_id FK
        int task_id FK
        int allocation_percent
    }
    NOTIFICATIONS {
        int id PK
        int user_id FK
        int organization_id FK
        int project_id FK
        int task_id FK
        string kind
        string message
        datetime read_at
    }
    WORKSPACE_INVITATIONS {
        int id PK
        int organization_id FK
        string email
        string role
        string token_hash
        datetime expires_at
        datetime accepted_at
    }

    USERS ||--o{ ORGANIZATION_MEMBERSHIPS : joins
    ORGANIZATIONS ||--o{ ORGANIZATION_MEMBERSHIPS : has
    ORGANIZATIONS ||--o{ WORKSPACES : owns
    WORKSPACES ||--o{ PROJECTS : contains
    PROJECTS ||--|| PROJECT_CALENDARS : has
    PROJECTS ||--o{ TASKS : contains
    PROJECTS ||--o{ DEPENDENCIES : contains
    TASKS ||--o{ TASKS : parent
    TASKS ||--o{ DEPENDENCIES : predecessor
    TASKS ||--o{ DEPENDENCIES : successor
    PROJECTS ||--o{ RESOURCES : contains
    PROJECTS ||--o{ ASSIGNMENTS : contains
    RESOURCES ||--o{ ASSIGNMENTS : allocated
    TASKS ||--o{ ASSIGNMENTS : receives
    USERS ||--o{ NOTIFICATIONS : receives
    ORGANIZATIONS ||--o{ WORKSPACE_INVITATIONS : issues
```

There are no workspace membership records. Organization membership is the only tenant boundary. Analysis runs and audit events are not implemented; risk simulations are computed on demand and return their inputs.

---

## 10. Dormant and unintegrated code

Only the analytics prototype remains dormant:

| File | Status | Why it is not active |
| --- | --- | --- |
| `backend/app/api/analytics.py` | Dormant | Imports missing `app.get_db`; not registered in `backend/app/api/__init__.py`; assumes the earlier raw-SQLite schema and weekday/8-hour calendar model; has no tests. |

The old `organizations.py`, `workspaces.py`, `projects.py`, and `tasks.py` prototypes were replaced by the active M2/M3 blueprints. They are no longer dormant evidence of missing tenancy/planning.

Use this language in the report:

> The planning, tenancy, CPM, resource, risk, export, and collaboration modules are active and tested. An older analytics prototype remains in the repository but is not registered, migrated, or tested, so it should not be used as evidence of a different analytics implementation.

Resource analysis, leveling, risk simulation, ICS export, and read-only Gantt visualization are active. `backend/Dockerfile` and `docs/deployment.md` describe the current Flask-Migrate/SQLite deployment path; no production deployment or restore drill has been recorded.

## 11. Implemented and future data model

| Entity | Purpose | Status |
| --- | --- | --- |
| `users` | Global identity and password hash. | Implemented. |
| `organizations` | Top-level tenant. | Implemented. |
| `organization_memberships` | User role within an organization; composite primary key. | Implemented. |
| `workspaces` | Organization-owned grouping of projects; case-insensitive unique name per organization. | Implemented. |
| `workspace_memberships` | Optional finer-grained access. | Not used; organization membership is the boundary. |
| `projects` | Workspace-owned plan with status, version, dates, and creator. | Implemented. |
| `project_calendars` | One calendar per project with JSON weekly rules and exceptions. | Implemented; editable in M4. |
| `tasks` | Project work item with hierarchy, status, duration, progress, priority, constraints, and PERT estimates. | Implemented. |
| `dependencies` | Directed task link with FS/SS/FF/SF type and working-minute lag. | Implemented. |
| `resources` | Project-scoped capacity. | Implemented in M6. |
| `assignments` | Resource allocation to tasks. | Implemented in M6. |
| `notifications` | Per-user in-app notification with read state. | Implemented with collaboration. |
| `workspace_invitations` | Hashed, expiring organization invitation. | Implemented with collaboration. |
| `analysis_runs` | Reproducible record of analytics/simulation inputs and results. | Not implemented; simulations are on demand. |
| `audit_events` | Lightweight record of important changes. | Not implemented. |

Implemented conventions:

- Integer primary keys and foreign keys; cascade deletes from organization to workspace to project to task/dependency.
- Composite unique membership pair; case-insensitive unique workspace and project names at their scopes.
- ISO 8601 audit timestamps in UTC and `YYYY-MM-DD` calendar dates.
- Foreign-key enforcement on every SQLite connection.
- Project version checks for project edits; task/dependency/calendar mutations increment the version.
- Stored planning inputs are separate from derived CPM results; M4 schedules are calculated on demand and not persisted. Future analysis runs store their own input snapshots and results.

## 12. Remaining modules in detail

M2 and M3 are now implemented prerequisites. The sections below describe what remains, what evidence is missing, and what the report can say about it.

### 12.1 Completed prerequisites: M2 and M3

**M2 - Organization/workspace access control** is implemented with:

- `organizations`, `organization_memberships`, and `workspaces` models and migration `6f1a2b3c4d5e_add_tenancy.py`.
- Roles `owner`, `admin`, `editor`, and `viewer`; only organization membership is used.
- Organization, member, and workspace APIs with role checks; `404` for non-members and `403` for insufficient roles.
- Last-owner protection (`409 last_owner`) and owner-only organization deletion.
- Frontend organization, member, and workspace controls.

**M3 - Core planning** is implemented with:

- `projects`, `project_calendars`, `tasks`, and `dependencies` models and migration `7a2b3c4d5e6f_add_planning.py`.
- Project CRUD with optimistic versioning; task hierarchy, status, duration, progress, priority, constraints, and PERT inputs; dependency CRUD for FS/SS/FF/SF with lag.
- Validation for self-links, duplicates, cross-project links, hierarchy cycles, and dependency cycles.
- One default UTC calendar per project (Monday-Friday 09:00-17:00).
- Frontend planning workspace for projects, tasks, dependencies, and role-aware controls.

M3 deliberately excluded calendar editing, schedule calculation, Gantt display, resources, and assignments. M4 adds calendar editing and CPM calculation; M5 adds a read-only Gantt display.

### 12.2 M4–M5 — Scheduling and Gantt

**Goal:** calculate and display a dependency-aware schedule.

**M4 - Calendar editing and CPM scheduling: implemented**
- Timezone-aware working-calendar arithmetic for working minutes, multiple daily intervals, holidays, and working/nonworking exceptions.
- Calendar validation for IANA timezones, all seven day keys, `HH:MM` values, positive intervals, non-overlap, and unique exception dates.
- `PATCH /projects/<id>/calendar` with project-version checks and editor/admin/owner permission.
- Four dependency types with working-minute lag: FS, SS, FF, SF.
- Topological cycle rejection and readable `422` errors for infeasible hard constraints.
- Forward/backward passes, earliest/latest dates, project finish, total float, free float, and critical path.
- All seven task constraint types, zero-duration milestones, target-finish advisories, and default/adjusted project-start warnings.
- `GET /projects/<id>/schedule`; derived dates are calculated on demand and are not persisted.
- Backend tests for calendar boundaries, DST, dependency types, constraints, float, target deadlines, infeasibility, API permissions, and stale versions.
- React calendar editor and schedule summary with task dates, float, critical flags, and warnings.

**M5 - Gantt visualization: implemented**
- Custom read-only SVG timeline with task bars, dependency links, milestones, critical-path emphasis, float bars, weekend shading, and a date header.
- Role-aware workspace integration; no new charting dependency. Drag/resize editing remains outside the first read-only version.

**Acceptance criteria**
- Hand-calculated scenarios produce expected dates, critical path, and float. Met for M4 engine tests.
- Cycles and cross-project links are rejected. Met in M3/M4.
- Finish-event semantics and exclusive boundaries are applied consistently. Met in M4 API serialization tests.
- A project with no imposed deadline uses the latest task finish; a target finish/deadline is visible when used. Met in M4.
- Gantt bars and dependency links match the schedule response. Met in M5 component tests.

### 12.3 M6 — Resource analytics and leveling preview

**Goal:** identify resource overload and propose explainable leveling adjustments.

**Required work**
- Resource and assignment models/migrations.
- Working-interval or daily load profiles per resource.
- Overload results with resource, interval, assigned load, capacity, and contributing tasks.
- Leveling preview that preserves dependencies and fixed dates, prioritizes lower-priority tasks, then tasks with more float, then stable task ID.
- User-facing acceptance/rejection of proposals.
- Tests for aggregation and preview behavior.

**Acceptance criteria**
- Overload results identify contributing tasks.
- Proposals respect dependencies when feasible.
- The preview is presented as a heuristic, not an optimal solver.

**Current state:** implemented. `backend/app/models/planning.py` defines resources and assignments; `backend/app/services/resources.py` provides CRUD, workload aggregation, overloads, and a leveling preview; `backend/app/api/resources.py` exposes the endpoints. The preview may extend the project finish only while staying within `target_finish`. `frontend/src/components/ResourceWorkloadPanel.tsx` provides the UI. Tests are in `backend/tests/test_resources.py` and `frontend/src/components/ResourceWorkloadPanel.test.tsx`.

### 12.4 M7 — Risk simulation

**Goal:** estimate deadline confidence with explicit uncertainty.

**Required work**
- PERT inputs: optimistic (`a`), most-likely (`m`), pessimistic (`b`).
- Beta-PERT sampling; deterministic tasks remain fixed.
- Seeded Monte Carlo runs with configurable iterations and target deadline.
- Saved analysis runs keyed to project version and parameters.
- Median/percentile finish dates and deadline-hit probability.
- Reproducibility tests for fixed seeds.

**Acceptance criteria**
- Fixed-seed runs are reproducible.
- Deterministic tasks produce deterministic dates.
- Results expose assumptions and are labelled as planning estimates, not guarantees.

**Current state:** implemented. `backend/app/services/risk.py` performs seeded beta-PERT Monte Carlo synchronously (default 2,000 iterations, range 100-10,000), with deterministic fallback for missing or unordered estimates. `POST /projects/<id>/risk-simulation` is exposed by `backend/app/api/risk.py`; `frontend/src/components/RiskSimulationPanel.tsx` displays percentiles, target probability, and critical frequency. Saved analysis runs are not implemented; the response carries the seed and assumptions for reproducibility. Tests are in `backend/tests/test_risk.py` and `frontend/src/components/RiskSimulationPanel.test.tsx`.

### 12.5 M8 — ICS export

**Goal:** export selected project events to a calendar application.

**Required work**
- ICS generation for selected project dates/events.
- Download endpoint and frontend action.
- Timezone/date-boundary handling consistent with scheduling conventions.
- Verification by importing the generated file into a calendar application.

**Acceptance criteria**
- Exported ICS imports successfully.
- Dates and event boundaries match the displayed schedule.
- Access control is enforced on export.

**Current state:** implemented. `backend/app/services/export.py` builds all-day VEVENTs with CRLF line endings and escaped text; `GET /projects/<id>/export.ics` in `backend/app/api/exports.py` enforces project access and sets a project-named attachment. The workspace exposes an Export ICS link. Tests are in `backend/tests/test_export.py`. Import into a desktop calendar application was not recorded.

### 12.6 Collaboration and account tools

**Goal:** let administrators bring members in and give users visibility and control over their data.

**Current state:** implemented. Admin/owner users create expiring invitation tokens; the token is hashed at rest and acceptance is restricted to the invited email address. Development responses include the token, while production relies on SMTP configuration. Notifications record invitation acceptance and task creation for other organization members; users can mark one or all as read. `GET /account/export` returns the user's organizations, projects, tasks, dependencies, resources, assignments, and notifications. `DELETE /account` requires the password, transfers owner roles or deletes a sole-member organization, and clears the user's notifications. Tests are in `backend/tests/test_collaboration.py`; UI tests cover invitations, notifications, and account controls.

### 12.7 Phase 8 — Evaluation and final report

**Goal:** produce measured evidence and an academic evaluation.

**Required work**
- Demo data and scenario definitions (parallel paths, shared resources, holidays, milestones, imposed deadline).
- Performance measurements near 1,000 tasks, including hardware, input shape, and run count.
- Unit/API/frontend checks for scheduling, validation, permissions, recalculation, and reproducibility.
- Small user evaluation of creating a plan, adding dependencies, finding critical work, resolving overload, and interpreting deadline confidence.
- Documented limitations, assumptions, and measured results.

**Current state:** automated evaluation is documented in [evaluation.md](evaluation.md). The suite covers M0-M8, the full migration chain was verified up/down/up, and `backend/scripts/benchmark.py` records 1,000-task schedule and risk timings. A small human user evaluation has not been conducted, and the benchmark is synthetic.

---

## 13. Known limitations and inconsistencies

### 13.1 Accuracy cautions for the report

- **Implemented through M8:** M0-M8 and the collaboration/account features are active and tested. Do not describe them as planned.
- **Dormant analytics only:** `backend/app/api/analytics.py` is the remaining unintegrated prototype. Do not count it as scheduling or analytics delivery; active CPM scheduling lives in `backend/app/scheduling/` and active resource/risk code lives in `backend/app/services/`.
- **Schedule calculation and read-only Gantt exist:** M4 computes dependency-aware dates, constraints, float, and critical path; M5 renders that schedule as a custom SVG Gantt.
- **Resources and risk exist:** M6 adds capacity, assignments, workload, and leveling; M7 adds synchronous seeded simulation. Neither is persisted as a saved analysis run.
- **Calendar is editable:** editor/admin/owner users can change timezone, weekly working hours, and exceptions through the API and basic frontend editor. The frontend editor exposes one interval per day, while the API accepts multiple.
- **SQLite only:** no PostgreSQL or other database support is implemented.
- **Deployment is documented but unexercised:** `docs/deployment.md` and `backend/Dockerfile` describe the current Gunicorn/SQLite/Alembic path; no production deployment or restore drill has been recorded.
- **Benchmark results exist but are synthetic:** the 1,000-task schedule and risk measurements are recorded in `docs/evaluation.md`; they are not a controlled experiment.

### 13.2 Technical debt and risks

- Only `analytics.py` remains from the older architecture; it should be deleted after confirming nothing depends on it.
- The project calendar is created lazily if missing, so calendar code must preserve the one-calendar-per-project invariant.
- Project version checks protect project edits; task, dependency, and calendar edits increment the version but task/dependency edits do not require a client-supplied version. Future schedule-affecting edits may need a stronger concurrency policy.
- `pytest-flask` shares one application context and caches `g._login_user`; multi-user tests must switch users through one client (logout/login) rather than holding simultaneous clients.
- Calendar arithmetic, CPM, resource, and risk code remain independent of Flask request state; route/service code handles authorization, versions, and error conversion.
- Risk simulation is synchronous and recalculates the full schedule per iteration; it took about 36 seconds for 1,000 tasks and 2,000 iterations. Background execution or lower iteration counts would be needed for stricter response targets.
- Invitation email delivery depends on SMTP in production; without it the invitation is saved and the API returns `503 email_delivery_failed`.
- The basic calendar editor collapses multiple intervals per day to one; the API retains multiple-interval support.

### 13.3 Resolved and open decisions

Resolved:

- Organization membership is sufficient for access; workspace membership is not used.
- Roles are `owner`, `admin`, `editor`, and `viewer`.
- Projects start with a UTC Monday-Friday 09:00-17:00 calendar; M4 supports editable timezones, weekly rules, and exceptions.
- Schedules, workloads, leveling previews, and risk simulations are computed on demand and not persisted; risk responses include the seed and assumptions needed to reproduce a run.
- The M5 Gantt uses custom SVG with no new charting dependency and is read-only in its first version.
- Resources and assignments are project-scoped and use an explainable heuristic preview, not an optimal solver.
- Supported task constraints are `none`, start/finish no-earlier/no-later, and must-start/must-finish; M4 enforces them during scheduling.
- Collaboration uses invitation tokens and in-app notifications; there is no live co-editing or email verification.

Open:

- Which drag/resize Gantt interactions fit the academic evaluation after the read-only M5 timeline?

## 14. Suggested report outline

The following structure maps directly to the evidence in this repository.

| Chapter | Suggested content | Primary evidence |
| --- | --- | --- |
| 1. Introduction | Background, problem statement, target users, academic objectives. | `README.md`, `plan.md` |
| 2. Requirements and scope | Functional requirements, non-goals, roles, workflows, acceptance criteria. | `plan.md`, `docs/architecture.md` |
| 3. System design | Modular monolith, architecture diagram, request lifecycle, data model, API conventions, security model. | `docs/architecture.md`, `docs/api-conventions.md`, this brief |
| 4. Implemented modules | M0 foundation, M1 identity, M2 tenancy, M3 planning, M4 scheduling, M5 Gantt, M6 resources, M7 risk, M8 export, and collaboration. | `backend/app/`, `frontend/src/`, this brief |
| 5. Testing and verification | Test strategy, 108 backend tests, 64 frontend tests, CI pipeline, migration cycle, manual test path. | `backend/tests/`, `frontend/src/**/*.test.*`, `.github/workflows/ci.yml` |
| 6. Collaboration and integration | Invitations, notifications, ICS export, and account controls. | `backend/app/api/collaboration.py`, `backend/app/api/accounts.py`, `frontend/src/components/` |
| 7. Limitations and risks | Dormant analytics, SQLite-only scope, synchronous simulation, unexercised deployment, no user study. | This brief, `docs/evaluation.md` |
| 8. Evaluation | Scenarios, performance measurement, reproducibility, and missing user evaluation. | `docs/evaluation.md`, `backend/scripts/benchmark.py` |
| 9. Conclusion | What was achieved, what remains, lessons learned, next steps. | All of the above |
| 10. References/appendix | Repository links, file index, glossary, API examples. | This brief |

### Suggested figures and tables

- Architecture diagram (Section 6.1).
- Login/CSRF sequence diagram (Section 8.4).
- Actual ER diagram (Section 9.2).
- Implemented/future data model table (Section 11).
- Implementation status table (Section 5).
- Authentication endpoint table (Section 8.3) and actual API surface (Section 9.1).
- Test evidence table (Section 15).
- Module status matrix (Section 5) and remaining-module details (Section 12).

### Suggested claims and evidence

| Claim | Evidence | Caveat |
| --- | --- | --- |
| The backend uses a Flask application factory and SQLAlchemy/Alembic. | `backend/app/__init__.py`, `backend/app/extensions.py`, `backend/migrations/` | Active. |
| Authentication supports login/logout/current-user with cookie sessions and CSRF. | `backend/app/api/auth.py`, `backend/tests/test_auth.py`, `backend/tests/test_csrf_auth.py` | Active. |
| The frontend supports sign-in, session restore, and sign-out. | `frontend/src/App.tsx`, `frontend/src/auth/AuthContext.tsx`, `frontend/src/pages/LoginPage.tsx`, frontend tests | Active. |
| Organizations, roles, members, and workspaces are enforced by the API. | `backend/app/models/tenancy.py`, `backend/app/services/tenancy.py`, `backend/app/api/organizations.py`, `backend/tests/test_tenancy.py` | Active M2. |
| Projects, tasks, dependencies, and editable calendars are supported. | `backend/app/models/planning.py`, `backend/app/services/planning.py`, `backend/tests/test_planning.py`, frontend workspace tests | Active M3/M4. |
| Dependency-aware CPM scheduling, constraints, float, and critical path are supported. | `backend/app/scheduling/`, `backend/app/services/scheduling.py`, `backend/app/api/schedules.py`, `backend/tests/test_calendar.py`, `backend/tests/test_cpm.py`, `backend/tests/test_schedule.py` | Active M4; schedules are computed on demand. |
| The frontend provides a role-aware planning workspace with calendar, schedule, Gantt, resource, risk, collaboration, and account controls. | `frontend/src/pages/WorkspacePage.tsx`, `frontend/src/components/`, frontend tests | Active. |
| The project supports read-only Gantt visualization of the computed schedule. | `frontend/src/components/GanttChart.tsx`, `frontend/src/components/GanttChart.test.tsx` | Active M5; drag/resize editing is not implemented. |
| The project supports resource workloads, leveling previews, seeded risk simulation, and ICS export. | `backend/app/services/resources.py`, `backend/app/services/risk.py`, `backend/app/services/export.py`, matching API modules and tests | Active M6-M8; previews and simulations are on demand. |
| The project supports invitations, notifications, and account export/deletion. | `backend/app/services/collaboration.py`, `backend/app/services/account.py`, `backend/tests/test_collaboration.py` | Active; no email verification or password reset. |
| CI verifies migrations, seeding, backend tests, frontend tests, and frontend build. | `.github/workflows/ci.yml` | Active for M0-M8. |

---

## 15. Test and verification evidence

### 15.1 Backend

- Command from `backend/`: `..\.venv\Scripts\python.exe -m pytest -q` (or `pytest` with the virtual environment active).
- Result at the snapshot: **108 passed, 1 third-party deprecation warning**.
- Test modules: `test_auth.py`, `test_calendar.py`, `test_collaboration.py`, `test_config.py`, `test_cpm.py`, `test_csrf_auth.py`, `test_csrf_tenancy.py`, `test_db.py`, `test_errors.py`, `test_export.py`, `test_health.py`, `test_planning.py`, `test_request_context.py`, `test_resources.py`, `test_risk.py`, `test_schedule.py`, `test_seed.py`, `test_tenancy.py`.
- Fixtures: `backend/tests/conftest.py` creates an isolated temporary SQLite database per app and drops it after the test.
- CI also runs migrations up, down to base, and up again, then runs `seed-demo`.
- The full migration chain was verified locally up, down to base, and up again through collaboration revision `9c3d5e7f8a9b`.

### 15.2 Frontend

- Command: `npm test` from `frontend/`.
- Result at the snapshot: **64 passed** across 11 test files.
- Test files: `App.test.tsx`, `auth/AuthContext.test.tsx`, `pages/LoginPage.test.tsx`, `pages/WorkspacePage.test.tsx`, `components/GanttChart.test.tsx`, `components/ResourceWorkloadPanel.test.tsx`, `components/RiskSimulationPanel.test.tsx`, `components/InvitationPanel.test.tsx`, `components/NotificationPanel.test.tsx`, `components/AccountPanel.test.tsx`, `lib/api.test.ts`.
- Build: `npm run build` runs `tsc --noEmit && vite build`; verified successfully.
- Workspace tests cover initial loading, organization/project/task/dependency creation, calendar updates, schedule rendering, Gantt rendering, resource/risk/invitation/notification/account controls, API errors, and viewer read-only controls.

### 15.3 Manual verification path

1. From `backend/`: `flask db upgrade`, `flask seed-demo`, `flask run --debug`.
2. From `frontend/`: `npm ci`, `npm run dev`.
3. Open the Vite URL, verify the health status, and sign in with `owner@demo.local` / `DemoPulse123!`.
4. Confirm the demo organization, workspace, project, tasks, and dependencies load; create and edit a task or dependency; reload to confirm session restore.
5. Create a resource and assignment, inspect workload and a leveling preview, run a seeded risk simulation, and download the ICS file.
6. Sign out and sign in as `viewer@demo.local` to confirm planning controls are read-only.
7. Check `http://127.0.0.1:5000/api/v1/health` returns `database: "ok"`.

## 16. Evidence index

| Evidence | What it demonstrates |
| --- | --- |
| [backend/app/__init__.py](../backend/app/__init__.py) | App factory, extension initialization, blueprint/CLI/error/request-context registration. |
| [backend/app/config.py](../backend/app/config.py) | Environment-based configuration and production checks. |
| [backend/app/extensions.py](../backend/app/extensions.py) | SQLAlchemy, Alembic, Flask-Login, CSRF, SQLite pragmas. |
| [backend/app/errors.py](../backend/app/errors.py) | JSON error envelope and handlers. |
| [backend/app/request_context.py](../backend/app/request_context.py) | Request IDs, timing, and access logging. |
| [backend/app/api/auth.py](../backend/app/api/auth.py) | Active authentication endpoints. |
| [backend/app/api/health.py](../backend/app/api/health.py) | Database-aware health endpoint. |
| [backend/app/api/organizations.py](../backend/app/api/organizations.py) | Organization and member endpoints. |
| [backend/app/api/workspaces.py](../backend/app/api/workspaces.py) | Workspace endpoints. |
| [backend/app/api/projects.py](../backend/app/api/projects.py) | Project and calendar endpoints. |
| [backend/app/api/tasks.py](../backend/app/api/tasks.py) | Task endpoints. |
| [backend/app/api/dependencies.py](../backend/app/api/dependencies.py) | Dependency endpoints. |
| [backend/app/api/schedules.py](../backend/app/api/schedules.py) | On-demand project schedule endpoint. |
| [backend/app/api/resources.py](../backend/app/api/resources.py) | Resource, assignment, workload, and leveling endpoints. |
| [backend/app/api/risk.py](../backend/app/api/risk.py) | Seeded risk-simulation endpoint. |
| [backend/app/api/exports.py](../backend/app/api/exports.py) | Authenticated ICS export endpoint. |
| [backend/app/api/collaboration.py](../backend/app/api/collaboration.py) | Notification and invitation endpoints. |
| [backend/app/api/accounts.py](../backend/app/api/accounts.py) | Account export and deletion endpoints. |
| [backend/app/api/__init__.py](../backend/app/api/__init__.py) | Registered blueprints; excludes dormant analytics. |
| [backend/app/models/user.py](../backend/app/models/user.py) | User model. |
| [backend/app/models/tenancy.py](../backend/app/models/tenancy.py) | Organization, membership, and workspace models. |
| [backend/app/models/planning.py](../backend/app/models/planning.py) | Project, calendar, task, dependency, resource, and assignment models. |
| [backend/app/models/collaboration.py](../backend/app/models/collaboration.py) | Notification and workspace-invitation models. |
| [backend/app/services/identity.py](../backend/app/services/identity.py) | Password, email, authentication, and demo-user seeding. |
| [backend/app/services/tenancy.py](../backend/app/services/tenancy.py) | Access checks, tenancy CRUD, and role rules. |
| [backend/app/services/planning.py](../backend/app/services/planning.py) | Planning validation, CRUD, versioning, and graph checks. |
| [backend/app/services/scheduling.py](../backend/app/services/scheduling.py) | Calendar updates and schedule-response assembly. |
| [backend/app/services/resources.py](../backend/app/services/resources.py) | Resource CRUD, workload, overloads, and leveling preview. |
| [backend/app/services/risk.py](../backend/app/services/risk.py) | Seeded PERT/Monte Carlo simulation. |
| [backend/app/services/export.py](../backend/app/services/export.py) | ICS generation and escaping. |
| [backend/app/services/collaboration.py](../backend/app/services/collaboration.py) | Invitations and notifications. |
| [backend/app/services/account.py](../backend/app/services/account.py) | Account export and deletion. |
| [backend/scripts/benchmark.py](../backend/scripts/benchmark.py) | Reproducible 1,000-task performance benchmark. |
| [backend/app/scheduling/calendar.py](../backend/app/scheduling/calendar.py) | Timezone-aware working calendar and exception handling. |
| [backend/app/scheduling/cpm.py](../backend/app/scheduling/cpm.py) | CPM forward/backward passes, constraints, floats, and critical path. |
| [backend/app/scheduling/graph.py](../backend/app/scheduling/graph.py) | Dependency topology and cycle validation. |
| [backend/app/services/demo.py](../backend/app/services/demo.py) | Idempotent demo tenant seeding. |
| [backend/migrations/versions/](../backend/migrations/versions/) | Alembic baseline, users, tenancy, planning, resources, and collaboration revisions. |
| [backend/tests/](../backend/tests/) | Backend test evidence for M0-M8. |
| [frontend/src/App.tsx](../frontend/src/App.tsx) | Session/health/login shell and workspace rendering. |
| [frontend/src/auth/AuthContext.tsx](../frontend/src/auth/AuthContext.tsx) | Client session state and login/logout operations. |
| [frontend/src/lib/api.ts](../frontend/src/lib/api.ts) | CSRF-aware API client, planning types, and schedule/calendar calls. |
| [frontend/src/pages/LoginPage.tsx](../frontend/src/pages/LoginPage.tsx) | Sign-in form and error display. |
| [frontend/src/pages/WorkspacePage.tsx](../frontend/src/pages/WorkspacePage.tsx) | Role-aware planning workspace plus Gantt, resource, risk, invitation, notification, and account panels. |
| [frontend/src/components/](../frontend/src/components/) | Gantt, resource, risk, invitation, notification, and account components with tests. |
| [frontend/src/](../frontend/src/) | Frontend tests and test setup. |
| [.github/workflows/ci.yml](../.github/workflows/ci.yml) | CI commands and quality gates. |
| [docs/api-conventions.md](api-conventions.md) | API/error/CSRF/authorization conventions. |
| [docs/architecture.md](architecture.md) | Architecture, tenancy boundary, and module status. |
| [docs/scheduling-assumptions.md](scheduling-assumptions.md) | Scheduling and analytics conventions and decisions. |
| [docs/evaluation.md](evaluation.md) | Test counts, migration cycle, benchmark results, scenarios, and limits. |
| [plan.md](../plan.md) | Full product scope, phases, and current status. |
| [README.md](../README.md) | Setup, demo tenant, tests, and current status. |

## 17. Glossary

| Term | Meaning |
| --- | --- |
| Alembic | Database migration tool used through Flask-Migrate. |
| CPM | Critical Path Method; computes earliest/latest dates and float. |
| CSRF | Cross-Site Request Forgery; state-changing requests require a token. |
| DAG | Directed acyclic graph; required for valid task dependencies. |
| FS/SS/FF/SF | Finish-to-start, start-to-start, finish-to-finish, start-to-finish dependency types. |
| Float | Slack time before a task affects the project finish or a successor. |
| ICS | iCalendar file format used to export events. |
| M0, M1, … | Implementation milestones used by the project plan. |
| PERT | Three-point estimate with optimistic, most-likely, and pessimistic durations. |
| SQLAlchemy | Python ORM used for the active data model. |
| Tenancy | Isolation between organizations and their data. |
| Total float | Working-time distance between earliest and latest start; zero means critical. |

---

## 18. Final checklist for the report author

- [ ] State that M0-M8 and the collaboration/account features are implemented.
- [ ] State that automated evaluation and benchmarks exist, but no human user evaluation was conducted.
- [ ] State that the M5 Gantt is read-only; drag/resize editing is not implemented.
- [ ] Explain that only `analytics.py` remains dormant; organization/workspace/project/task/resource modules are active.
- [ ] Include the actual API table and the target-model outline separately.
- [ ] Include the implemented ER model and future entities separately.
- [ ] Include the 108 backend / 64 frontend test results, migration cycle, and CI pipeline.
- [ ] Include the benchmark hardware, workload shape, timing, and synchronous-simulation limitation.
- [ ] Include limitations, resolved/open decisions, and future work.
- [ ] Use the suggested outline and figures, adapting them to the course requirements.
- [ ] Cite the repository snapshot and the M9 evaluation document.
