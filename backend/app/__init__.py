from pathlib import Path
import os
import sqlite3
import secrets
from urllib.parse import urlparse

from flask import Flask, current_app, g, jsonify, request, session
from sqlalchemy import text
from sqlalchemy.engine import make_url
from werkzeug.middleware.proxy_fix import ProxyFix
from app.config import get_config
from app.extensions import db, login_manager, migrate


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        database_path = Path(current_app.config["DATABASE"])
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
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
            email_verified_at TEXT,
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
            owner_user_id INTEGER,
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
            FOREIGN KEY (owner_user_id)
                REFERENCES users(id) ON DELETE SET NULL,
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

    user_columns = {row["name"] for row in db.execute("PRAGMA table_info(users)")}
    if "email_verified_at" not in user_columns:
        db.execute("ALTER TABLE users ADD COLUMN email_verified_at TEXT")
        db.execute("UPDATE users SET email_verified_at = created_at WHERE email_verified_at IS NULL")
    task_columns = {row["name"] for row in db.execute("PRAGMA table_info(tasks)")}
    if "owner_user_id" not in task_columns:
        db.execute("ALTER TABLE tasks ADD COLUMN owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")

    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS account_tokens (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('email_verification', 'password_reset')),
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_account_tokens_user_kind ON account_tokens(user_id, kind);

        CREATE TABLE IF NOT EXISTS auth_rate_limits (
            bucket_key TEXT PRIMARY KEY,
            window_started INTEGER NOT NULL,
            attempts INTEGER NOT NULL,
            blocked_until INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS workspace_invitations (
            id INTEGER PRIMARY KEY,
            organization_id INTEGER NOT NULL,
            email TEXT NOT NULL COLLATE NOCASE,
            role TEXT NOT NULL CHECK (role IN ('admin', 'member')),
            token_hash TEXT NOT NULL UNIQUE,
            invited_by INTEGER,
            expires_at TEXT NOT NULL,
            accepted_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
            FOREIGN KEY (invited_by) REFERENCES users(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_invitations_org_email ON workspace_invitations(organization_id, email);

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            organization_id INTEGER,
            project_id INTEGER,
            task_id INTEGER,
            kind TEXT NOT NULL,
            message TEXT NOT NULL,
            read_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_notifications_user_created ON notifications(user_id, created_at);
        INSERT OR IGNORE INTO schema_meta(version) VALUES (3);
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


def create_app(config_name: str | dict | None = None, test_config: dict | None = None) -> Flask:
    if isinstance(config_name, dict):
        test_config, config_name = config_name, None
    app = Flask(__name__, instance_relative_config=True)
    selected_environment = (config_name or os.environ.get("APP_ENV") or os.environ.get("PROJECTPULSE_ENV") or "development")
    production = str(selected_environment).lower() == "production"
    test_mode = bool(test_config and test_config.get("TESTING"))
    config_class = get_config(str(selected_environment))
    app.config.from_object(config_class)
    secret_key = os.environ.get("PROJECTPULSE_SECRET_KEY") or app.config.get("SECRET_KEY")
    if test_config:
        secret_key = test_config.get("SECRET_KEY", secret_key)
    if production and not test_mode and not secret_key:
        raise RuntimeError("PROJECTPULSE_SECRET_KEY must be set in production.")
    if production and not test_mode and (
        len(secret_key) < 32
        or secret_key.lower().startswith(("replace-", "change-me", "your-"))
    ):
        raise RuntimeError(
            "PROJECTPULSE_SECRET_KEY must be a unique random value of at least 32 characters."
        )
    if production and not test_mode and (not os.environ.get("PROJECTPULSE_TRUSTED_HOSTS") or not os.environ.get("PROJECTPULSE_ALLOWED_ORIGINS")):
        raise RuntimeError("PROJECTPULSE_TRUSTED_HOSTS and PROJECTPULSE_ALLOWED_ORIGINS must be set in production.")
    privacy_config = {
        "PROJECTPULSE_OPERATOR_NAME": "OPERATOR_NAME",
        "PROJECTPULSE_SUPPORT_EMAIL": "SUPPORT_EMAIL",
        "PROJECTPULSE_HOSTING_LOCATION": "HOSTING_LOCATION",
        "PROJECTPULSE_RETENTION_PERIOD": "RETENTION_PERIOD",
        "PROJECTPULSE_DELETION_PROCESS": "DELETION_PROCESS",
    }
    missing_privacy = [
        variable for variable in privacy_config
        if not os.environ.get(variable)
        or os.environ[variable].strip().lower().startswith(("set-", "replace-", "todo"))
    ]
    if production and not test_mode and missing_privacy:
        raise RuntimeError("Production legal/contact settings are required: " + ", ".join(missing_privacy))
    mail_host = os.environ.get("PROJECTPULSE_MAIL_HOST")
    mail_from = os.environ.get("PROJECTPULSE_MAIL_FROM")
    if production and not test_mode and (mail_host or "").lower().startswith(("smtp.example", "example.")):
        raise RuntimeError("Configure a real SMTP host before production startup.")
    if production and not test_mode and "example.com" in (mail_from or "").lower():
        raise RuntimeError("Configure a real sender address before production startup.")
    if production and not test_mode and (not mail_host or not mail_from):
        raise RuntimeError("PROJECTPULSE_MAIL_HOST and PROJECTPULSE_MAIL_FROM are required in production for account verification and recovery.")
    app.config.from_mapping(
        SECRET_KEY=secret_key or "local-development-secret-not-for-deployment",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=production,
        PREFERRED_URL_SCHEME="https" if production else "http",
        TRUSTED_HOSTS=[host.strip() for host in os.environ.get("PROJECTPULSE_TRUSTED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()],
        ALLOWED_ORIGINS=[origin.strip().rstrip("/") for origin in os.environ.get("PROJECTPULSE_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()],
        DATABASE=os.environ.get("PROJECTPULSE_DATABASE", str(Path(app.instance_path) / "projectpulse.sqlite3")),
        PRODUCTION=production,
        PUBLIC_URL=os.environ.get("PROJECTPULSE_PUBLIC_URL", "http://localhost:5173").rstrip("/"),
        MAIL_HOST=mail_host,
        MAIL_PORT=int(os.environ.get("PROJECTPULSE_MAIL_PORT", "587")),
        MAIL_FROM=mail_from,
        MAIL_USERNAME=os.environ.get("PROJECTPULSE_MAIL_USERNAME"),
        MAIL_PASSWORD=os.environ.get("PROJECTPULSE_MAIL_PASSWORD"),
        MAIL_USE_TLS=os.environ.get("PROJECTPULSE_MAIL_USE_TLS", "1").lower() in {"1", "true", "yes"},
        SENTRY_DSN=os.environ.get("PROJECTPULSE_SENTRY_DSN", ""),
        OPERATOR_NAME=os.environ.get("PROJECTPULSE_OPERATOR_NAME", "ProjectPulse operator"),
        SUPPORT_EMAIL=os.environ.get("PROJECTPULSE_SUPPORT_EMAIL", ""),
        HOSTING_LOCATION=os.environ.get("PROJECTPULSE_HOSTING_LOCATION", "Not specified"),
        RETENTION_PERIOD=os.environ.get("PROJECTPULSE_RETENTION_PERIOD", "Not specified"),
        DELETION_PROCESS=os.environ.get("PROJECTPULSE_DELETION_PROCESS", "Contact support to request deletion."),
    )
    if production and not test_mode and os.environ.get("PROJECTPULSE_COOKIE_SECURE", "1").lower() not in {"1", "true", "yes"}:
        raise RuntimeError("Secure session cookies cannot be disabled in production.")
    if test_config:
        app.config.update(test_config)

    if test_config and test_config.get("SQLALCHEMY_DATABASE_URI", "").startswith("sqlite:"):
        db_path = make_url(test_config["SQLALCHEMY_DATABASE_URI"]).database
        if db_path and db_path != ":memory:":
            app.config["DATABASE"] = db_path
        else:
            app.config["DATABASE"] = ":memory:"
    elif os.environ.get("PROJECTPULSE_DATABASE"):
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.environ["PROJECTPULSE_DATABASE"].replace("\\", "/")
    elif not os.environ.get("DATABASE_URL"):
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + app.config["DATABASE"].replace("\\", "/")

    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    from app.models import user as _user_model  # noqa: F401
    from app.models.user import User
    login_manager.init_app(app)
    login_manager.login_view = None

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    from app.cli import register_cli
    from app.errors import register_error_handlers
    from app.request_context import register_request_context
    register_error_handlers(app)
    register_request_context(app)
    register_cli(app)

    if production:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    if app.config.get("SENTRY_DSN"):
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        sentry_sdk.init(dsn=app.config["SENTRY_DSN"], integrations=[FlaskIntegration()], traces_sample_rate=0.0, send_default_pii=False)

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
        if not current_app.config.get("WTF_CSRF_ENABLED", True):
            return None
        token = session.get("csrf_token")
        supplied = request.headers.get("X-CSRF-Token") or request.headers.get("X-CSRFToken")
        if not token or not supplied or not secrets.compare_digest(token, supplied):
            return jsonify(error={"code": "csrf_error", "message": "Refresh the page and try again."}), 400

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)
    if app.config.get("TESTING"):
        with app.app_context():
            db.create_all()
            init_db()

    # Import after get_db is defined to avoid circular imports in route modules.
    from app.api.auth import auth_api
    from app.api.analytics import analytics_api
    from app.api.organizations import organizations_api
    from app.api.projects import projects_api
    from app.api.tasks import tasks_api
    from app.api.workspaces import workspaces_api
    from app.api.accounts import accounts_api
    from app.api.invitations import invitations_api
    from app.api.notifications import notifications_api
    from app.api.calendars import calendars_api

    app.register_blueprint(auth_api)
    app.register_blueprint(analytics_api)
    app.register_blueprint(organizations_api)
    app.register_blueprint(workspaces_api)
    app.register_blueprint(projects_api)
    app.register_blueprint(tasks_api)
    app.register_blueprint(accounts_api)
    app.register_blueprint(invitations_api)
    app.register_blueprint(notifications_api)
    app.register_blueprint(calendars_api)

    @app.get("/api/v1/legal")
    def legal_information():
        return jsonify(
            operator=current_app.config["OPERATOR_NAME"],
            support_email=current_app.config["SUPPORT_EMAIL"],
            hosting_location=current_app.config["HOSTING_LOCATION"],
            retention_period=current_app.config["RETENTION_PERIOD"],
            deletion_process=current_app.config["DELETION_PROCESS"],
        )

    @app.get("/api/v1/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Health check database query failed")
            return jsonify(status="degraded", service="projectpulse-api", database="unavailable"), 503
        return jsonify(status="ok", service="projectpulse-api", database="ok")

    @app.get("/api/v1/csrf")
    @app.get("/api/v1/auth/csrf")
    def csrf_token():
        session.setdefault("csrf_token", secrets.token_urlsafe(32))
        return jsonify(token=session["csrf_token"], csrf_token=session["csrf_token"])

    @app.cli.command("init-db")
    def init_db_command():
        db.create_all()
        init_db()
        print("Initialized ProjectPulse SQLite database.")

    return app
