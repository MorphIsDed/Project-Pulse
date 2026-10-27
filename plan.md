# ProjectPulse implementation scope

## Product

A local academic project planner using React/TypeScript, Flask, SQLite, NumPy, and pandas. The target remains roughly 1,000 tasks per project.

Keep authentication, organization roles, workspace/project management, direct member management, tasks/milestones, dependencies, working calendars, CPM/float, read-only Gantt, and ICS export. Retire resource management, leveling, risk simulation, invitations, notifications, and account export/deletion.

## Compact analytics

`GET /api/v1/projects/<id>/summary` requires membership, including viewer access. pandas groups all project tasks by status; NumPy computes mean, median, and p90 working-minute duration over positive-duration tasks. Completed percentage uses completed task count divided by all tasks, including milestones. Empty projects return zero counts and completion; no positive durations returns null statistics. Responses include the project version and are never persisted.

## Interface

A horizontal desktop navigation bar holds organization/workspace selectors, projects, management actions, and sign-out. Tasks is the default view; Timeline provides Gantt, recalculation, schedule details and export; Settings provides project metadata and calendar editing. Task details and dependency controls open in a side dialog. Management forms use focused dialogs. Named destructive confirmations remain explicit.

Use shared CSS tokens, system fonts, blue accents, subtle glass on navigation bar/toolbar, and device-controlled light/dark colors. Below 900px, navigation becomes a drawer; below 640px task details fill the screen. Native dialogs provide keyboard containment and Escape, with restored focus. Respect reduced motion and preserve input on failed saves.

## Compatibility

No schema reset, table drops, migration rewrites, or data conversion. Legacy storage mappings remain deliberately, and task estimate API fields remain compatible. Existing foreign-key cascades still apply when a user explicitly deletes a parent. Retired endpoints return the normal not-found response. Keep CSRF, tenancy checks, stale project versions, and scheduling rules.

## Acceptance

Verify summary calculations, empty/milestone-only projects, access control, project/task/dependency/calendar workflows, read-only roles, failed-save retry, dialog behavior, responsive themes, legacy record preservation, migration up/down/up on a disposable database, and production build. Document actual test and benchmark results in docs/evaluation.md.
