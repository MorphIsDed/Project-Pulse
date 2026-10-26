from pathlib import Path
import sqlite3
from app.api.auth import auth_api
from flask import Flask, jsonify, current_app, g


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
    get_db().executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT OR IGNORE INTO schema_meta(version) VALUES (1);
        """
    )
    get_db().commit()


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="development-only-change-me",
        DATABASE=str(Path(app.instance_path) / "projectpulse.sqlite3"),
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)
    app.register_blueprint(auth_api)
    app.register_blueprint(organizations_api)
    app.register_blueprint(workspaces_api)
    app.register_blueprint(projects_api)
    app.register_blueprint(tasks_api)

    @app.get("/api/v1/health")
    def health():
        return jsonify(status="ok", service="projectpulse-api")

    @app.cli.command("init-db")
    def init_db_command():
        init_db()
        print("Initialized ProjectPulse SQLite database.")

    return app

def init_db() -> None:
    get_db().executescript(
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
            role TEXT NOT NULL
                CHECK (role IN ('owner', 'admin', 'member')),
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
            created_by INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            UNIQUE (workspace_id, name),

            FOREIGN KEY (workspace_id)
                REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by)
                REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_memberships_user
            ON organization_memberships(user_id);

        CREATE INDEX IF NOT EXISTS idx_workspaces_organization
            ON workspaces(organization_id);

        CREATE INDEX IF NOT EXISTS idx_projects_workspace
            ON projects(workspace_id);
            
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

            CHECK (
                (estimate_optimistic IS NULL
                AND estimate_most_likely IS NULL
                AND estimate_pessimistic IS NULL)
                OR
                (estimate_optimistic >= 0
                AND estimate_most_likely >= estimate_optimistic
                AND estimate_pessimistic >= estimate_most_likely)
            ),
            CHECK (parent_task_id IS NULL OR parent_task_id != id)
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_project
            ON tasks(project_id);

        CREATE INDEX IF NOT EXISTS idx_tasks_parent
            ON tasks(parent_task_id);
            
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

        CREATE INDEX IF NOT EXISTS idx_dependencies_predecessor
            ON dependencies(predecessor_task_id);

        CREATE INDEX IF NOT EXISTS idx_dependencies_successor
            ON dependencies(successor_task_id);
        """
    )
    get_db().commit()
    
