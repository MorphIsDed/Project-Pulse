from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.api.validation import json_body, optional_int_arg, pagination_args
from app.errors import ApiError
from app.extensions import db
from app.models.planning import Task
from app.services.collaboration import notify_project_members
from app.services.planning import (
    create_task,
    delete_task,
    list_tasks,
    update_task,
)
from app.services.tenancy import EDIT_ROLES, require_project_membership

tasks_api = Blueprint("tasks_api", __name__, url_prefix="/api/v1")


def _get_task(project_id: int, task_id: int) -> Task:
    task = db.session.get(Task, task_id)
    if task is None or task.project_id != project_id:
        raise ApiError("not_found", "Task not found.", 404)
    return task


@tasks_api.get("/projects/<int:project_id>/tasks")
@login_required
def get_tasks(project_id):
    require_project_membership(project_id, current_user.id)
    limit, offset = pagination_args()
    status = request.args.get("status") or None
    parent_task_id = optional_int_arg("parent_task_id")
    tasks = list_tasks(
        project_id,
        limit,
        offset,
        status=status,
        parent_task_id=parent_task_id,
    )
    return jsonify(tasks=tasks, limit=limit, offset=offset)


@tasks_api.post("/projects/<int:project_id>/tasks")
@login_required
def post_task(project_id):
    project, _membership = require_project_membership(
        project_id, current_user.id, EDIT_ROLES
    )
    data = json_body()
    task = create_task(project, data)
    notify_project_members(
        project,
        current_user.id,
        "task_created",
        f"{current_user.display_name} added task '{task.name}' to {project.name}.",
        task_id=task.id,
    )
    return jsonify(
        task=task.to_dict(),
        project_version=project.version,
    ), 201


@tasks_api.get("/projects/<int:project_id>/tasks/<int:task_id>")
@login_required
def get_task(project_id, task_id):
    require_project_membership(project_id, current_user.id)
    task = _get_task(project_id, task_id)
    return jsonify(task=task.to_dict())


@tasks_api.patch("/projects/<int:project_id>/tasks/<int:task_id>")
@login_required
def patch_task(project_id, task_id):
    project, _membership = require_project_membership(
        project_id, current_user.id, EDIT_ROLES
    )
    task = _get_task(project_id, task_id)
    data = json_body()
    task = update_task(project, task, data)
    return jsonify(
        task=task.to_dict(),
        project_version=project.version,
    )


@tasks_api.delete("/projects/<int:project_id>/tasks/<int:task_id>")
@login_required
def delete_task_route(project_id, task_id):
    project, _membership = require_project_membership(
        project_id, current_user.id, EDIT_ROLES
    )
    task = _get_task(project_id, task_id)
    delete_task(project, task)
    return "", 204
