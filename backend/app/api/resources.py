from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from app.api.validation import json_body, pagination_args
from app.errors import ApiError
from app.extensions import db
from app.models.resources import Assignment, Resource
from app.services.resources import (
    create_assignment,
    create_resource,
    delete_assignment,
    delete_resource,
    get_leveling_preview,
    get_project_workload,
    list_assignments,
    list_resources,
    update_assignment,
    update_resource,
)
from app.services.tenancy import EDIT_ROLES, require_project_membership


resources_api = Blueprint("resources_api", __name__, url_prefix="/api/v1")


def _get_resource(project_id: int, resource_id: int) -> Resource:
    resource = db.session.get(Resource, resource_id)
    if resource is None or resource.project_id != project_id:
        raise ApiError("not_found", "Resource not found.", 404)
    return resource


def _get_assignment(project_id: int, assignment_id: int) -> Assignment:
    assignment = db.session.get(Assignment, assignment_id)
    if assignment is None or assignment.project_id != project_id:
        raise ApiError("not_found", "Assignment not found.", 404)
    return assignment


@resources_api.get("/projects/<int:project_id>/resources")
@login_required
def get_resources(project_id):
    require_project_membership(project_id, current_user.id)
    limit, offset = pagination_args(default_limit=100)
    resources = list_resources(project_id, limit, offset)
    return jsonify(resources=resources, limit=limit, offset=offset)


@resources_api.post("/projects/<int:project_id>/resources")
@login_required
def post_resource(project_id):
    project, _membership = require_project_membership(
        project_id, current_user.id, EDIT_ROLES
    )
    resource = create_resource(project, json_body())
    return jsonify(
        resource=resource.to_dict(),
        project_version=project.version,
    ), 201


@resources_api.patch(
    "/projects/<int:project_id>/resources/<int:resource_id>"
)
@login_required
def patch_resource(project_id, resource_id):
    project, _membership = require_project_membership(
        project_id, current_user.id, EDIT_ROLES
    )
    resource = _get_resource(project_id, resource_id)
    resource = update_resource(project, resource, json_body())
    return jsonify(
        resource=resource.to_dict(),
        project_version=project.version,
    )


@resources_api.delete(
    "/projects/<int:project_id>/resources/<int:resource_id>"
)
@login_required
def delete_resource_route(project_id, resource_id):
    project, _membership = require_project_membership(
        project_id, current_user.id, EDIT_ROLES
    )
    resource = _get_resource(project_id, resource_id)
    delete_resource(project, resource)
    return "", 204


@resources_api.get("/projects/<int:project_id>/assignments")
@login_required
def get_assignments(project_id):
    require_project_membership(project_id, current_user.id)
    limit, offset = pagination_args(default_limit=100)
    assignments = list_assignments(project_id, limit, offset)
    return jsonify(assignments=assignments, limit=limit, offset=offset)


@resources_api.post("/projects/<int:project_id>/assignments")
@login_required
def post_assignment(project_id):
    project, _membership = require_project_membership(
        project_id, current_user.id, EDIT_ROLES
    )
    assignment = create_assignment(project, json_body())
    return jsonify(
        assignment=assignment.to_dict(),
        project_version=project.version,
    ), 201


@resources_api.patch(
    "/projects/<int:project_id>/assignments/<int:assignment_id>"
)
@login_required
def patch_assignment(project_id, assignment_id):
    project, _membership = require_project_membership(
        project_id, current_user.id, EDIT_ROLES
    )
    assignment = _get_assignment(project_id, assignment_id)
    assignment = update_assignment(project, assignment, json_body())
    return jsonify(
        assignment=assignment.to_dict(),
        project_version=project.version,
    )


@resources_api.delete(
    "/projects/<int:project_id>/assignments/<int:assignment_id>"
)
@login_required
def delete_assignment_route(project_id, assignment_id):
    project, _membership = require_project_membership(
        project_id, current_user.id, EDIT_ROLES
    )
    assignment = _get_assignment(project_id, assignment_id)
    delete_assignment(project, assignment)
    return "", 204


@resources_api.get("/projects/<int:project_id>/workload")
@login_required
def get_workload(project_id):
    project, _membership = require_project_membership(
        project_id, current_user.id
    )
    return jsonify(workload=get_project_workload(project))


@resources_api.get("/projects/<int:project_id>/leveling-preview")
@login_required
def get_leveling_preview_route(project_id):
    project, _membership = require_project_membership(
        project_id, current_user.id
    )
    return jsonify(preview=get_leveling_preview(project))
