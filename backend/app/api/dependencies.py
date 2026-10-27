from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from app.api.validation import json_body, pagination_args
from app.errors import ApiError
from app.extensions import db
from app.models.planning import Dependency
from app.services.planning import (
    create_dependency,
    delete_dependency,
    list_dependencies,
)
from app.services.tenancy import EDIT_ROLES, require_project_membership

dependencies_api = Blueprint(
    "dependencies_api", __name__, url_prefix="/api/v1"
)


@dependencies_api.get("/projects/<int:project_id>/dependencies")
@login_required
def get_dependencies(project_id):
    require_project_membership(project_id, current_user.id)
    limit, offset = pagination_args()
    dependencies = list_dependencies(project_id, limit, offset)
    return jsonify(
        dependencies=dependencies,
        limit=limit,
        offset=offset,
    )


@dependencies_api.post("/projects/<int:project_id>/dependencies")
@login_required
def post_dependency(project_id):
    project, _membership = require_project_membership(
        project_id, current_user.id, EDIT_ROLES
    )
    data = json_body()
    dependency = create_dependency(project, data)
    return jsonify(
        dependency=dependency.to_dict(),
        project_version=project.version,
    ), 201


@dependencies_api.delete(
    "/projects/<int:project_id>/dependencies/<int:dependency_id>"
)
@login_required
def delete_dependency_route(project_id, dependency_id):
    project, _membership = require_project_membership(
        project_id, current_user.id, EDIT_ROLES
    )
    dependency = db.session.get(Dependency, dependency_id)
    if dependency is None or dependency.project_id != project_id:
        raise ApiError("not_found", "Dependency not found.", 404)
    delete_dependency(project, dependency)
    return "", 204
