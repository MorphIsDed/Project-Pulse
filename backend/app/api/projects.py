import sqlite3
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
        SELECT id, workspace_id, name, status, created_by, created_at
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
                "created_by": row["created_by"],
                "created_at": row["created_at"],
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
            "created_by": user_id,
        }
    ), 201