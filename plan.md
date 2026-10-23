# ProjectPulse Plan

## 1. Project overview

ProjectPulse is a locally deployed, browser-based project planning and analytics application. It is an academic project intended to demonstrate how project schedules can be created, analyzed, and explained. The target scale for the initial release is about 1,000 tasks in one project.

The application will support multiple organizations, workspaces, projects, and users. People in an organization can share plans, but the initial version will not support live co-editing. The main value is helping a project team see task timing, dependency effects, critical work, resource overload, and uncertainty around a target finish date.

## 2. Goals

- Create and manage organizations, workspaces, projects, and project teams.
- Create and organize tasks, milestones, dependencies, calendars, resources, and assignments.
- Show plans in an interactive Gantt chart.
- Recalculate schedules using working calendars and task dependencies.
- Explain critical path and task float.
- Identify when assigned resource demand exceeds resource capacity.
- Offer a transparent resource-leveling preview that users can accept or reject.
- Estimate deadline confidence using seeded PERT/Monte Carlo simulation.
- Export selected project events as an ICS calendar file.
- Evaluate the application with documented scenarios and measured performance.

## 3. Non-goals for the initial release

- Live multi-user editing or real-time presence.
- Enterprise single sign-on.
- Portfolio-level optimization or cross-project resource pooling.
- Two-way calendar synchronization or OAuth calendar integrations.
- Globally optimal resource-constrained scheduling.
- Email notifications unless the core application is complete and time remains.

## 4. Users and main workflows

### Organization owner or administrator

1. Register and sign in.
2. Create an organization and initial workspace.
3. Invite or add members and assign roles.
4. Create projects and control who can access them.

### Project planner or member

1. Open an authorized workspace and project.
2. Add tasks, milestones, estimates, dependencies, resources, and assignments.
3. Review or adjust the schedule in the Gantt view.
4. Inspect critical tasks, float, and resource overloads.
5. Preview leveling proposals and decide whether to apply them.
6. Run deadline-risk analysis and inspect its assumptions and results.
7. Export selected project dates to a calendar.

## 5. Proposed architecture

Use a modular monolith: one Flask application, one SQLite database, and one React/TypeScript frontend.

```text
Browser
  React + TypeScript
      | JSON over HTTP (/api/v1)
Flask application
  API routes -> validation and authorization -> services/repositories
                                         |             |
                                  scheduling       analytics
                                         |             |
                                      SQLite       ICS export
```

Keep route handlers thin. Scheduling and analytics code should use ordinary Python data structures and avoid Flask request context so those algorithms can be reasoned about independently. Use transactions for multi-table changes and project versions to detect stale edits. The initial application calculates schedules synchronously; simulation can move to background jobs only if measurements show that it is needed.

## 6. Core data model

- **Organization:** top-level tenant.
- **User:** global identity with unique email and password hash.
- **Organization membership:** a user’s role in an organization.
- **Workspace:** belongs to an organization.
- **Workspace membership:** optional finer-grained access within an organization; whether it is mandatory is an open policy decision.
- **Project:** belongs to a workspace and has a status, calendar, version, dates, and creator.
- **Task:** belongs to a project and may have a parent task; stores user inputs separately from calculated schedule fields.
- **Dependency:** directed link between tasks, with FS, SS, FF, or SF type and working-time lag.
- **Calendar:** project working intervals, timezone, holidays, and exceptions.
- **Resource and assignment:** project-scoped capacity plus task allocation.
- **Analysis run:** kind, input project version, parameters, summary, creator, and timestamp for reproducibility.
- **Audit event:** lightweight record of important changes.

Use integer primary keys, foreign keys, membership-pair uniqueness, and ISO-formatted dates/timestamps. Store audit timestamps in UTC. Enable SQLite foreign-key enforcement for every database connection. Every project request must verify access through its organization and applicable workspace membership. Never rely on a browser-supplied ID as authorization.

## 7. Scheduling and analysis rules

### Calendar and date convention

- API calendar dates use `YYYY-MM-DD`; audit timestamps use UTC ISO 8601.
- Internally, task finish is an exclusive event boundary. The UI must convert this convention to the date range it displays.
- Durations and lags are integer working minutes.
- The project calendar governs task duration and dependency lag in the first release.
- Calendar arithmetic skips nonworking intervals, holidays, and exceptions.
- A zero-duration task is a milestone and consumes no working minutes.
- Negative lag is allowed only when the resulting constraints remain valid.

### Dependencies and CPM

A project schedule must be a directed acyclic graph. Reject self-links, duplicate equivalent links, cross-project links, and cycles. Support:

- FS: successor start >= predecessor finish + lag.
- SS: successor start >= predecessor start + lag.
- FF: successor finish >= predecessor finish + lag.
- SF: successor finish >= predecessor start + lag.

Convert finish-event constraints to successor start bounds using the successor's duration and project calendar. The forward pass computes earliest dates. The backward pass uses the computed project finish unless a target finish/deadline is selected. Total float is the working-time distance from earliest to latest start; zero total float is critical under these conventions. Free float is the gap before a task constrains a successor. A DAG can still have infeasible hard constraints; return a clear error rather than silently moving fixed dates.

### Resource analysis

Build a working-interval or daily load profile per resource. An overload result identifies its resource, interval, assigned load, capacity, and contributing tasks. The leveling preview preserves dependencies and fixed dates, ranks lower-priority tasks first, then tasks with more float, then stable task ID, and proposes changes. It is an explainable heuristic, not an optimal solver.

### Risk analysis

Collect explicit optimistic (`a`), most-likely (`m`), and pessimistic (`b`) durations. Use beta-PERT sampling; the PERT mean is `(a + 4m + b) / 6`. Tasks without uncertainty estimates remain deterministic. A run records seed, iteration count, target deadline, project version, and distribution assumptions. Report median and percentile finish dates and deadline-hit probability. Present results as conditional planning estimates, not guarantees.

## 8. API outline

All API endpoints return JSON under `/api/v1`, with consistent errors containing a stable code and readable message. Paginate list endpoints.

- Authentication: register, login, logout, current user (`/me`).
- Tenancy: organizations, organization members, workspaces, workspace members.
- Planning: projects, tasks, dependencies, project calendar, resources, assignments.
- Scheduling: recalculate schedule; return changed task dates, float, critical path, and warnings.
- Analytics: critical path, resource overload, leveling preview, seeded risk simulation, saved analysis runs.
- Integration: project ICS export.

Use same-origin cookie sessions for local deployment where practical, protect state-changing routes against CSRF, and keep credentials and secrets out of source control.

## 9. Delivery phases and acceptance criteria

### Phase 0 — Requirements and design

Define roles, access rules, date conventions, dependency semantics, calendar policy, and analytical assumptions. Keep these documented in `docs/architecture.md` and `docs/scheduling-assumptions.md`.

### Phase 1 — Foundation

Create the React app, Flask app, SQLite setup, configuration, migration approach, consistent error format, and health route. Acceptance: local app starts, database initializes, and health endpoint responds.

### Phase 2 — Identity and tenancy

Implement registration/login/logout, organizations, memberships, workspaces, roles, and access checks. Acceptance: unauthorized users cannot access another organization’s projects.

### Phase 3 — Project and task management

Implement project/task CRUD, task hierarchy, assignments, and dependency CRUD with validation. Acceptance: create/edit/delete flows work; invalid and cross-project links are rejected.

### Phase 4 — Gantt and scheduling

Implement the Gantt experience, calendars, four dependency types, lag, cycle detection, CPM, and float. Acceptance: hand-calculated cases produce expected dates, critical path, and float.

### Phase 5 — Resource analysis

Implement load profiles, overload views, and leveling preview. Acceptance: overload results identify contributing tasks and proposals respect dependencies when feasible.

### Phase 6 — Risk analysis

Implement PERT input, seeded Monte Carlo runs, percentile/confidence outputs, and saved runs. Acceptance: fixed-seed runs are reproducible and deterministic tasks produce deterministic dates.

### Phase 7 — Export and polish

Implement ICS export and usability improvements; consider email only if core work is complete. Acceptance: ICS imports into a calendar application and core flows work from a clean local setup.

### Phase 8 — Evaluation and report

Prepare demo data, scenario results, measured performance, limitations, and the final academic report. Evaluate task loading, schedule recalculation, and simulation near 1,000 tasks, recording hardware, input shape, and run count. Conduct a small user evaluation of creating a plan, adding dependencies, finding critical work, resolving overload, and interpreting deadline confidence.

## 10. Testing and evaluation approach

- Unit-level checks: calendar arithmetic, dependency types, lead/lag, cycles, CPM, float, PERT, and resource aggregation.
- API checks: validation, database transactions, permissions, recalculation, and reproducible saved runs.
- Frontend checks: Gantt interactions, form validation, error states, and date/timezone rendering.
- Scenario: parallel paths, shared resources, holidays, a milestone, and an imposed deadline.
- Performance: approximately 1,000 tasks; record environment and workload shape.
- User evaluation: record where participants are confused and what they can complete unaided.

## 11. Current implementation status

Milestone M0 (platform foundation) is complete: Flask app factory, environment-based configuration, Flask-SQLAlchemy models, Flask-Migrate/Alembic baseline, session and CSRF scaffolding, a consistent JSON error envelope, request IDs and access logging, a database-aware health endpoint, pytest fixtures/tests, documentation, and CI.

Milestone M1 (identity) is complete: a `users` model and migration, password hashing, normalized email validation, disabled-by-default registration, login/logout/current-user endpoints, CSRF token issuance, an idempotent `flask seed-demo` command with owner/editor/viewer demo accounts, authentication tests, and a React sign-in screen with session restore and sign-out.

Organization/workspace access control (M2), project/task planning (M3), scheduling and Gantt (M4–M5), resource analytics (M6), risk simulation (M7), and ICS export (M8) remain to be implemented. Treat this plan as the target design; update this section as features are completed.

## 12. Open decisions

- Is organization membership sufficient for access, or must a user also have workspace membership?
- Which roles exist, and which actions may each role perform?
- Which task constraints are supported and are they hard or advisory?
- Can each project choose its timezone and working hours in the first release?
- Which Gantt interactions and library best fit the academic evaluation?
