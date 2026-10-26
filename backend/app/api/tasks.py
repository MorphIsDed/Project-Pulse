import sqlite3
from flask import Blueprint, jsonify, request, session
from app import get_db


tasks_api = Blueprint("tasks_api", __name__)


def user_can_access_project(project_id: int, user_id: int) -> bool:
    row = get_db().execute(
        """
        SELECT 1
        FROM projects AS p
        JOIN workspaces AS w ON w.id = p.workspace_id
        JOIN organization_memberships AS m
          ON m.organization_id = w.organization_id
        WHERE p.id = ? AND m.user_id = ?
        """,
        (project_id, user_id),
    ).fetchone()

    return row is not None


@tasks_api.get("/api/v1/projects/<int:project_id>/tasks")
def list_tasks(project_id):
    user_id = session.get("user_id")

    if user_id is None:
        return jsonify(
            error={"code": "not_authenticated", "message": "Please log in."}
        ), 401

    if not user_can_access_project(project_id, user_id):
        return jsonify(
            error={"code": "not_found", "message": "Project not found."}
        ), 404

    rows = get_db().execute(
        """
        SELECT id, project_id, parent_task_id, name, description, status,
               duration_work_minutes, progress, priority, constraint_type,
               constraint_date, estimate_optimistic, estimate_most_likely,
               estimate_pessimistic, created_at, updated_at
        FROM tasks
        WHERE project_id = ?
        ORDER BY id
        """,
        (project_id,),
    ).fetchall()

    return jsonify(
        tasks=[dict(row) for row in rows]
    ), 200


@tasks_api.post("/api/v1/projects/<int:project_id>/tasks")
def create_task(project_id):
    user_id = session.get("user_id")

    if user_id is None:
        return jsonify(
            error={"code": "not_authenticated", "message": "Please log in."}
        ), 401

    if not user_can_access_project(project_id, user_id):
        return jsonify(
            error={"code": "not_found", "message": "Project not found."}
        ), 404

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify(
            error={"code": "invalid_json", "message": "Send a JSON object."}
        ), 400

    name = data.get("name")
    description = data.get("description", "")
    duration = data.get("duration_work_minutes", 0)
    priority = data.get("priority", 3)
    parent_task_id = data.get("parent_task_id")

    if not isinstance(name, str) or not name.strip():
        return jsonify(
            error={"code": "invalid_name", "message": "Task name is required."}
        ), 400

    if not isinstance(description, str):
        return jsonify(
            error={"code": "invalid_description", "message": "Description must be text."}
        ), 400

    if type(duration) is not int or duration < 0:
        return jsonify(
            error={
                "code": "invalid_duration",
                "message": "Duration must be a non-negative integer in working minutes.",
            }
        ), 400

    if type(priority) is not int or not 1 <= priority <= 5:
        return jsonify(
            error={"code": "invalid_priority", "message": "Priority must be an integer from 1 to 5."}
        ), 400

    if parent_task_id is not None:
        if type(parent_task_id) is not int:
            return jsonify(
                error={"code": "invalid_parent", "message": "Parent task ID must be an integer."}
            ), 400

        parent = get_db().execute(
            "SELECT id FROM tasks WHERE id = ? AND project_id = ?",
            (parent_task_id, project_id),
        ).fetchone()

        if parent is None:
            return jsonify(
                error={
                    "code": "invalid_parent",
                    "message": "Parent task must belong to this project.",
                }
            ), 400

    try:
        db = get_db()
        cursor = db.execute(
            """
            INSERT INTO tasks (
                project_id, parent_task_id, name, description,
                duration_work_minutes, priority
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                parent_task_id,
                name.strip(),
                description,
                duration,
                priority,
            ),
        )
        db.commit()
    except sqlite3.IntegrityError:
        get_db().rollback()
        return jsonify(
            error={"code": "task_creation_failed", "message": "Could not create task."}
        ), 400

    task = get_db().execute(
        """
        SELECT id, project_id, parent_task_id, name, description, status,
               duration_work_minutes, progress, priority, constraint_type,
               constraint_date, estimate_optimistic, estimate_most_likely,
               estimate_pessimistic, created_at, updated_at
        FROM tasks
        WHERE id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()

    return jsonify(task=dict(task)), 201