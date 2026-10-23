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

The initial Flask health endpoint, SQLite foundation, and React landing page are in place. The remaining roadmap features are planned work; see the status section in [plan.md](plan.md).

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
flask --app wsgi init-db
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

The development SQLite database is stored under `backend/instance/`. Do not commit database files, password hashes from real accounts, environment files, or production secrets. Replace development secrets with environment-based configuration before deployment. The Flask development server is for local development only.

## Development notes

- Keep scheduling and analytics logic independent of Flask request state.
- Use transactions for related writes and check project versions for stale edits.
- Enforce tenant membership on every project read and mutation.
- Keep schedule inputs separate from derived dates.
- Document any change to date, calendar, dependency, or simulation assumptions.
- Build features in the order and acceptance criteria in `plan.md`.
