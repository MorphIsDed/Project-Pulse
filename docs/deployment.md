# Deployment

## Production setup

Production uses SQLite on a persistent Docker volume. Caddy serves the built frontend, routes `/api/*` to the private Flask API, and obtains and renews HTTPS certificates for `APP_DOMAIN`. The API port is not exposed to the internet. Gunicorn writes access and error logs to the container's standard output/error streams.

1. Point the domain's DNS record at the deployment host and allow inbound ports 80 and 443.
2. Copy `.env.example` to `.env`. Set `APP_DOMAIN`, generate a unique secret with `python -c "import secrets; print(secrets.token_hex(32))"`, and paste it as `PROJECTPULSE_SECRET_KEY`. Production startup rejects missing, short, and placeholder secrets.
3. Set `BACKUP_PATH` to a persistent, encrypted backup location. For production, use storage outside the application host and make the directory writable by container UID 10001.
4. Start the production stack:

   ```sh
   docker compose up -d --build
   ```

The API initializes the SQLite schema before starting Gunicorn. `/api/v1/health` checks database connectivity. Caddy sends HTTP traffic to HTTPS and serves the React single-page app at the same origin as the API.

## Automated backups

The `backup` service takes a consistent SQLite online backup immediately after the API is healthy and repeats at `PROJECTPULSE_BACKUP_INTERVAL_SECONDS` (default: daily). It checks SQLite integrity and foreign keys before publishing each backup and removes backups older than `PROJECTPULSE_BACKUP_RETENTION_DAYS` (default: 30). Failed backup operations are logged and the container restarts to retry.

Backups are stored under `BACKUP_PATH`. Configure that path as encrypted, persistent storage outside the application host; a local folder alone does not protect against host or disk loss. Restrict access to the backup location and include its contents in the organization's off-site retention policy.

To inspect the newest backup inside the running backup container:

```sh
BACKUP_FILE=projectpulse-20261026T000000Z.sqlite3
docker compose exec backup python -m app.backup verify "/backups/$BACKUP_FILE"
```

## Restore and restore drill

To run a non-destructive restore drill, restore a selected backup to a new file and verify its integrity, foreign keys, and per-table row counts:

```sh
docker compose exec backup python -m app.backup restore-check /backups/<backup-file> /backups/restore-drill.sqlite3
```

For recovery, stop the API first so no process has the live database open. Restore to the database path with `--replace`, then restart the stack:

```sh
BACKUP_FILE=projectpulse-20261026T000000Z.sqlite3
docker compose stop api backup
docker compose run --rm --no-deps restore restore-to "/backups/$BACKUP_FILE" /data/projectpulse.sqlite3 --replace
docker compose up -d api web backup
```

The restore command verifies the temporary copy and its row counts before atomically replacing the live file. Keep the failed database file and the selected backup until the restored app passes its health check and data review.

## Application and edge security

The production app requires a secret of at least 32 characters, trusted host and allowed origin settings, and secure session cookies. State-changing requests require the CSRF token and an allowed same-site origin. Caddy terminates HTTPS, applies HSTS and related browser security headers, and keeps the API private to the deployment network. Do not use Flask's development server or Vite's development server in production.

## Build images manually

The API image can also be built from the repository root:

```sh
docker build -f backend/Dockerfile -t projectpulse-api .
```

The production `compose.yml` is the recommended configuration because it includes the API, frontend/TLS edge, persistent SQLite data, and scheduled backups.
