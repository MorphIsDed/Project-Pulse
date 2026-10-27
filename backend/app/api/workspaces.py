from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from app.api.validation import json_body, pagination_args, require_fields
from app.services.tenancy import (
    MANAGE_ROLES,
    create_workspace,
    delete_workspace,
    list_workspaces,
    rename_workspace,
    require_organization_membership,
    require_workspace_membership,
)

workspaces_api = Blueprint("workspaces_api", __name__, url_prefix="/api/v1")


@workspaces_api.get("/organizations/<int:organization_id>/workspaces")
@login_required
def get_workspaces(organization_id):
    membership = require_organization_membership(
        organization_id, current_user.id
    )
    limit, offset = pagination_args()
    workspaces = list_workspaces(
        organization_id, membership.role, limit, offset
    )
    return jsonify(
        workspaces=workspaces,
        limit=limit,
        offset=offset,
    )


@workspaces_api.post("/organizations/<int:organization_id>/workspaces")
@login_required
def post_workspace(organization_id):
    membership = require_organization_membership(
        organization_id, current_user.id, MANAGE_ROLES
    )
    data = json_body()
    require_fields(data, "name")
    workspace = create_workspace(organization_id, data["name"])
    return jsonify(
        workspace=workspace.to_dict(role=membership.role)
    ), 201


@workspaces_api.get("/workspaces/<int:workspace_id>")
@login_required
def get_workspace(workspace_id):
    workspace, membership = require_workspace_membership(
        workspace_id, current_user.id
    )
    return jsonify(
        workspace=workspace.to_dict(role=membership.role)
    )


@workspaces_api.patch("/workspaces/<int:workspace_id>")
@login_required
def patch_workspace(workspace_id):
    workspace, membership = require_workspace_membership(
        workspace_id, current_user.id, MANAGE_ROLES
    )
    data = json_body()
    require_fields(data, "name")
    workspace = rename_workspace(workspace, data["name"])
    return jsonify(
        workspace=workspace.to_dict(role=membership.role)
    )


@workspaces_api.delete("/workspaces/<int:workspace_id>")
@login_required
def delete_workspace_route(workspace_id):
    workspace, _membership = require_workspace_membership(
        workspace_id, current_user.id, MANAGE_ROLES
    )
    delete_workspace(workspace)
    return "", 204
