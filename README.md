# ProjectPulse

ProjectPulse is a local, browser-based project planning and analytics application for an academic project. It is designed for organizations that manage shared workspaces and project plans. The initial performance target is about 1,000 tasks per project; live co-editing is outside the first release.

## What we are building

The app combines a React + TypeScript frontend, a Flask JSON API, and a SQLite database in one modular monolith. Implemented features are:

- Organizations, users, roles, workspaces, and shared projects.
- Task and milestone management with dependencies and calendars.
- Read-only Gantt visualization and dependency-aware schedule recalculation.
- Critical path, total float, and free float analysis.
- Resource load and overload detection, plus an explainable leveling preview.
- PERT/Monte Carlo deadline confidence estimates with reproducible seeds.
- ICS calendar export.
- Invitation-based organization membership, in-app notifications, and account data export/deletion.

The detailed product scope, data model, rules, phases, and evaluation plan are in [plan.md](plan.md). Scheduling conventions are recorded in [docs/scheduling-assumptions.md](docs/scheduling-assumptions.md), module design is in [docs/architecture.md](docs/architecture.md), API conventions are in [docs/api-conventions.md](docs/api-conventions.md), and test/benchmark evidence is in [docs/evaluation.md](docs/evaluation.md).

## Current status

Milestones M0-M8 are complete, and the M9 evaluation assets are in place. The backend provides environment-based configuration, SQLAlchemy models with Alembic migrations, session/CSRF protection, a consistent JSON error envelope, request IDs, a database-aware health check, seeded demo accounts, cookie-session authentication, organization membership and role enforcement, workspace/project/task/dependency/resource CRUD, invitations and notifications, deterministic demo seeding, editable project calendars, an on-demand FS/SS/FF/SF schedule endpoint with constraints, float, and critical path, resource workload and leveling previews, seeded risk simulation, ICS export, and account export/deletion. The frontend provides sign-in, a state-based planning workspace with role-aware organization, member, workspace, project, task, dependency, calendar, schedule, Gantt, resource, risk, invitation, notification, and account controls.

The risk simulation runs synchronously. With 1,000 tasks and the default 2,000 iterations, the benchmark takes about 35 seconds on the recorded machine; see [docs/evaluation.md](docs/evaluation.md). A small user evaluation has not been conducted.

For a detailed implementation-status brief intended for report writing, including unimplemented modules and dormant code, see [docs/project-report-brief.md](docs/project-report-brief.md).

## Requirements

- Python 3.11 or newer.
- Node.js and npm (use the current supported LTS release for development).
- The packages listed in `requirements.txt` for the backend, analysis, export, and development checks.
- Frontend packages listed in `frontend/package.json`.

`requirements.txt` is the single source of dependency versions. `backend/pyproject.toml` holds tooling configuration only.

## Run locally on Windows PowerShell

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` if needed, then initialize the database and start the Flask API from `backend`:

```powershell
Set-Location backend
flask db upgrade
flask seed-demo
flask run --debug
```

`flask seed-demo` is idempotent. It creates three demo accounts plus a demo organization, workspace, project, three tasks, and two finish-to-start dependencies. It prints how many users were created or skipped, then summarizes the demo tenant. The development defaults are:

| Email | Role in the demo organization |
| --- | --- |
| `owner@demo.local` | owner |
| `editor@demo.local` | editor |
| `viewer@demo.local` | viewer |

The demo password is `DemoPulse123!` unless `DEMO_PASSWORD` is set. The command refuses to run in production unless `--force` is passed.

The health endpoint is [http://127.0.0.1:5000/api/v1/health](http://127.0.0.1:5000/api/v1/health). It returns `database: "ok"` when the API can reach SQLite.

In a second terminal, install and start the frontend:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open the local URL printed by Vite. Vite forwards `/api` requests to the Flask development server on port 5000.

## Configuration and data

Configuration comes from `backend/.flaskenv` (Flask app selection) and the root `.env` file (secrets and environment).

| Variable | Purpose | Default |
| --- | --- | --- |
| `SECRET_KEY` | Flask session signing key | development fallback |
| `DATABASE_URL` | SQLAlchemy database URI | `sqlite:///projectpulse.sqlite3` |
| `APP_ENV` | `development`, `testing`, or `production` | `development` |
| `ALLOW_PUBLIC_SIGNUP` | Enables public registration when true | `false` |
| `DEMO_PASSWORD` | Password assigned by `flask seed-demo` | `DemoPulse123!` |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` | `INFO` |
| `PUBLIC_URL` | Browser origin used in invitation links | `http://localhost:5173` |
| `MAIL_HOST`, `MAIL_PORT` | SMTP host and port | unset, `587` |
| `MAIL_FROM`, `MAIL_USERNAME`, `MAIL_PASSWORD` | SMTP sender and credentials | unset |
| `MAIL_USE_TLS` | Start SMTP TLS | `true` |

A relative SQLite path resolves under `backend/instance/`. Without `MAIL_HOST` and `MAIL_FROM`, development logs invitation emails to the Flask log instead of sending them. Production invitation delivery requires SMTP configuration. Do not commit `.env`, database files, password hashes from real accounts, or production secrets. The Flask development server is for local development only.

## Database migrations

Schema changes are managed with Flask-Migrate/Alembic. Run all commands from `backend` with the virtual environment active:

```powershell
flask db upgrade          # apply migrations
flask db revision -m "..."  # create an empty revision
flask db migrate -m "..."   # autogenerate from model changes (review it)
flask db downgrade        # step back one revision
```

Review autogenerated migrations before committing them. SQLite is configured with batch mode for `ALTER` operations.

## Tests

Backend tests use an isolated temporary SQLite database and never touch `backend/instance/`:

```powershell
Set-Location backend
pytest
```

Frontend tests use Vitest, jsdom, and React Testing Library; they run without a backend:

```powershell
Set-Location frontend
npm test
npm run test:coverage
npm run build
```

CI runs both suites, applies migrations against a fresh database to catch model/migration drift, and runs `flask seed-demo` to exercise the idempotent demo tenant.

The M9 evaluation benchmark is reproducible from `backend`:

```powershell
..\.venv\Scripts\python.exe -m scripts.benchmark --runs 5 --iterations 2000
```

## Development notes

- Keep scheduling and analytics logic independent of Flask request state.
- Use SQLAlchemy transactions for related writes and check project versions for stale edits.
- Enforce organization membership and role rules on every workspace, project, task, and dependency read or mutation.
- Keep schedule inputs separate from derived dates.
- Document any change to date, calendar, dependency, or simulation assumptions.
- Build features in the order and acceptance criteria in `plan.md`.
