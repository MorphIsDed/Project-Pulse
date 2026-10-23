from pathlib import Path
import sqlite3

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
        """
    )
    get_db().commit()
    
