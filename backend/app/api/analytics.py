"""Project scheduling, resource, and task-insight API routes.

The first schedule implementation uses a weekday calendar with an eight-hour
workday. Dates and dependency constraints are returned as derived values; task
inputs remain unchanged.
"""

from collections import defaultdict, deque
from datetime import date, datetime, time, timedelta
import math
import sqlite3

from flask import Blueprint, jsonify, request, session

from app import get_db

analytics_api = Blueprint("analytics_api", __name__)
WORKDAY_MINUTES = 480


def _bump_project_version(project_id: int) -> None:
    get_db().execute("UPDATE projects SET version = version + 1 WHERE id = ?", (project_id,))


def _project_or_error(project_id: int):
    user_id = session.get("user_id")
    if user_id is None:
        return None, (jsonify(error={"code": "not_authenticated", "message": "Please log in."}), 401)
    project = get_db().execute(
        """SELECT p.* FROM projects p
           JOIN workspaces w ON w.id = p.workspace_id
           JOIN organization_memberships m ON m.organization_id = w.organization_id
           WHERE p.id = ? AND m.user_id = ?""",
        (project_id, user_id),
    ).fetchone()
    if project is None:
        return None, (jsonify(error={"code": "not_found", "message": "Project not found."}), 404)
    return (project, user_id), None


def _date_add_workdays(start: date, days: int) -> date:
    cursor = start
    direction = 1 if days >= 0 else -1
    remaining = abs(days)
    while remaining:
        cursor += timedelta(days=direction)
        if cursor.weekday() < 5:
            remaining -= 1
    return cursor


def _workday_distance(start: date, finish: date) -> int:
    direction = 1 if finish >= start else -1
    cursor = start
    count = 0
    while cursor != finish:
        if cursor.weekday() < 5:
            count += direction
        cursor += timedelta(days=direction)
    return count


def _offset_datetime(start: date, work_minutes: int) -> datetime:
    """Move from 09:00 on a weekday, skipping weekends and 17:00-09:00."""
    cursor = datetime.combine(start, time(9, 0))
    direction = 1 if work_minutes >= 0 else -1
    remaining = abs(work_minutes)
    while remaining:
        if direction > 0:
            if cursor.weekday() >= 5:
                cursor = datetime.combine(_date_add_workdays(cursor.date(), 1), time(9, 0))
            end = datetime.combine(cursor.date(), time(17, 0))
            if cursor >= end:
                cursor = datetime.combine(_date_add_workdays(cursor.date(), 1), time(9, 0))
                continue
            available = int((end - cursor).total_seconds() // 60)
            step = min(remaining, available)
            cursor += timedelta(minutes=step)
        else:
            if cursor.weekday() >= 5:
                cursor = datetime.combine(_date_add_workdays(cursor.date(), -1), time(17, 0))
            start_of_day = datetime.combine(cursor.date(), time(9, 0))
            if cursor <= start_of_day:
                cursor = datetime.combine(_date_add_workdays(cursor.date(), -1), time(17, 0))
                continue
            available = int((cursor - start_of_day).total_seconds() // 60)
            step = min(remaining, available)
            cursor -= timedelta(minutes=step)
        remaining -= step
    return cursor


def _work_minutes_to_deadline(start: date, target_finish: date) -> int:
    if target_finish < start:
        return -1
    return _workday_distance(start, target_finish + timedelta(days=1)) * WORKDAY_MINUTES


def _workday_start_offset(start: date, target: date) -> int:
    if target.weekday() >= 5:
        raise ValueError("Task date constraints must fall on a weekday.")
    return _workday_distance(start, target) * WORKDAY_MINUTES


def _schedule(project_id: int, start_override: str | None = None):
    db = get_db()
    project = db.execute("SELECT start_date, target_finish, version FROM projects WHERE id = ?", (project_id,)).fetchone()
    start_text = start_override or project["start_date"] or date.today().isoformat()
    try:
        project_start = date.fromisoformat(start_text)
    except (TypeError, ValueError):
        raise ValueError("Project start must be an ISO date (YYYY-MM-DD).")
    if project_start.weekday() >= 5:
        project_start = _date_add_workdays(project_start, 1)

    tasks = [dict(row) for row in db.execute(
        "SELECT id, name, status, duration_work_minutes, progress, priority, constraint_type, constraint_date FROM tasks WHERE project_id = ? ORDER BY id",
        (project_id,),
    ).fetchall()]
    dependencies = [dict(row) for row in db.execute(
        "SELECT id, predecessor_task_id, successor_task_id, type, lag_work_minutes FROM dependencies WHERE project_id = ? ORDER BY id",
        (project_id,),
    ).fetchall()]
    by_id = {task["id"]: task for task in tasks}
    outgoing: dict[int, list[dict]] = defaultdict(list)
    incoming: dict[int, list[dict]] = defaultdict(list)
    indegree = {task["id"]: 0 for task in tasks}
    for dependency in dependencies:
        if dependency["predecessor_task_id"] not in by_id or dependency["successor_task_id"] not in by_id:
            continue
        outgoing[dependency["predecessor_task_id"]].append(dependency)
        incoming[dependency["successor_task_id"]].append(dependency)
        indegree[dependency["successor_task_id"]] += 1
    ready = deque(task["id"] for task in tasks if indegree[task["id"]] == 0)
    order = []
    while ready:
        task_id = ready.popleft()
        order.append(task_id)
        for dependency in outgoing[task_id]:
            successor = dependency["successor_task_id"]
            indegree[successor] -= 1
            if indegree[successor] == 0:
                ready.append(successor)
    if len(order) != len(tasks):
        raise ValueError("The project dependencies contain a cycle. Remove a dependency before calculating the schedule.")

    duration = {task["id"]: task["duration_work_minutes"] for task in tasks}
    constraints = {}
    for task in tasks:
        kind = task["constraint_type"]
        if kind == "none":
            continue
        if not task["constraint_date"]:
            raise ValueError(f"Task '{task['name']}' has a date constraint without a constraint date.")
        try:
            constraint_date = date.fromisoformat(task["constraint_date"])
        except ValueError:
            raise ValueError(f"Task '{task['name']}' has an invalid constraint date.")
        start_offset = _workday_start_offset(project_start, constraint_date)
        finish_offset = _work_minutes_to_deadline(project_start, constraint_date)
        constraints[task["id"]] = (kind, start_offset, finish_offset)
    early_start: dict[int, int] = {}
    early_finish: dict[int, int] = {}
    for task_id in order:
        start_bound = 0
        for dependency in incoming[task_id]:
            predecessor = dependency["predecessor_task_id"]
            lag = dependency["lag_work_minutes"]
            relation = dependency["type"]
            if relation == "FS":
                bound = early_finish[predecessor] + lag
            elif relation == "SS":
                bound = early_start[predecessor] + lag
            elif relation == "FF":
                bound = early_finish[predecessor] + lag - duration[task_id]
            else:  # SF
                bound = early_start[predecessor] + lag - duration[task_id]
            start_bound = max(start_bound, bound)
        task_constraint = constraints.get(task_id)
        if task_constraint:
            kind, start_offset, finish_offset = task_constraint
            if kind == "start_no_earlier_than":
                start_bound = max(start_bound, start_offset)
            elif kind == "finish_no_earlier_than":
                start_bound = max(start_bound, finish_offset - duration[task_id])
            elif kind == "must_start_on":
                if start_bound > start_offset:
                    raise ValueError(f"Task '{by_id[task_id]['name']}' cannot meet its required start date.")
                start_bound = start_offset
            elif kind == "must_finish_on":
                fixed_start = finish_offset - duration[task_id]
                if start_bound > fixed_start:
                    raise ValueError(f"Task '{by_id[task_id]['name']}' cannot meet its required finish date.")
                start_bound = fixed_start
        early_start[task_id] = start_bound
        early_finish[task_id] = start_bound + duration[task_id]

    finish = max(early_finish.values(), default=0)
    backward_boundary = finish
    if project["target_finish"]:
        try:
            target_date = date.fromisoformat(project["target_finish"])
        except ValueError:
            raise ValueError("Project target finish must be an ISO date (YYYY-MM-DD).")
        backward_boundary = _work_minutes_to_deadline(project_start, target_date)
        if backward_boundary < finish:
            raise ValueError("The target finish is earlier than the calculated schedule finish.")
    late_finish = {task_id: backward_boundary for task_id in by_id}
    late_start = {task_id: backward_boundary - duration[task_id] for task_id in by_id}
    for task_id, (kind, start_offset, finish_offset) in constraints.items():
        if kind in ("start_no_later_than", "must_start_on"):
            late_finish[task_id] = min(late_finish[task_id], start_offset + duration[task_id])
        elif kind in ("finish_no_later_than", "must_finish_on"):
            late_finish[task_id] = min(late_finish[task_id], finish_offset)
        late_start[task_id] = late_finish[task_id] - duration[task_id]
    for task_id in reversed(order):
        for dependency in outgoing[task_id]:
            successor = dependency["successor_task_id"]
            lag = dependency["lag_work_minutes"]
            relation = dependency["type"]
            if relation == "FS":
                bound = late_start[successor] - lag
            elif relation == "SS":
                bound = late_start[successor] - lag + duration[task_id]
            elif relation == "FF":
                bound = late_finish[successor] - lag
            else:  # SF
                bound = late_finish[successor] - lag + duration[task_id]
            late_finish[task_id] = min(late_finish[task_id], bound)
        late_start[task_id] = late_finish[task_id] - duration[task_id]

    for task_id in by_id:
        if late_start[task_id] < early_start[task_id]:
            raise ValueError(f"Task '{by_id[task_id]['name']}' has conflicting date or dependency constraints.")
        constraint = constraints.get(task_id)
        if constraint and constraint[0] in ("start_no_later_than", "finish_no_later_than"):
            _, start_offset, finish_offset = constraint
            if constraint[0] == "start_no_later_than" and early_start[task_id] > start_offset:
                raise ValueError(f"Task '{by_id[task_id]['name']}' cannot meet its latest start date.")
            if constraint[0] == "finish_no_later_than" and early_finish[task_id] > finish_offset:
                raise ValueError(f"Task '{by_id[task_id]['name']}' cannot meet its latest finish date.")

    scheduled = []
    for task in tasks:
        task_id = task["id"]
        es, ef = early_start[task_id], early_finish[task_id]
        ls, lf = late_start[task_id], late_finish[task_id]
        early_start_at = _offset_datetime(project_start, es)
        early_finish_at = _offset_datetime(project_start, ef)
        late_start_at = _offset_datetime(project_start, ls)
        late_finish_at = _offset_datetime(project_start, lf)
        scheduled.append({
            **task,
            "early_start": early_start_at.date().isoformat(),
            "early_finish": early_finish_at.date().isoformat(),
            "early_start_at": early_start_at.isoformat(timespec="minutes"),
            "early_finish_at": early_finish_at.isoformat(timespec="minutes"),
            "late_start": late_start_at.date().isoformat(),
            "late_finish": late_finish_at.date().isoformat(),
            "late_start_at": late_start_at.isoformat(timespec="minutes"),
            "late_finish_at": late_finish_at.isoformat(timespec="minutes"),
            "total_float_work_minutes": max(0, ls - es),
            "critical": ls <= es,
            "duration_workdays": math.ceil(duration[task_id] / WORKDAY_MINUTES),
        })
    return {
        "project_id": project_id,
        "project_version": project["version"],
        "project_start": project_start.isoformat(),
        "start_source": "request" if start_override else "project" if project["start_date"] else "today_default",
        "target_finish": project["target_finish"],
        "project_finish": _offset_datetime(project_start, finish).date().isoformat(),
        "calendar": {"working_days": "Monday-Friday", "workday_start": "09:00", "workday_finish": "17:00", "minutes_per_day": WORKDAY_MINUTES, "holidays": "not configured"},
        "tasks": scheduled,
        "dependencies": dependencies,
    }


@analytics_api.get("/api/v1/projects/<int:project_id>/schedule")
def project_schedule(project_id):
    access, error = _project_or_error(project_id)
    if error:
        return error
    start = request.args.get("start")
    try:
        return jsonify(schedule=_schedule(project_id, start)), 200
    except ValueError as exc:
        return jsonify(error={"code": "invalid_schedule", "message": str(exc)}), 422


@analytics_api.get("/api/v1/projects/<int:project_id>/insights")
def project_insights(project_id):
    access, error = _project_or_error(project_id)
    if error:
        return error
    tasks = get_db().execute("SELECT status, progress, duration_work_minutes FROM tasks WHERE project_id = ?", (project_id,)).fetchall()
    total = len(tasks)
    counts = {status: sum(row["status"] == status for row in tasks) for status in ("not_started", "in_progress", "blocked", "completed")}
    try:
        schedule = _schedule(project_id)
    except ValueError as exc:
        return jsonify(error={"code": "invalid_schedule", "message": str(exc)}), 422
    return jsonify(insights={
        "project_id": project_id,
        "project_version": access[0]["version"],
        "total_tasks": total,
        "completed_tasks": counts["completed"],
        "average_progress": round(sum(row["progress"] for row in tasks) / total) if total else 0,
        "status_counts": counts,
        "estimated_work_minutes": sum(row["duration_work_minutes"] for row in tasks),
        "critical_tasks": [task["id"] for task in schedule["tasks"] if task["critical"]],
        "project_start": schedule["project_start"],
        "project_finish": schedule["project_finish"],
    }), 200


@analytics_api.get("/api/v1/projects/<int:project_id>/resources")
def list_resources(project_id):
    access, error = _project_or_error(project_id)
    if error:
        return error
    rows = get_db().execute(
        "SELECT id, project_id, name, resource_type, capacity_units, created_at FROM resources WHERE project_id = ? ORDER BY name",
        (project_id,),
    ).fetchall()
    return jsonify(resources=[dict(row) for row in rows]), 200


@analytics_api.post("/api/v1/projects/<int:project_id>/resources")
def create_resource(project_id):
    access, error = _project_or_error(project_id)
    if error:
        return error
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error={"code": "invalid_json", "message": "Send a JSON object."}), 400
    name = data.get("name")
    resource_type = data.get("resource_type", "person")
    capacity = data.get("capacity_units", 1)
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
        return jsonify(error={"code": "invalid_name", "message": "Resource name is required (120 characters max)."}), 400
    if resource_type not in ("person", "equipment", "other"):
        return jsonify(error={"code": "invalid_resource_type", "message": "Resource type must be person, equipment, or other."}), 400
    if isinstance(capacity, bool) or not isinstance(capacity, (int, float)) or capacity <= 0:
        return jsonify(error={"code": "invalid_capacity", "message": "Capacity must be a positive number of units."}), 400
    try:
        cursor = get_db().execute("INSERT INTO resources (project_id, name, resource_type, capacity_units) VALUES (?, ?, ?, ?)", (project_id, name.strip(), resource_type, capacity))
        _bump_project_version(project_id)
        get_db().commit()
    except sqlite3.IntegrityError:
        get_db().rollback()
        return jsonify(error={"code": "resource_conflict", "message": "A resource with that name already exists in this project."}), 409
    row = get_db().execute("SELECT id, project_id, name, resource_type, capacity_units, created_at FROM resources WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(resource=dict(row)), 201


@analytics_api.delete("/api/v1/projects/<int:project_id>/resources/<int:resource_id>")
def delete_resource(project_id, resource_id):
    access, error = _project_or_error(project_id)
    if error:
        return error
    cursor = get_db().execute("DELETE FROM resources WHERE id = ? AND project_id = ?", (resource_id, project_id))
    if cursor.rowcount == 0:
        return jsonify(error={"code": "not_found", "message": "Resource not found."}), 404
    _bump_project_version(project_id)
    get_db().commit()
    return "", 204


@analytics_api.get("/api/v1/projects/<int:project_id>/dependencies")
def list_dependencies(project_id):
    access, error = _project_or_error(project_id)
    if error:
        return error
    rows = get_db().execute(
        """SELECT d.id, d.project_id, d.predecessor_task_id, a.name AS predecessor_name,
                  d.successor_task_id, b.name AS successor_name, d.type, d.lag_work_minutes
           FROM dependencies d JOIN tasks a ON a.id = d.predecessor_task_id
           JOIN tasks b ON b.id = d.successor_task_id WHERE d.project_id = ? ORDER BY d.id""",
        (project_id,),
    ).fetchall()
    return jsonify(dependencies=[dict(row) for row in rows]), 200


@analytics_api.post("/api/v1/projects/<int:project_id>/dependencies")
def create_dependency(project_id):
    access, error = _project_or_error(project_id)
    if error:
        return error
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error={"code": "invalid_json", "message": "Send a JSON object."}), 400
    predecessor = data.get("predecessor_task_id")
    successor = data.get("successor_task_id")
    relation = data.get("type", "FS")
    lag = data.get("lag_work_minutes", 0)
    if type(predecessor) is not int or type(successor) is not int or predecessor == successor:
        return jsonify(error={"code": "invalid_tasks", "message": "Choose two different tasks in this project."}), 400
    if relation not in ("FS", "SS", "FF", "SF"):
        return jsonify(error={"code": "invalid_type", "message": "Dependency type must be FS, SS, FF, or SF."}), 400
    if type(lag) is not int:
        return jsonify(error={"code": "invalid_lag", "message": "Lag must be an integer number of working minutes."}), 400
    rows = get_db().execute("SELECT id FROM tasks WHERE project_id = ? AND id IN (?, ?)", (project_id, predecessor, successor)).fetchall()
    if len(rows) != 2:
        return jsonify(error={"code": "invalid_tasks", "message": "Both tasks must belong to this project."}), 400
    try:
        cursor = get_db().execute("INSERT INTO dependencies (project_id, predecessor_task_id, successor_task_id, type, lag_work_minutes) VALUES (?, ?, ?, ?, ?)", (project_id, predecessor, successor, relation, lag))
        _bump_project_version(project_id)
    except sqlite3.IntegrityError:
        get_db().rollback()
        return jsonify(error={"code": "dependency_conflict", "message": "That dependency already exists."}), 409
    try:
        schedule = _schedule(project_id)
    except ValueError as exc:
        get_db().rollback()
        return jsonify(error={"code": "dependency_cycle", "message": str(exc)}), 400
    get_db().commit()
    dependency = get_db().execute("SELECT id, project_id, predecessor_task_id, successor_task_id, type, lag_work_minutes FROM dependencies WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(dependency=dict(dependency), schedule=schedule), 201


@analytics_api.delete("/api/v1/projects/<int:project_id>/dependencies/<int:dependency_id>")
def delete_dependency(project_id, dependency_id):
    access, error = _project_or_error(project_id)
    if error:
        return error
    cursor = get_db().execute("DELETE FROM dependencies WHERE id = ? AND project_id = ?", (dependency_id, project_id))
    if cursor.rowcount == 0:
        return jsonify(error={"code": "not_found", "message": "Dependency not found."}), 404
    _bump_project_version(project_id)
    get_db().commit()
    return jsonify(schedule=_schedule(project_id)), 200


@analytics_api.get("/api/v1/projects/<int:project_id>/workload")
def project_workload(project_id):
    access, error = _project_or_error(project_id)
    if error:
        return error
    try:
        schedule = _schedule(project_id)
    except ValueError as exc:
        return jsonify(error={"code": "invalid_schedule", "message": str(exc)}), 422
    tasks_by_id = {task["id"]: task for task in schedule["tasks"]}
    resources = get_db().execute("SELECT id, name, resource_type, capacity_units FROM resources WHERE project_id = ? ORDER BY name", (project_id,)).fetchall()
    assignments = get_db().execute(
        """SELECT a.id, a.task_id, a.resource_id, a.units, a.work_minutes_per_day, t.name AS task_name
           FROM assignments a JOIN tasks t ON t.id = a.task_id JOIN resources r ON r.id = a.resource_id
           WHERE t.project_id = ? AND r.project_id = ? ORDER BY a.resource_id, a.task_id""",
        (project_id, project_id),
    ).fetchall()
    by_resource: dict[int, list[dict]] = defaultdict(list)
    for row in assignments:
        by_resource[row["resource_id"]].append(dict(row))
    result = []
    overloads = []
    for resource in resources:
        resource_assignments = by_resource[resource["id"]]
        daily: dict[str, dict] = defaultdict(lambda: {"assigned_units": 0.0, "tasks": []})
        for assignment in resource_assignments:
            task = tasks_by_id.get(assignment["task_id"])
            if task is None:
                continue
            start = date.fromisoformat(task["early_start"])
            finish = date.fromisoformat(task["early_finish"])
            if task["duration_work_minutes"] == 0:
                work_dates = []
            else:
                work_dates = []
                finish_at = datetime.fromisoformat(task["early_finish_at"])
                cursor = start
                while cursor <= finish:
                    if cursor.weekday() < 5 and (cursor < finish or finish_at.time() > time(9, 0)):
                        work_dates.append(cursor)
                    cursor += timedelta(days=1)
            for work_date in work_dates:
                key = work_date.isoformat()
                load_units = assignment["units"] * (assignment["work_minutes_per_day"] / WORKDAY_MINUTES) if assignment["work_minutes_per_day"] is not None else assignment["units"]
                daily[key]["assigned_units"] += load_units
                daily[key]["tasks"].append({"task_id": task["id"], "task_name": task["name"], "units": round(load_units, 2)})
        days = [{"date": key, "assigned_units": round(value["assigned_units"], 2), "capacity_units": resource["capacity_units"], "tasks": value["tasks"], "overloaded": value["assigned_units"] > resource["capacity_units"]} for key, value in sorted(daily.items())]
        for day in days:
            if day["overloaded"]:
                overloads.append({"resource_id": resource["id"], "resource_name": resource["name"], **day})
        result.append({"id": resource["id"], "name": resource["name"], "resource_type": resource["resource_type"], "capacity_units": resource["capacity_units"], "assignments": resource_assignments, "days": days})
    return jsonify(workload={"project_id": project_id, "project_version": access[0]["version"], "resources": result, "overloads": overloads}), 200


@analytics_api.post("/api/v1/projects/<int:project_id>/tasks/<int:task_id>/assignments")
def assign_resource(project_id, task_id):
    access, error = _project_or_error(project_id)
    if error:
        return error
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error={"code": "invalid_json", "message": "Send a JSON object."}), 400
    resource_id = data.get("resource_id")
    units = data.get("units", 1)
    minutes = data.get("work_minutes_per_day")
    if type(resource_id) is not int or isinstance(units, bool) or not isinstance(units, (int, float)) or units <= 0:
        return jsonify(error={"code": "invalid_assignment", "message": "A resource and positive assignment units are required."}), 400
    if minutes is not None and (type(minutes) is not int or minutes < 0):
        return jsonify(error={"code": "invalid_work", "message": "Daily work must be a non-negative integer number of minutes."}), 400
    valid = get_db().execute("SELECT 1 FROM tasks t JOIN resources r ON r.project_id = t.project_id WHERE t.id = ? AND t.project_id = ? AND r.id = ?", (task_id, project_id, resource_id)).fetchone()
    if valid is None:
        return jsonify(error={"code": "not_found", "message": "Task or resource not found in this project."}), 404
    try:
        cursor = get_db().execute("INSERT INTO assignments (task_id, resource_id, units, work_minutes_per_day) VALUES (?, ?, ?, ?)", (task_id, resource_id, units, minutes))
        _bump_project_version(project_id)
        get_db().commit()
    except sqlite3.IntegrityError:
        get_db().rollback()
        return jsonify(error={"code": "assignment_conflict", "message": "This resource is already assigned to the task."}), 409
    row = get_db().execute("SELECT id, task_id, resource_id, units, work_minutes_per_day, created_at FROM assignments WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(assignment=dict(row)), 201


@analytics_api.delete("/api/v1/projects/<int:project_id>/tasks/<int:task_id>/assignments/<int:assignment_id>")
def remove_assignment(project_id, task_id, assignment_id):
    access, error = _project_or_error(project_id)
    if error:
        return error
    cursor = get_db().execute(
        "DELETE FROM assignments WHERE id = ? AND task_id = ? AND task_id IN (SELECT id FROM tasks WHERE project_id = ?)",
        (assignment_id, task_id, project_id),
    )
    if cursor.rowcount == 0:
        return jsonify(error={"code": "not_found", "message": "Assignment not found."}), 404
    _bump_project_version(project_id)
    get_db().commit()
    return "", 204
