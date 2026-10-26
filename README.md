# ProjectPulse

ProjectPulse is a local, browser-based project planning and analytics application for an academic project. It is designed for organizations that manage shared workspaces and project plans. The initial performance target is about 1,000 tasks per project; live co-editing is outside the first release.

## What we are building

The app combines a React + TypeScript frontend, a Flask JSON API, and a SQLite database in one modular monolith. The planned features are:

- Organizations, users, roles, workspaces, and shared projects.
- Task and milestone management with dependencies and calendars.
- Interactive Gantt planning and dependency-aware schedule recalculation.
- Critical path, total float, and free float analysis.
- Resource load and overload detection, plus an explainable leveling preview.
- PERT/Monte Carlo deadline confidence estimates with reproducible seeds.
- ICS calendar export.

The detailed product scope, data model, rules, phases, and evaluation plan are in [plan.md](plan.md). Scheduling conventions are also recorded in [docs/scheduling-assumptions.md](docs/scheduling-assumptions.md), and the module design is in [docs/architecture.md](docs/architecture.md).

## Current status

The Flask API, SQLite database, and React interface are in place. Review [deployment guidance](docs/deployment.md) before production use.

## Requirements

- Python 3.11 or newer.
- Node.js and npm (use the current supported LTS release for development).
- The packages listed in `requirements.txt` for the backend, analysis, export, and development checks.
- Frontend packages listed in `frontend/package.json`.

## Run locally on Windows PowerShell

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Start the Flask API from `backend` in that activated environment:

```powershell
Set-Location backend
flask --app wsgi db upgrade
flask --app wsgi run --debug
```

The health endpoint is [http://127.0.0.1:5000/api/v1/health](http://127.0.0.1:5000/api/v1/health).

In a second terminal, install and start the frontend:

```powershell
Set-Location "D:\Project Pulse\frontend"
npm install
npm run dev
```

Open the local URL printed by Vite. Vite forwards `/api` requests to the Flask development server on port 5000.

## Configuration and data

The SQLite database is stored under `backend/instance/` during local development. Do not commit database files, password hashes from real accounts, environment files, or production secrets. Production runs with `docker compose` and requires a unique `PROJECTPULSE_SECRET_KEY`, `APP_DOMAIN`, and an encrypted persistent `BACKUP_PATH`; the stack configures allowed origins and secure cookies. See [docs/deployment.md](docs/deployment.md). The Flask development server is for local development only.

## Development notes

- Keep scheduling and analytics logic independent of Flask request state.
- Use transactions for related writes and check project versions for stale edits.
- Enforce tenant membership on every project read and mutation.
- Keep schedule inputs separate from derived dates.
- Document any change to date, calendar, dependency, or simulation assumptions.
- Build features in the order and acceptance criteria in `plan.md`.
## Account, privacy, and team controls

Accounts require email verification. Password recovery links and team invitations are sent through the SMTP settings in `.env`. Configure a real SMTP host, sender, operator contact, support address, hosting location, retention period, and deletion process before deployment; the production API refuses placeholder legal details. Optional Sentry reporting is enabled by setting `PROJECTPULSE_SENTRY_DSN`.

Signed-in users can export account data and delete their account from Settings. Workspace admins can invite members as admins or members. Owners and admins manage invitations and project calendars; members can access project work. Task owner changes generate in-app notifications. Calendar working weekdays and holidays are applied to project schedule calculations, and schedule timestamps include the configured time zone.
