# Evaluation

Snapshot date: 2026-10-27.

This document records the automated verification and measured performance available for the M9 evaluation. It distinguishes measured evidence from work that was not performed, especially the human user evaluation.

## Automated verification

Commands were run from the repository root environment on Windows 11.

| Check | Command | Result |
| --- | --- | --- |
| Backend tests | `..\.venv\Scripts\python.exe -m pytest -q` from `backend` | 108 passed, 1 third-party deprecation warning |
| Frontend tests | `npm test` from `frontend` | 64 passed in 11 test files |
| Frontend typecheck/build | `npm run build` from `frontend` | Passed; Vite production build completed |
| Migration chain | `flask db upgrade`, `db downgrade base`, `db upgrade` against a temporary SQLite file | Passed from baseline through `9c3d5e7f8a9b` and back |

The backend suite uses an isolated temporary SQLite database and covers authentication, CSRF, tenancy, planning, calendars, CPM, resources, risk, export, collaboration, account deletion, configuration, errors, health, request IDs, and demo seeding. The frontend suite covers authentication, the workspace, the Gantt chart, resource workloads, risk simulation, invitations, notifications, account controls, and the API client.

## Scenario coverage

| Scenario | Evidence |
| --- | --- |
| Working calendars, holidays, exceptions, and daylight-saving transitions | `backend/tests/test_calendar.py` |
| FS/SS/FF/SF dependencies, lag, constraints, float, critical path, milestones, and target finish | `backend/tests/test_cpm.py`, `backend/tests/test_schedule.py` |
| Resource aggregation, overloads, leveling priority, and target-finish boundary | `backend/tests/test_resources.py` |
| Seed reproducibility, PERT sampling, deterministic fallback, percentiles, target probability, and critical frequency | `backend/tests/test_risk.py` |
| ICS all-day events, escaping, CRLF line endings, and attachment naming | `backend/tests/test_export.py`, `backend/tests/test_collaboration.py` |
| Invitations, role assignment, notifications, account export, and account deletion | `backend/tests/test_collaboration.py` |
| Resource, risk, invitation, notification, account, and workspace UI | `frontend/src/components/*.test.tsx`, `frontend/src/pages/WorkspacePage.test.tsx` |

## Performance benchmark

The benchmark is reproducible from `backend`:

```powershell
..\.venv\Scripts\python.exe -m scripts.benchmark --runs 5 --iterations 2000
```

Recorded environment:

- Windows 11 (build 26200), Python 3.12.10
- Intel Core Ultra 9 285H, 16 cores, 31.4 GB RAM
- Local SQLite database; development configuration

Input shape:

- 1,000 tasks in 100 independent finish-to-start chains of 10 tasks
- 900 dependencies
- 8-hour deterministic durations
- Risk estimates of optimistic 4 hours, most likely 8 hours, and pessimistic 12 hours per task
- 2,000 seeded risk iterations (`seed=42`)

Results:

| Measurement | Median | Minimum | Maximum |
| --- | --- | --- | --- |
| CPM schedule calculation, 5 runs | 6.2 ms | 6.2 ms | 7.1 ms |
| Risk simulation, 2,000 iterations | 36.1 s (single run) | - | - |

The CPM engine scales comfortably for the 1,000-task target in this shape. Synchronous risk simulation is the measured bottleneck: each iteration recalculates the full schedule, so a 1,000-task project with default iterations takes tens of seconds and blocks the request. The endpoint remains synchronous by design; moving it to a background job or reducing iterations would be needed before larger projects or stricter response-time targets.

## Evaluation limits

- The benchmark is synthetic. It does not cover every dependency topology, calendar exception pattern, or resource assignment density.
- Timings are single-machine observations, not a statistically controlled experiment. Host load and SQLite file placement can change them.
- Risk simulations are not persisted, so saved-run comparison and audit history are not evaluated.
- The leveling preview is an explainable heuristic. It is not compared with an optimal resource-constrained scheduler.
- The deployment path is documented, but no production deployment or backup/restore drill has been recorded.
- No small human user evaluation was conducted. The workflow study described in the plan (creating a plan, finding critical work, resolving overload, and interpreting deadline confidence) remains future work.

## Reproducibility notes

- Backend test command: `..\.venv\Scripts\python.exe -m pytest -q` from `backend`.
- Frontend test command: `npm test` from `frontend`.
- Risk runs return the seed, iteration count, project version, and assumptions so a run can be repeated against the same project inputs.
- The migration chain is verified up, down to base, and up again; CI performs the same cycle on every push to `main`.
