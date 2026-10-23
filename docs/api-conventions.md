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

Starter codes: `invalid_json`, `validation_error`, `bad_request`, `unauthorized`, `forbidden`, `not_found`, `method_not_allowed`, `csrf_error`, `internal_error`.

Status mapping: validation and malformed input `400`, unauthenticated `401`, unauthorized `403`, missing resource `404`, wrong method `405`, conflict `409`, unsupported media type `415`, unexpected server failure `500`, unavailable dependency `503`.

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

## Health

`GET /api/v1/health` does not require authentication.

```json
{ "status": "ok", "service": "projectpulse-api", "database": "ok" }
```

When SQLite cannot be reached it returns `503` with `status: "degraded"` and `database: "unavailable"`.
