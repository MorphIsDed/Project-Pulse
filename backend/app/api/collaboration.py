from flask import Blueprint, current_app, jsonify
from flask_login import current_user, login_required

from app.api.validation import json_body, pagination_args
from app.services.collaboration import (
    accept_invitation,
    invite_member,
    list_notifications,
    list_pending_invitations,
    mark_all_notifications_read,
    mark_notification_read,
    revoke_invitation,
)
from app.services.tenancy import (
    MANAGE_ROLES,
    require_organization_membership,
)


collaboration_api = Blueprint(
    "collaboration_api", __name__, url_prefix="/api/v1"
)


@collaboration_api.get("/notifications")
@login_required
def get_notifications():
    limit, _offset = pagination_args(default_limit=100)
    return jsonify(
        notifications=list_notifications(current_user.id, limit=limit)
    )


@collaboration_api.patch("/notifications/<int:notification_id>")
@login_required
def patch_notification(notification_id):
    notification = mark_notification_read(
        current_user.id, notification_id
    )
    return jsonify(notification=notification.to_dict())


@collaboration_api.post("/notifications/read-all")
@login_required
def post_notifications_read_all():
    count = mark_all_notifications_read(current_user.id)
    return jsonify(marked_read=count)


@collaboration_api.get(
    "/organizations/<int:organization_id>/invitations"
)
@login_required
def get_invitations(organization_id):
    require_organization_membership(
        organization_id, current_user.id, MANAGE_ROLES
    )
    return jsonify(
        invitations=list_pending_invitations(organization_id)
    )


@collaboration_api.post(
    "/organizations/<int:organization_id>/invitations"
)
@login_required
def post_invitation(organization_id):
    membership = require_organization_membership(
        organization_id, current_user.id, MANAGE_ROLES
    )
    invitation, token = invite_member(
        membership.organization, current_user.id, json_body()
    )
    body = {"invitation": invitation.to_dict()}
    if current_app.config.get("APP_ENV") != "production":
        body["accept_token"] = token
    return jsonify(body), 201


@collaboration_api.delete(
    "/organizations/<int:organization_id>/invitations/<int:invitation_id>"
)
@login_required
def delete_invitation(organization_id, invitation_id):
    require_organization_membership(
        organization_id, current_user.id, MANAGE_ROLES
    )
    revoke_invitation(organization_id, invitation_id)
    return "", 204


@collaboration_api.post("/invitations/accept")
@login_required
def post_accept_invitation():
    data = json_body()
    invitation = accept_invitation(current_user, data.get("token"))
    return jsonify(
        message="Invitation accepted.",
        organization_id=invitation.organization_id,
    )
