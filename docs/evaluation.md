# Evaluation

## Verification recorded 2026-10-27

Baseline before cleanup: 108 backend tests and 64 frontend tests passed. After retiring feature-specific tests and adding summary, compatibility, and UI coverage: 101 backend tests and 61 frontend tests pass. The production frontend build also passes, including unused-local/parameter checks. One existing Flask-Login datetime deprecation warning remains.

Backend command (from backend):

```powershell
..\.venv\Scripts\python.exe -m pytest -q --basetemp=./.test-cleanup
```

Frontend commands (from frontend):

```powershell
npm test
npm run build
```

A workspace-local pytest temporary directory was used because the sandbox default temp directory was inaccessible. Tests use disposable databases; the application's existing database was not changed.

## Coverage and migration evidence

Tests cover authentication/CSRF, tenant isolation, role permissions, planning validation, calendars, dependency semantics, CPM/float, Gantt, ICS export, and compact analytics. Summary cases include known duration percentiles, empty projects, milestone-only projects, all status keys, task updates, viewer access, anonymous requests, and non-member denial.

The compatibility test inserts legacy resources, assignments, notifications, invitations, and task estimates, restarts the app against the same temporary database, edits a task, and verifies those legacy records remain intact. Retired routes are checked against the registered route map.

Alembic upgrade/check/downgrade-to-base/upgrade/check and demo seeding passed on a separate disposable database. Both model drift checks reported no new upgrade operations. No migration file was modified.

## Browser verification

Headless Chrome was exercised against a local Flask/Vite app with a disposable seeded database. Desktop (1440px), tablet (820px), and mobile (390px) layouts were inspected in light and dark modes. Cases included long task names, project insights, Gantt, task details, settings, navigation drawer, empty projects, and a simulated summary error. No page JavaScript errors or mobile page overflow were detected. Tab focus remains in dialogs; Escape closes them and restores focus. Reduced-motion emulation was used for deterministic screenshots.

Unit tests also cover task creation/summary refresh, failed-save input preservation and retry, named deletion confirmation, project switching, viewer read-only controls, and summary failures that do not block editing. Task/dependency loading follows pagination so the task list and full-project insights cover the same project.

## Benchmark

Run from backend:

```powershell
..\.venv\Scripts\python.exe -m scripts.benchmark --runs 3
```

Recorded on Windows 11, Python 3.12.10, Intel64 Family 6 Model 197. Workload: 1,000 tasks, 100 independent chains of 10, and 900 dependencies.

| Computation | Median | Range | Runs |
| --- | --- | --- | --- |
| Calendar-aware schedule | 0.0025 s | 0.0025–0.0026 s | 3 |
| pandas/NumPy task summary | 0.0008 s | 0.0007–0.0009 s | 3 |

These warmed computation measurements exclude HTTP, database reads, browser rendering, and process/library startup. They are not end-to-end latency promises. Resource leveling and risk simulation benchmarks have been removed with those features.

## Limits

No human user study or production deployment validation was performed. Gantt remains read-only. SQLite is the supported datastore. The simple calendar UI edits one daily interval and preserves existing exceptions; richer calendars remain available through the API. Legacy storage remains intentionally for compatibility.
