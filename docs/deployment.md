# Deployment

## Current production boundary

The backend has a production WSGI image definition in `backend/Dockerfile`. Run it behind a TLS-terminating reverse proxy (for example, Caddy or a managed load balancer), and serve the built frontend from the same site origin. Forward `/api/*` to port 8000. Set the proxy's forwarded-proto header and restrict direct access to the backend port. The app logs Gunicorn access and error output to standard streams for the container platform to collect.

Copy `.env.example` to a deployment secret store and replace the placeholder key with a cryptographically random value. Configure the public hostname in both `PROJECTPULSE_TRUSTED_HOSTS` and `PROJECTPULSE_ALLOWED_ORIGINS`. `PROJECTPULSE_COOKIE_SECURE=1` is required in production. Do not use Vite's development server or Flask's development server in production.

Build from the repository root so the Dockerfile can copy `requirements.txt` and `backend/`:

```sh
docker build -f backend/Dockerfile -t projectpulse-api .
```

Mount a persistent writable volume at `/data`, then set `PROJECTPULSE_DATABASE=/data/projectpulse.sqlite3`. Initialize a new database with `flask --app wsgi init-db` from the container's `/app` directory before accepting traffic. Preserve the volume when replacing containers.

## Database and migration blocker

The current API uses SQLite's Python driver, `?` placeholders, `lastrowid`, SQLite DDL, and SQLite-specific schema bootstrapping. PostgreSQL is **not supported yet**. `Flask-Migrate` appearing in the root requirements does not currently provide migrations: it is not initialized, and the schema is still created by `init-db`. Do not point `PROJECTPULSE_DATABASE` at a PostgreSQL URL. Before a production launch, migrate persistence to a dialect-aware layer, add versioned migrations for both existing SQLite data and PostgreSQL, and exercise an upgrade from a real copy of the current schema.

## Backups and restore

Backups are not automated yet. For SQLite, use the SQLite online backup API (or a storage snapshot taken after quiescing writes) to create consistent copies; do not copy the live database file with ordinary file-copy tools. Store encrypted backups outside the application host, rotate them according to an approved retention policy, and perform a restore drill into an isolated environment before launch. No successful restore drill has been recorded for this repository.

## Edge and health checks

Terminate HTTPS at the proxy and redirect HTTP to HTTPS there. Restrict accepted hostnames at both the proxy and `PROJECTPULSE_TRUSTED_HOSTS`. The API health endpoint checks database connectivity at `/api/v1/health` and returns 503 if the query fails. Configure the platform to collect stdout/stderr and alert on repeated 5xx responses. There is no external error-monitoring integration yet.
