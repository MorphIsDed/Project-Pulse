from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from app.api.validation import json_body, pagination_args, require_fields
from app.services.tenancy import (
    MANAGE_ROLES,
    add_member,
    create_organization,
    delete_organization,
    list_members,
    list_organizations,
    remove_member,
    rename_organization,
    require_organization_membership,
    update_member_role,
)

organizations_api = Blueprint(
    "organizations_api",
    __name__,
    url_prefix="/api/v1/organizations",
)


@organizations_api.get("")
@login_required
def get_organizations():
    limit, offset = pagination_args()
    organizations = list_organizations(current_user.id, limit, offset)
    return jsonify(
        organizations=organizations,
        limit=limit,
        offset=offset,
    )


@organizations_api.post("")
@login_required
def post_organization():
    data = json_body()
    require_fields(data, "name")
    organization = create_organization(current_user.id, data["name"])
    return jsonify(organization=organization.to_dict(role="owner")), 201


@organizations_api.get("/<int:organization_id>")
@login_required
def get_organization(organization_id):
    membership = require_organization_membership(
        organization_id, current_user.id
    )
    return jsonify(
        organization=membership.organization.to_dict(role=membership.role)
    )


@organizations_api.patch("/<int:organization_id>")
@login_required
def patch_organization(organization_id):
    membership = require_organization_membership(
        organization_id, current_user.id, MANAGE_ROLES
    )
    data = json_body()
    require_fields(data, "name")
    organization = rename_organization(
        membership.organization, data["name"]
    )
    return jsonify(
        organization=organization.to_dict(role=membership.role)
    )


@organizations_api.delete("/<int:organization_id>")
@login_required
def remove_organization(organization_id):
    membership = require_organization_membership(
        organization_id, current_user.id, ("owner",)
    )
    delete_organization(membership.organization)
    return "", 204


@organizations_api.get("/<int:organization_id>/members")
@login_required
def get_organization_members(organization_id):
    require_organization_membership(organization_id, current_user.id)
    limit, offset = pagination_args()
    members = list_members(organization_id, limit, offset)
    return jsonify(members=members, limit=limit, offset=offset)


@organizations_api.post("/<int:organization_id>/members")
@login_required
def post_organization_member(organization_id):
    membership = require_organization_membership(
        organization_id, current_user.id, MANAGE_ROLES
    )
    data = json_body()
    require_fields(data, "email", "role")
    member = add_member(membership, data["email"], data["role"])
    return jsonify(member=member.to_dict(include_user=True)), 201


@organizations_api.patch("/<int:organization_id>/members/<int:user_id>")
@login_required
def patch_organization_member(organization_id, user_id):
    membership = require_organization_membership(
        organization_id, current_user.id, MANAGE_ROLES
    )
    data = json_body()
    require_fields(data, "role")
    member = update_member_role(membership, user_id, data["role"])
    return jsonify(member=member.to_dict(include_user=True))


@organizations_api.delete("/<int:organization_id>/members/<int:user_id>")
@login_required
def delete_organization_member(organization_id, user_id):
    membership = require_organization_membership(
        organization_id, current_user.id, MANAGE_ROLES
    )
    remove_member(membership, user_id)
    return "", 204
