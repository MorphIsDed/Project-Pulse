# Deployment

## Production boundary

The backend has a production WSGI image definition in `backend/Dockerfile`. Run it behind a TLS-terminating reverse proxy, and serve the Vite build from the same site origin. Forward `/api/*` to the API on port 8000. The image runs Gunicorn with two workers and logs access and error output to standard streams.

<<<<<<< HEAD
1. Point the domain's DNS record at the deployment host and allow inbound ports 80 and 443.
2. Copy `.env.example` to `.env`. Set `APP_DOMAIN`, generate a unique secret with `python -c "import secrets; print(secrets.token_hex(32))"`, and paste it as `PROJECTPULSE_SECRET_KEY`. Production startup rejects missing, short, and placeholder secrets. Public registration is enabled by default; set `ALLOW_PUBLIC_SIGNUP=0` to restrict account creation to administrators and invitations. New users must verify their email before signing in.
3. Set `BACKUP_PATH` to a persistent, encrypted backup location. For production, use storage outside the application host and make the directory writable by container UID 10001.
4. Start the production stack:
=======
The image sets `APP_ENV=production` and defaults `DATABASE_URL` to `sqlite:////data/projectpulse.sqlite3`. Mount a persistent writable volume at `/data` and keep the volume when replacing containers. Set `SECRET_KEY` to a cryptographically random value at runtime; the app refuses to start in production without it.
>>>>>>> bb8b5819780a204a93d4a7baf3a81d69b145293a

Production cookies are secure and HTTP-only. Build the frontend with `npm run build` and serve `frontend/dist` from the reverse proxy or static host on the same site origin as the API. Do not use Vite's development server or Flask's development server in production.

Build from the repository root because the Dockerfile copies the root `requirements.txt` and `backend/`:

```sh
docker build -f backend/Dockerfile -t projectpulse-api .
docker run --rm \
  -e SECRET_KEY="replace-with-a-random-secret" \
  -v projectpulse-data:/data \
  -p 8000:8000 \
  projectpulse-api
```

Run migrations and seed the demo tenant only when appropriate before accepting traffic:

```sh
docker run --rm -e SECRET_KEY="replace-with-a-random-secret" \
  -v projectpulse-data:/data projectpulse-api flask --app wsgi db upgrade
docker run --rm -e SECRET_KEY="replace-with-a-random-secret" \
  -v projectpulse-data:/data projectpulse-api flask --app wsgi seed-demo
```

`flask seed-demo` refuses production unless `--force` is passed.

## Database and migrations

SQLite is the only supported database. Flask-Migrate/Alembic is the schema-change path; `init-db` from older prototype notes is not used. Apply upgrades with `flask --app wsgi db upgrade` from `/app` or through the migration command above. Review migrations before applying, and back up the database before an upgrade.

## Backups and restore

Backups are not automated. For SQLite, use the SQLite online backup API or a storage snapshot taken after quiescing writes; do not copy a live database with ordinary file-copy tools. Store encrypted backups outside the application host, rotate them according to an approved retention policy, and rehearse a restore into an isolated environment. No successful restore drill has been recorded for this repository.

## Health and operations

Terminate HTTPS at the proxy and redirect HTTP to HTTPS there. Restrict direct access to the backend port. `GET /api/v1/health` checks database connectivity and returns `503` when the query fails. Collect stdout/stderr, alert on repeated 5xx responses.

There is no external error-monitoring integration. Request IDs are returned in `X-Request-ID` and are included in logs and error envelopes.
