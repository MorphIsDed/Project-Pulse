import sqlite3
from datetime import date
from flask import Blueprint, jsonify, request, session
from app import get_db


projects_api = Blueprint("projects_api", __name__)


def get_workspace_membership(workspace_id: int, user_id: int):
    return get_db().execute(
        """
        SELECT m.role
        FROM workspaces AS w
        JOIN organization_memberships AS m
          ON m.organization_id = w.organization_id
        WHERE w.id = ? AND m.user_id = ?
        """,
        (workspace_id, user_id),
    ).fetchone()


@projects_api.get("/api/v1/workspaces/<int:workspace_id>/projects")
def list_projects(workspace_id):
    user_id = session.get("user_id")

    if user_id is None:
        return jsonify(
            error={"code": "not_authenticated", "message": "Please log in."}
        ), 401

    if get_workspace_membership(workspace_id, user_id) is None:
        return jsonify(
            error={"code": "not_found", "message": "Workspace not found."}
        ), 404

    rows = get_db().execute(
        """
        SELECT id, workspace_id, name, status, start_date, target_finish,
               version, created_by, created_at, updated_at
        FROM projects
        WHERE workspace_id = ?
        ORDER BY name
        """,
        (workspace_id,),
    ).fetchall()

    return jsonify(
        projects=[
            {
                "id": row["id"],
                "workspace_id": row["workspace_id"],
                "name": row["name"],
                "status": row["status"],
                "start_date": row["start_date"],
                "target_finish": row["target_finish"],
                "version": row["version"],
                "created_by": row["created_by"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]
    ), 200


@projects_api.post("/api/v1/workspaces/<int:workspace_id>/projects")
def create_project(workspace_id):
    user_id = session.get("user_id")

    if user_id is None:
        return jsonify(
            error={"code": "not_authenticated", "message": "Please log in."}
        ), 401

    membership = get_workspace_membership(workspace_id, user_id)

    if membership is None:
        return jsonify(
            error={"code": "not_found", "message": "Workspace not found."}
        ), 404

    if membership["role"] not in ("owner", "admin"):
        return jsonify(
            error={"code": "forbidden", "message": "Only owners and admins can create projects."}
        ), 403

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify(
            error={"code": "invalid_json", "message": "Send a JSON object."}
        ), 400

    name = data.get("name")

    if not isinstance(name, str) or not name.strip():
        return jsonify(
            error={"code": "invalid_name", "message": "Project name is required."}
        ), 400

    name = name.strip()

    if len(name) > 120:
        return jsonify(
            error={"code": "invalid_name", "message": "Name must be 120 characters or fewer."}
        ), 400

    db = get_db()

    try:
        cursor = db.execute(
            """
            INSERT INTO projects (workspace_id, name, created_by)
            VALUES (?, ?, ?)
            """,
            (workspace_id, name, user_id),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify(
            error={
                "code": "project_conflict",
                "message": "A project with that name may already exist in this workspace.",
            }
        ), 409

    return jsonify(
        project={
            "id": cursor.lastrowid,
            "workspace_id": workspace_id,
            "name": name,
            "status": "active",
            "start_date": None,
            "target_finish": None,
            "version": 1,
            "created_by": user_id,
        }
    ), 201


@projects_api.patch("/api/v1/projects/<int:project_id>")
def update_project(project_id):
    user_id = session.get("user_id")
    if user_id is None:
        return jsonify(error={"code": "not_authenticated", "message": "Please log in."}), 401

    row = get_db().execute(
        """SELECT p.*, m.role FROM projects p
           JOIN workspaces w ON w.id = p.workspace_id
           JOIN organization_memberships m ON m.organization_id = w.organization_id
           WHERE p.id = ? AND m.user_id = ?""",
        (project_id, user_id),
    ).fetchone()
    if row is None:
        return jsonify(error={"code": "not_found", "message": "Project not found."}), 404
    if row["role"] not in ("owner", "admin"):
        return jsonify(error={"code": "forbidden", "message": "Only owners and admins can update project settings."}), 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify(error={"code": "invalid_json", "message": "Send project fields as a JSON object."}), 400
    expected_version = data.pop("version", None)
    if expected_version is not None and (type(expected_version) is not int or expected_version != row["version"]):
        return jsonify(error={"code": "stale_project", "message": "The project changed since it was loaded. Refresh and try again."}), 409

    updates = {}
    if "name" in data:
        name = data["name"]
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
            return jsonify(error={"code": "invalid_name", "message": "Project name is required (120 characters max)."}), 400
        updates["name"] = name.strip()
    if "status" in data:
        if data["status"] not in ("active", "on_hold", "completed", "archived"):
            return jsonify(error={"code": "invalid_status", "message": "Choose active, on_hold, completed, or archived."}), 400
        updates["status"] = data["status"]
    for field in ("start_date", "target_finish"):
        if field in data:
            value = data[field]
            if value in (None, ""):
                updates[field] = None
            elif not isinstance(value, str):
                return jsonify(error={"code": "invalid_date", "message": f"{field} must be an ISO date."}), 400
            else:
                try:
                    date.fromisoformat(value)
                except ValueError:
                    return jsonify(error={"code": "invalid_date", "message": f"{field} must use YYYY-MM-DD."}), 400
                updates[field] = value
    if not updates:
        return jsonify(error={"code": "empty_update", "message": "Include a supported project field to update."}), 400
    if updates.get("start_date", row["start_date"]) and updates.get("target_finish", row["target_finish"]):
        if updates.get("target_finish", row["target_finish"]) < updates.get("start_date", row["start_date"]):
            return jsonify(error={"code": "invalid_date_range", "message": "Target finish must be on or after the project start date."}), 400

    assignments = ", ".join(f"{field} = ?" for field in updates)
    values = list(updates.values())
    values.extend((project_id, row["version"]))
    cursor = get_db().execute(
        f"UPDATE projects SET {assignments}, version = version + 1 WHERE id = ? AND version = ?",
        values,
    )
    if cursor.rowcount == 0:
        get_db().rollback()
        return jsonify(error={"code": "stale_project", "message": "The project changed since it was loaded. Refresh and try again."}), 409
    get_db().commit()
    updated = get_db().execute(
        "SELECT id, workspace_id, name, status, start_date, target_finish, version, created_at, updated_at FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()
    return jsonify(project=dict(updated)), 200
