import sqlite3
from datetime import date
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
        SELECT id, project_id, parent_task_id, owner_user_id, name, description, status,
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
                project_id, parent_task_id, owner_user_id, name, description,
                duration_work_minutes, priority
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                parent_task_id,
                user_id,
                name.strip(),
                description,
                duration,
                priority,
            ),
        )
        db.execute("UPDATE projects SET version = version + 1 WHERE id = ?", (project_id,))
        db.commit()
    except sqlite3.IntegrityError:
        get_db().rollback()
        return jsonify(
            error={"code": "task_creation_failed", "message": "Could not create task."}
        ), 400

    task = get_db().execute(
        """
        SELECT id, project_id, parent_task_id, owner_user_id, name, description, status,
               duration_work_minutes, progress, priority, constraint_type,
               constraint_date, estimate_optimistic, estimate_most_likely,
               estimate_pessimistic, created_at, updated_at
        FROM tasks
        WHERE id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()

    return jsonify(task=dict(task)), 201


@tasks_api.patch("/api/v1/projects/<int:project_id>/tasks/<int:task_id>")
def update_task(project_id, task_id):
    user_id = session.get("user_id")
    if user_id is None:
        return jsonify(error={"code": "not_authenticated", "message": "Please log in."}), 401
    if not user_can_access_project(project_id, user_id):
        return jsonify(error={"code": "not_found", "message": "Project not found."}), 404
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify(error={"code": "invalid_json", "message": "Send task fields as a JSON object."}), 400
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ? AND project_id = ?", (task_id, project_id)).fetchone()
    if task is None:
        return jsonify(error={"code": "not_found", "message": "Task not found."}), 404

    allowed = {"name", "description", "status", "duration_work_minutes", "progress", "priority", "constraint_type", "constraint_date", "estimate_optimistic", "estimate_most_likely", "estimate_pessimistic", "owner_user_id"}
    if set(data) - allowed:
        return jsonify(error={"code": "unsupported_field", "message": "One or more task fields cannot be updated."}), 400
    updates = {}
    if "name" in data:
        value = data["name"]
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 200:
            return jsonify(error={"code": "invalid_name", "message": "Task name is required (200 characters max)."}), 400
        updates["name"] = value.strip()
    if "description" in data:
        if not isinstance(data["description"], str):
            return jsonify(error={"code": "invalid_description", "message": "Description must be text."}), 400
        updates["description"] = data["description"]
    if "status" in data:
        if data["status"] not in ("not_started", "in_progress", "blocked", "completed"):
            return jsonify(error={"code": "invalid_status", "message": "Choose not_started, in_progress, blocked, or completed."}), 400
        updates["status"] = data["status"]
    if "duration_work_minutes" in data:
        value = data["duration_work_minutes"]
        if type(value) is not int or value < 0:
            return jsonify(error={"code": "invalid_duration", "message": "Duration must be non-negative working minutes."}), 400
        updates["duration_work_minutes"] = value
    if "progress" in data:
        value = data["progress"]
        if type(value) is not int or not 0 <= value <= 100:
            return jsonify(error={"code": "invalid_progress", "message": "Progress must be an integer from 0 to 100."}), 400
        updates["progress"] = value
    if "priority" in data:
        value = data["priority"]
        if type(value) is not int or not 1 <= value <= 5:
            return jsonify(error={"code": "invalid_priority", "message": "Priority must be an integer from 1 to 5."}), 400
        updates["priority"] = value
    if "owner_user_id" in data:
        value=data["owner_user_id"]
        if value is not None:
            if type(value) is not int:return jsonify(error={"code":"invalid_owner","message":"Choose a member of this workspace."}),400
            valid=db.execute("SELECT 1 FROM projects p JOIN workspaces w ON w.id=p.workspace_id JOIN organization_memberships m ON m.organization_id=w.organization_id WHERE p.id=? AND m.user_id=?",(project_id,value)).fetchone()
            if not valid:return jsonify(error={"code":"invalid_owner","message":"Choose a member of this workspace."}),400
        updates["owner_user_id"]=value
    if "constraint_type" in data:
        value = data["constraint_type"]
        allowed_constraints = ("none", "start_no_earlier_than", "start_no_later_than", "must_start_on", "finish_no_earlier_than", "finish_no_later_than", "must_finish_on")
        if value not in allowed_constraints:
            return jsonify(error={"code": "invalid_constraint", "message": "Unsupported task constraint."}), 400
        updates["constraint_type"] = value
    if "constraint_date" in data:
        value = data["constraint_date"]
        if value not in (None, ""):
            if not isinstance(value, str):
                return jsonify(error={"code": "invalid_constraint_date", "message": "Constraint date must use YYYY-MM-DD."}), 400
            try:
                date.fromisoformat(value)
            except ValueError:
                return jsonify(error={"code": "invalid_constraint_date", "message": "Constraint date must use YYYY-MM-DD."}), 400
        updates["constraint_date"] = value or None
    estimates = ("estimate_optimistic", "estimate_most_likely", "estimate_pessimistic")
    if any(field in data for field in estimates):
        values = [data.get(field, task[field]) for field in estimates]
        if all(value is None for value in values):
            updates.update({field: None for field in estimates})
        elif any(type(value) is not int or value < 0 for value in values) or not values[0] <= values[1] <= values[2]:
            return jsonify(error={"code": "invalid_estimates", "message": "Provide optimistic, most likely, and pessimistic estimates in ascending order."}), 400
        else:
            updates.update(dict(zip(estimates, values)))
    if not updates:
        return jsonify(error={"code": "empty_update", "message": "Include a supported task field to update."}), 400

    assignments = ", ".join(f"{field} = ?" for field in updates)
    try:
        previous_owner=task["owner_user_id"]
        db.execute(f"UPDATE tasks SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND project_id = ?", [*updates.values(), task_id, project_id])  # nosec B608 — assignment columns are built from validated update fields.
        if "owner_user_id" in updates and updates["owner_user_id"] and updates["owner_user_id"] != previous_owner:
            db.execute("INSERT INTO notifications(user_id,project_id,task_id,kind,message) VALUES(?,?,?,'task_assigned',?)",(updates["owner_user_id"],project_id,task_id,f"You were assigned to {task['name']}"))
        db.execute("UPDATE projects SET version = version + 1 WHERE id = ?", (project_id,))
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify(error={"code": "task_update_failed", "message": "Could not update this task."}), 400
    updated = db.execute(
        """SELECT id, project_id, parent_task_id, owner_user_id, name, description, status,
                  duration_work_minutes, progress, priority, constraint_type,
                  constraint_date, estimate_optimistic, estimate_most_likely,
                  estimate_pessimistic, created_at, updated_at
           FROM tasks WHERE id = ? AND project_id = ?""",
        (task_id, project_id),
    ).fetchone()
    return jsonify(task=dict(updated)), 200
