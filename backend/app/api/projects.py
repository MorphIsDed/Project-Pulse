from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from app.api.validation import json_body, pagination_args
from app.services.planning import (
    create_project,
    delete_project,
    get_calendar,
    list_projects,
    update_project,
)
from app.services.scheduling import update_calendar
from app.services.tenancy import (
    EDIT_ROLES,
    MANAGE_ROLES,
    require_project_membership,
    require_workspace_membership,
)

projects_api = Blueprint("projects_api", __name__, url_prefix="/api/v1")


@projects_api.get("/workspaces/<int:workspace_id>/projects")
@login_required
def get_projects(workspace_id):
    _workspace, membership = require_workspace_membership(
        workspace_id, current_user.id
    )
    limit, offset = pagination_args()
    projects = list_projects(
        workspace_id, membership.role, limit, offset
    )
    return jsonify(
        projects=projects,
        limit=limit,
        offset=offset,
    )


@projects_api.post("/workspaces/<int:workspace_id>/projects")
@login_required
def post_project(workspace_id):
    workspace, membership = require_workspace_membership(
        workspace_id, current_user.id, EDIT_ROLES
    )
    data = json_body()
    project = create_project(workspace, current_user.id, data)
    return jsonify(
        project=project.to_dict(role=membership.role)
    ), 201


@projects_api.get("/projects/<int:project_id>")
@login_required
def get_project(project_id):
    project, membership = require_project_membership(
        project_id, current_user.id
    )
    return jsonify(
        project=project.to_dict(role=membership.role)
    )


@projects_api.patch("/projects/<int:project_id>")
@login_required
def patch_project(project_id):
    project, membership = require_project_membership(
        project_id, current_user.id, EDIT_ROLES
    )
    data = json_body()
    project = update_project(project, data)
    return jsonify(
        project=project.to_dict(role=membership.role)
    )


@projects_api.delete("/projects/<int:project_id>")
@login_required
def delete_project_route(project_id):
    project, _membership = require_project_membership(
        project_id, current_user.id, MANAGE_ROLES
    )
    delete_project(project)
    return "", 204


@projects_api.get("/projects/<int:project_id>/calendar")
@login_required
def get_project_calendar(project_id):
    project, _membership = require_project_membership(
        project_id, current_user.id
    )
    calendar = get_calendar(project)
    return jsonify(calendar=calendar.to_dict())


@projects_api.patch("/projects/<int:project_id>/calendar")
@login_required
def patch_project_calendar(project_id):
    project, membership = require_project_membership(
        project_id, current_user.id, EDIT_ROLES
    )
    data = json_body()
    calendar, project = update_calendar(project, data)
    return jsonify(
        calendar=calendar.to_dict(),
        project=project.to_dict(role=membership.role),
    )


@projects_api.get("/projects/<int:project_id>/summary")
@login_required
def get_project_summary(project_id):
    from app.services.summary import project_summary

    project, _membership = require_project_membership(project_id, current_user.id)
    return jsonify(summary=project_summary(project))
