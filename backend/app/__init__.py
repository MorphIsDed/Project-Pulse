from pathlib import Path
import os
import sqlite3
import secrets
from urllib.parse import urlparse

from flask import Flask, current_app, g, jsonify, request, session


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        database_path = Path(current_app.config["DATABASE"])
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


def close_db(_error: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db() -> None:
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT OR IGNORE INTO schema_meta(version) VALUES (1);

        CREATE TABLE IF NOT EXISTS organizations (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS organization_memberships (
            organization_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'member')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (organization_id, user_id),
            FOREIGN KEY (organization_id)
                REFERENCES organizations(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id)
                REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS workspaces (
            id INTEGER PRIMARY KEY,
            organization_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (organization_id, name),
            FOREIGN KEY (organization_id)
                REFERENCES organizations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY,
            workspace_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'on_hold', 'completed', 'archived')),
            start_date TEXT,
            target_finish TEXT,
            calendar_id INTEGER,
            version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
            created_by INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (workspace_id, name),
            FOREIGN KEY (workspace_id)
                REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY (calendar_id)
                REFERENCES calendars(id) ON DELETE SET NULL,
            FOREIGN KEY (created_by)
                REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS calendars (
            id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL UNIQUE,
            name TEXT NOT NULL,
            timezone TEXT NOT NULL DEFAULT 'UTC',
            weekly_rules TEXT NOT NULL DEFAULT '{}',
            exceptions TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id)
                REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            parent_task_id INTEGER,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'not_started'
                CHECK (status IN ('not_started', 'in_progress', 'blocked', 'completed')),
            duration_work_minutes INTEGER NOT NULL DEFAULT 0
                CHECK (duration_work_minutes >= 0),
            progress INTEGER NOT NULL DEFAULT 0
                CHECK (progress BETWEEN 0 AND 100),
            priority INTEGER NOT NULL DEFAULT 3
                CHECK (priority BETWEEN 1 AND 5),
            constraint_type TEXT NOT NULL DEFAULT 'none'
                CHECK (constraint_type IN (
                    'none',
                    'start_no_earlier_than',
                    'start_no_later_than',
                    'must_start_on',
                    'finish_no_earlier_than',
                    'finish_no_later_than',
                    'must_finish_on'
                )),
            constraint_date TEXT,
            estimate_optimistic INTEGER,
            estimate_most_likely INTEGER,
            estimate_pessimistic INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id)
                REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_task_id)
                REFERENCES tasks(id) ON DELETE SET NULL,
            CHECK (parent_task_id IS NULL OR parent_task_id != id),
            CHECK (
                (estimate_optimistic IS NULL
                 AND estimate_most_likely IS NULL
                 AND estimate_pessimistic IS NULL)
                OR
                (estimate_optimistic IS NOT NULL
                 AND estimate_most_likely IS NOT NULL
                 AND estimate_pessimistic IS NOT NULL
                 AND estimate_optimistic >= 0
                 AND estimate_most_likely >= estimate_optimistic
                 AND estimate_pessimistic >= estimate_most_likely)
            )
        );

        CREATE TABLE IF NOT EXISTS dependencies (
            id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            predecessor_task_id INTEGER NOT NULL,
            successor_task_id INTEGER NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('FS', 'SS', 'FF', 'SF')),
            lag_work_minutes INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (project_id)
                REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (predecessor_task_id)
                REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (successor_task_id)
                REFERENCES tasks(id) ON DELETE CASCADE,
            CHECK (predecessor_task_id != successor_task_id),
            UNIQUE (project_id, predecessor_task_id, successor_task_id, type)
        );

        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            calendar_id INTEGER,
            name TEXT NOT NULL,
            resource_type TEXT NOT NULL DEFAULT 'person'
                CHECK (resource_type IN ('person', 'equipment', 'other')),
            capacity_units REAL NOT NULL DEFAULT 1.0 CHECK (capacity_units > 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id)
                REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (calendar_id)
                REFERENCES calendars(id) ON DELETE SET NULL,
            UNIQUE (project_id, name)
        );

        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY,
            task_id INTEGER NOT NULL,
            resource_id INTEGER NOT NULL,
            units REAL NOT NULL DEFAULT 1.0 CHECK (units > 0),
            work_minutes_per_day INTEGER CHECK (
                work_minutes_per_day IS NULL OR work_minutes_per_day >= 0
            ),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE,
            UNIQUE (task_id, resource_id)
        );

        CREATE TABLE IF NOT EXISTS analysis_runs (
            id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            kind TEXT NOT NULL CHECK (
                kind IN ('critical_path', 'resource_overload', 'leveling', 'risk_simulation')
            ),
            project_version INTEGER NOT NULL CHECK (project_version > 0),
            parameters_json TEXT NOT NULL DEFAULT '{}',
            summary_json TEXT NOT NULL DEFAULT '{}',
            created_by INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY,
            organization_id INTEGER NOT NULL,
            user_id INTEGER,
            project_id INTEGER,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            action TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id)
                REFERENCES organizations(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_memberships_user
            ON organization_memberships(user_id);
        CREATE INDEX IF NOT EXISTS idx_workspaces_organization
            ON workspaces(organization_id);
        CREATE INDEX IF NOT EXISTS idx_projects_workspace
            ON projects(workspace_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_project
            ON tasks(project_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_parent
            ON tasks(parent_task_id);
        CREATE INDEX IF NOT EXISTS idx_dependencies_predecessor
            ON dependencies(predecessor_task_id);
        CREATE INDEX IF NOT EXISTS idx_dependencies_successor
            ON dependencies(successor_task_id);
        CREATE INDEX IF NOT EXISTS idx_resources_project
            ON resources(project_id);
        CREATE INDEX IF NOT EXISTS idx_assignments_task
            ON assignments(task_id);
        CREATE INDEX IF NOT EXISTS idx_assignments_resource
            ON assignments(resource_id);
        CREATE INDEX IF NOT EXISTS idx_analysis_runs_project
            ON analysis_runs(project_id);
        CREATE INDEX IF NOT EXISTS idx_audit_events_organization_time
            ON audit_events(organization_id, created_at);

        CREATE TRIGGER IF NOT EXISTS trg_tasks_parent_same_project_insert
        BEFORE INSERT ON tasks
        WHEN NEW.parent_task_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM tasks
              WHERE id = NEW.parent_task_id AND project_id = NEW.project_id
          )
        BEGIN
            SELECT RAISE(ABORT, 'parent task must belong to the same project');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_tasks_parent_same_project_update
        BEFORE UPDATE OF parent_task_id, project_id ON tasks
        WHEN NEW.parent_task_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM tasks
              WHERE id = NEW.parent_task_id AND project_id = NEW.project_id
          )
        BEGIN
            SELECT RAISE(ABORT, 'parent task must belong to the same project');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_dependencies_same_project_insert
        BEFORE INSERT ON dependencies
        WHEN NOT EXISTS (
            SELECT 1
            FROM tasks AS predecessor
            JOIN tasks AS successor
              ON successor.id = NEW.successor_task_id
            WHERE predecessor.id = NEW.predecessor_task_id
              AND predecessor.project_id = NEW.project_id
              AND successor.project_id = NEW.project_id
        )
        BEGIN
            SELECT RAISE(ABORT, 'dependency tasks must belong to the same project');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_dependencies_same_project_update
        BEFORE UPDATE OF project_id, predecessor_task_id, successor_task_id
        ON dependencies
        WHEN NOT EXISTS (
            SELECT 1
            FROM tasks AS predecessor
            JOIN tasks AS successor
              ON successor.id = NEW.successor_task_id
            WHERE predecessor.id = NEW.predecessor_task_id
              AND predecessor.project_id = NEW.project_id
              AND successor.project_id = NEW.project_id
        )
        BEGIN
            SELECT RAISE(ABORT, 'dependency tasks must belong to the same project');
        END;

        INSERT OR IGNORE INTO schema_meta(version) VALUES (2);
        """
    )

    # Additive upgrades for databases created by the earlier starter schema.
    project_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(projects)").fetchall()
    }
    project_additions = {
        "start_date": "TEXT",
        "target_finish": "TEXT",
        "calendar_id": "INTEGER REFERENCES calendars(id) ON DELETE SET NULL",
        "version": "INTEGER NOT NULL DEFAULT 1 CHECK (version > 0)",
        "updated_at": "TEXT",
    }
    for column, definition in project_additions.items():
        if column not in project_columns:
            db.execute(f"ALTER TABLE projects ADD COLUMN {column} {definition}")

    db.execute(
        "UPDATE projects SET updated_at = CURRENT_TIMESTAMP "
        "WHERE updated_at IS NULL OR updated_at = ''"
    )
    db.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS trg_projects_updated_at_insert
        AFTER INSERT ON projects
        WHEN NEW.updated_at IS NULL OR NEW.updated_at = ''
        BEGIN
            UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END;

        CREATE TRIGGER IF NOT EXISTS trg_projects_updated_at_update
        AFTER UPDATE ON projects
        WHEN NEW.updated_at = OLD.updated_at
        BEGIN
            UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END;
        """
    )
    db.commit()


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    production = os.environ.get("PROJECTPULSE_ENV", "development").lower() == "production"
    secret_key = os.environ.get("PROJECTPULSE_SECRET_KEY")
    if production and not secret_key:
        raise RuntimeError("PROJECTPULSE_SECRET_KEY must be set in production.")
    if production and (not os.environ.get("PROJECTPULSE_TRUSTED_HOSTS") or not os.environ.get("PROJECTPULSE_ALLOWED_ORIGINS")):
        raise RuntimeError("PROJECTPULSE_TRUSTED_HOSTS and PROJECTPULSE_ALLOWED_ORIGINS must be set in production.")
    app.config.from_mapping(
        SECRET_KEY=secret_key or "local-development-secret-not-for-deployment",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=production,
        PREFERRED_URL_SCHEME="https" if production else "http",
        TRUSTED_HOSTS=[host.strip() for host in os.environ.get("PROJECTPULSE_TRUSTED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()],
        ALLOWED_ORIGINS=[origin.strip().rstrip("/") for origin in os.environ.get("PROJECTPULSE_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()],
        DATABASE=os.environ.get("PROJECTPULSE_DATABASE", str(Path(app.instance_path) / "projectpulse.sqlite3")),
    )
    if production and os.environ.get("PROJECTPULSE_COOKIE_SECURE", "1").lower() not in {"1", "true", "yes"}:
        raise RuntimeError("Secure session cookies cannot be disabled in production.")
    if test_config:
        app.config.update(test_config)

    @app.before_request
    def protect_state_changes():
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return None
        origin = request.headers.get("Origin")
        if origin:
            if origin.rstrip("/") not in current_app.config["ALLOWED_ORIGINS"]:
                return jsonify(error={"code": "origin_denied", "message": "Request origin is not allowed."}), 403
        elif request.headers.get("Sec-Fetch-Site") == "cross-site":
            return jsonify(error={"code": "origin_denied", "message": "Cross-site requests are not allowed."}), 403
        token = session.get("csrf_token")
        supplied = request.headers.get("X-CSRF-Token")
        if not token or not supplied or not secrets.compare_digest(token, supplied):
            return jsonify(error={"code": "csrf_failed", "message": "Refresh the page and try again."}), 403

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)

    # Import after get_db is defined to avoid circular imports in route modules.
    from app.api.auth import auth_api
    from app.api.analytics import analytics_api
    from app.api.organizations import organizations_api
    from app.api.projects import projects_api
    from app.api.tasks import tasks_api
    from app.api.workspaces import workspaces_api

    app.register_blueprint(auth_api)
    app.register_blueprint(analytics_api)
    app.register_blueprint(organizations_api)
    app.register_blueprint(workspaces_api)
    app.register_blueprint(projects_api)
    app.register_blueprint(tasks_api)

    @app.get("/api/v1/health")
    def health():
        try:
            get_db().execute("SELECT 1")
        except Exception:
            current_app.logger.exception("Health check database query failed")
            return jsonify(status="error", service="projectpulse-api"), 503
        return jsonify(status="ok", service="projectpulse-api")

    @app.get("/api/v1/csrf")
    def csrf_token():
        session.setdefault("csrf_token", secrets.token_urlsafe(32))
        return jsonify(token=session["csrf_token"])

    @app.cli.command("init-db")
    def init_db_command():
        init_db()
        print("Initialized ProjectPulse SQLite database.")

    return app
