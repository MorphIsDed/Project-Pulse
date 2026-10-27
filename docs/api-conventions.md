# API conventions

All application endpoints are JSON under `/api/v1`.

## Errors

Every error response uses one envelope:

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

- `code` is stable and machine-readable.
- `message` is readable and safe to show to a user.
- `details` is optional and request-specific.
- `request_id` matches the `X-Request-ID` response header and the server log entry.

Core codes: `invalid_json`, `validation_error`, `bad_request`, `unauthorized`, `forbidden`, `not_found`, `method_not_allowed`, `csrf_error`, `internal_error`.

Tenancy, planning, and scheduling add domain codes such as `invalid_name`, `invalid_role`, `member_not_found`, `member_exists`, `last_owner`, `workspace_conflict`, `project_conflict`, `stale_project`, `invalid_date`, `invalid_date_range`, `invalid_status`, `invalid_description`, `invalid_parent`, `parent_cycle`, `invalid_duration`, `invalid_progress`, `invalid_priority`, `invalid_constraint`, `invalid_constraint_date`, `invalid_estimates`, `invalid_task`, `invalid_dependency_type`, `invalid_lag`, `self_dependency`, `cross_project_dependency`, `duplicate_dependency`, `dependency_cycle`, `invalid_calendar`, `invalid_timezone`, `invalid_weekly_rules`, `invalid_exception`, `invalid_schedule`, `schedule_infeasible`, `schedule_horizon_exceeded`, `empty_update`, `unsupported_field`, `invalid_pagination`, `organization_creation_failed`, `task_creation_failed`, `task_update_failed`, `already_member`, `invalid_invitation`, `invitation_email_mismatch`, `email_delivery_failed`, `risk_simulation_infeasible`, `invalid_credentials`, `invalid_resource`, `invalid_capacity`, `resource_conflict`, and `duplicate_assignment`.

Status mapping: validation and malformed input `400`, unauthenticated `401`, unauthorized `403`, missing resource `404`, wrong method `405`, conflict `409`, unsupported media type `415`, unprocessable planning/scheduling input `422`, unexpected server failure `500`, unavailable dependency `503`.

Unhandled exceptions return `internal_error` with a generic message; details and stack traces stay in server logs.

## Request correlation

Clients may send `X-Request-ID`. The API echoes it, or generates one when it is absent. Logs include method, path, status, duration, and request ID.

## Dates and time

- API calendar dates use `YYYY-MM-DD`.
- Audit timestamps use UTC ISO 8601.
- Durations and lags are integer working minutes.
- Task finish is an exclusive event boundary internally; the UI converts it to the displayed date range.

## Authentication and CSRF

Authentication uses same-origin cookie sessions backed by Flask-Login. State-changing requests must send the current token in the `X-CSRFToken` header. Get a token from `GET /api/v1/auth/csrf`; login and registration return a fresh token that replaces it. A stale token produces `400` with code `csrf_error`, after which the client should fetch a new token and retry once.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/auth/csrf` | Issue a CSRF token |
| `POST` | `/api/v1/auth/register` | Create an account (disabled by default) |
| `POST` | `/api/v1/auth/login` | Start a session |
| `POST` | `/api/v1/auth/logout` | End a session |
| `GET` | `/api/v1/auth/me` | Return the current user |

Login and registration bodies use `email`, `password`, and (for registration) `display_name`; login also accepts `remember`. Responses return `{ "user": { "id", "email", "display_name" }, "csrf_token" }` and never include password hashes. `POST /auth/register` returns `403 registration_disabled` unless `ALLOW_PUBLIC_SIGNUP=true`. Invalid login attempts return the same `401 invalid_credentials` message for an unknown email and a wrong password. Duplicate registration returns `409 email_taken`.

## Tenancy and authorization

Organization membership is the access boundary. A membership has one role:

| Role | Capabilities |
| --- | --- |
| `owner` | All tenancy, member, invitation, workspace, project, task, dependency, and resource actions; delete organization; manage the `owner` role. |
| `admin` | Manage non-owner members and invitations; create/rename/delete workspaces; create/update/delete projects; edit tasks, dependencies, and resources. Cannot delete the organization or grant/manage `owner`. |
| `editor` | Create/update projects; create/update/delete tasks, dependencies, and resources. Cannot manage tenancy, members, invitations, or delete projects. |
| `viewer` | Read-only access to organizations, members, workspaces, projects, calendar, tasks, dependencies, schedules, resources, and analytics. |

Non-members receive `404` rather than learning that a resource exists. Members with insufficient role receive `403 forbidden`. The API prevents removing or demoting the last organization owner with `409 last_owner`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/organizations` | List organizations for the current user |
| `POST` | `/api/v1/organizations` | Create an organization and owner membership |
| `GET` | `/api/v1/organizations/<id>` | Read an organization |
| `PATCH` | `/api/v1/organizations/<id>` | Rename an organization |
| `DELETE` | `/api/v1/organizations/<id>` | Delete an organization (owner only) |
| `GET` | `/api/v1/organizations/<id>/members` | List members |
| `POST` | `/api/v1/organizations/<id>/members` | Add an existing user by email |
| `PATCH` | `/api/v1/organizations/<id>/members/<user_id>` | Change a member role |
| `DELETE` | `/api/v1/organizations/<id>/members/<user_id>` | Remove a member |
| `GET` | `/api/v1/organizations/<id>/workspaces` | List workspaces |
| `POST` | `/api/v1/organizations/<id>/workspaces` | Create a workspace |
| `GET` | `/api/v1/workspaces/<id>` | Read a workspace |
| `PATCH` | `/api/v1/workspaces/<id>` | Rename a workspace |
| `DELETE` | `/api/v1/workspaces/<id>` | Delete a workspace and its projects |

Workspace names are unique within an organization using case-insensitive comparison.

## Planning

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/workspaces/<id>/projects` | List projects |
| `POST` | `/api/v1/workspaces/<id>/projects` | Create a project and default calendar |
| `GET` | `/api/v1/projects/<id>` | Read a project |
| `PATCH` | `/api/v1/projects/<id>` | Update a project (requires `version`) |
| `DELETE` | `/api/v1/projects/<id>` | Delete a project (owner/admin) |
| `GET` | `/api/v1/projects/<id>/calendar` | Read the project calendar |
| `PATCH` | `/api/v1/projects/<id>/calendar` | Update calendar name/timezone/rules/exceptions (requires `version`) |
| `GET` | `/api/v1/projects/<id>/schedule` | Calculate the current project schedule |
| `GET` | `/api/v1/projects/<id>/tasks` | List tasks |
| `POST` | `/api/v1/projects/<id>/tasks` | Create a task |
| `GET` | `/api/v1/projects/<id>/tasks/<task_id>` | Read a task |
| `PATCH` | `/api/v1/projects/<id>/tasks/<task_id>` | Update a task |
| `DELETE` | `/api/v1/projects/<id>/tasks/<task_id>` | Delete a task |
| `GET` | `/api/v1/projects/<id>/dependencies` | List dependencies |
| `POST` | `/api/v1/projects/<id>/dependencies` | Create a dependency |
| `DELETE` | `/api/v1/projects/<id>/dependencies/<dependency_id>` | Delete a dependency |

Project names are case-insensitively unique within a workspace. Projects default to `active` status and version `1`; every project, task, or dependency mutation that changes planning inputs increments the project version. Task and dependency mutation responses include `project_version`. A project `PATCH` must send the loaded `version`; a mismatch returns `409 stale_project`.

Tasks support `not_started`, `in_progress`, `blocked`, and `completed`; duration is non-negative integer working minutes; progress is 0-100; priority is 1-5; `parent_task_id` must reference a task in the same project and must not create a hierarchy cycle. Constraint types are `none`, `start_no_earlier_than`, `start_no_later_than`, `must_start_on`, `finish_no_earlier_than`, `finish_no_later_than`, and `must_finish_on`; a non-`none` constraint requires `constraint_date` (`YYYY-MM-DD`). PERT estimates are optional but must be supplied together in ascending non-negative order.

Dependencies support `FS`, `SS`, `FF`, and `SF`, with integer `lag_work_minutes` (negative lag is allowed). Self-links, cross-project links, duplicate equivalent links, and cycles are rejected. The default calendar uses timezone `UTC` and Monday-Friday 09:00-17:00 rules. M4 makes it editable for editor, admin, and owner roles. A calendar PATCH must send the loaded project `version` and returns the updated calendar plus project; stale versions return `409 stale_project`.

List endpoints accept `limit` (default 50, maximum 100) and `offset` (non-negative). Task lists also accept `status` and `parent_task_id`. Invalid pagination returns `400 invalid_pagination`. CSRF applies to all state-changing routes above.

## Scheduling

`GET /api/v1/projects/<id>/schedule` calculates on demand and returns the project start/finish, task early/late dates, total/free float in working minutes, critical flags, critical path, dependencies, calendar snapshot, and warnings. Schedules are not persisted.

- The project start is `start_date`; when absent, the current date in the calendar timezone is used and a `project_start_defaulted` warning is returned. A nonworking start moves to the next working instant with `project_start_adjusted`.
- The engine supports FS, SS, FF, and SF dependencies with working-minute lag, zero-duration milestones, and all seven task constraint types.
- A target finish is an advisory backward-pass boundary. Missing it returns a `target_finish_missed` warning and negative float; it does not reject the schedule.
- Conflicting hard constraints or dependency/constraint combinations return `422 schedule_infeasible`. A fixed constraint date on a nonworking day returns `422 invalid_constraint_date`.
- Calendar rules use `mon` through `sun`, at least one working interval, and non-overlapping intervals. Exceptions use `{date, name, working, intervals}` and replace the weekly rule for that date. Timezones must be valid IANA names.

## Resources and analytics

Editor, admin, and owner roles manage resources and assignments; viewers may read them and request analytics.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/projects/<id>/resources` | List project resources |
| `POST` | `/api/v1/projects/<id>/resources` | Create a resource |
| `PATCH` | `/api/v1/projects/<id>/resources/<resource_id>` | Update a resource |
| `DELETE` | `/api/v1/projects/<id>/resources/<resource_id>` | Delete a resource |
| `GET` | `/api/v1/projects/<id>/assignments` | List task assignments |
| `POST` | `/api/v1/projects/<id>/assignments` | Assign a resource to a task |
| `PATCH` | `/api/v1/projects/<id>/assignments/<assignment_id>` | Update allocation |
| `DELETE` | `/api/v1/projects/<id>/assignments/<assignment_id>` | Remove an assignment |
| `GET` | `/api/v1/projects/<id>/workload` | Return load and overload intervals |
| `POST` | `/api/v1/projects/<id>/leveling-preview` | Preview leveling proposals |
| `POST` | `/api/v1/projects/<id>/risk-simulation` | Run a seeded PERT/Monte Carlo simulation |

The leveling preview is read-only: it proposes changes but does not mutate tasks. The risk-simulation body accepts an optional `seed` and `iterations`; iterations default to 2,000 and must be between 100 and 10,000. The response includes the seed, project version, deterministic finish, finish percentiles, target probability, per-task distributions, and assumptions.

## Export, collaboration, and account

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/projects/<id>/export.ics` | Download an all-day ICS calendar |
| `GET` | `/api/v1/notifications` | List the current user's notifications |
| `PATCH` | `/api/v1/notifications/<id>` | Mark one notification read |
| `POST` | `/api/v1/notifications/read-all` | Mark all notifications read |
| `GET` | `/api/v1/organizations/<id>/invitations` | List pending invitations (admin/owner) |
| `POST` | `/api/v1/organizations/<id>/invitations` | Create an invitation (admin/owner) |
| `DELETE` | `/api/v1/organizations/<id>/invitations/<invitation_id>` | Revoke an invitation |
| `POST` | `/api/v1/invitations/accept` | Accept an invitation with a token |
| `GET` | `/api/v1/account/export` | Download the current account as JSON |
| `DELETE` | `/api/v1/account` | Delete the account after password confirmation |

Invitation responses include `accept_token` outside production so development clients can complete the flow without email. Invitations expire after seven days and must be accepted by the invited email address. Account deletion removes a sole-member organization; otherwise an owner role passes to an admin or the earliest remaining member.

## Health

`GET /api/v1/health` does not require authentication.

```json
{ "status": "ok", "service": "projectpulse-api", "database": "ok" }
```

When SQLite cannot be reached it returns `503` with `status: "degraded"` and `database: "unavailable"`.
