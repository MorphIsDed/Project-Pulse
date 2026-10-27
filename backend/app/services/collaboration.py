import secrets
from datetime import timedelta, timezone
from hashlib import sha256

from flask import current_app
from sqlalchemy import func

from app.errors import ApiError
from app.extensions import db
from app.mail import send_email
from app.models.base import utcnow
from app.models.collaboration import Notification, WorkspaceInvitation
from app.models.tenancy import OrganizationMembership
from app.models.user import User
from app.services.identity import normalize_email
from app.services.tenancy import validate_role

INVITATION_ROLES = ("admin", "editor", "viewer")
INVITATION_DAYS = 7


def token_hash(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def invite_member(organization, actor_id: int, data: dict):
    email = normalize_email(data.get("email"))
    role = validate_role(data.get("role", "viewer"), INVITATION_ROLES)
    existing = db.session.execute(
        db.select(OrganizationMembership)
        .join(User, User.id == OrganizationMembership.user_id)
        .where(
            OrganizationMembership.organization_id == organization.id,
            func.lower(User.email) == email,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ApiError(
            "already_member", "That person is already a member.", 409
        )

    db.session.execute(
        db.delete(WorkspaceInvitation).where(
            WorkspaceInvitation.organization_id == organization.id,
            func.lower(WorkspaceInvitation.email) == email,
            WorkspaceInvitation.accepted_at.is_(None),
        )
    )
    token = secrets.token_urlsafe(32)
    invitation = WorkspaceInvitation(
        organization_id=organization.id,
        email=email,
        role=role,
        token_hash=token_hash(token),
        invited_by=actor_id,
        expires_at=utcnow() + timedelta(days=INVITATION_DAYS),
        created_at=utcnow(),
    )
    db.session.add(invitation)
    db.session.commit()

    public_url = current_app.config["PUBLIC_URL"].rstrip("/")
    try:
        send_email(
            email,
            "ProjectPulse organization invitation",
            f"You have been invited to join {organization.name} as {role}.\n\n"
            f"Accept at {public_url}/?invite_token={token}\n\n"
            f"The invitation expires in {INVITATION_DAYS} days.",
        )
    except Exception:
        current_app.logger.exception("Invitation delivery failed")
        raise ApiError(
            "email_delivery_failed",
            "Invitation saved, but the email could not be delivered.",
            503,
            {"invitation_id": invitation.id},
        ) from None
    return invitation, token


def list_pending_invitations(organization_id: int) -> list[dict]:
    invitations = db.session.scalars(
        db.select(WorkspaceInvitation)
        .where(
            WorkspaceInvitation.organization_id == organization_id,
            WorkspaceInvitation.accepted_at.is_(None),
            WorkspaceInvitation.expires_at > utcnow(),
        )
        .order_by(WorkspaceInvitation.created_at.desc())
    ).all()
    return [item.to_dict() for item in invitations]


def revoke_invitation(organization_id: int, invitation_id: int) -> None:
    invitation = db.session.get(WorkspaceInvitation, invitation_id)
    if invitation is None or invitation.organization_id != organization_id:
        raise ApiError("not_found", "Invitation not found.", 404)
    db.session.delete(invitation)
    db.session.commit()


def accept_invitation(user: User, token: str):
    if not isinstance(token, str) or not token.strip():
        raise ApiError(
            "invalid_invitation", "Enter an invitation token.", 400
        )
    invitation = db.session.execute(
        db.select(WorkspaceInvitation).where(
            WorkspaceInvitation.token_hash == token_hash(token.strip()),
            WorkspaceInvitation.accepted_at.is_(None),
        )
    ).scalar_one_or_none()
    expires_at = invitation.expires_at if invitation is not None else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if invitation is None or expires_at <= utcnow():
        raise ApiError(
            "invalid_invitation",
            "This invitation is invalid or expired.",
            400,
        )
    if invitation.email.lower() != user.email.lower():
        raise ApiError(
            "invitation_email_mismatch",
            "Sign in with the invited email address.",
            403,
        )

    membership = db.session.get(
        OrganizationMembership,
        (invitation.organization_id, user.id),
    )
    if membership is None:
        membership = OrganizationMembership(
            organization_id=invitation.organization_id,
            user_id=user.id,
            role=invitation.role,
        )
        db.session.add(membership)
    else:
        membership.role = invitation.role
    invitation.accepted_at = utcnow()

    db.session.add(
        Notification(
            user_id=user.id,
            organization_id=invitation.organization_id,
            kind="invitation_accepted",
            message=(
                f"You joined organization {invitation.organization_id} "
                f"as {invitation.role}."
            ),
            created_at=utcnow(),
        )
    )
    if invitation.invited_by is not None:
        db.session.add(
            Notification(
                user_id=invitation.invited_by,
                organization_id=invitation.organization_id,
                kind="invitation_accepted",
                message=f"{user.display_name} accepted your invitation.",
                created_at=utcnow(),
            )
        )
    db.session.commit()
    return invitation


def list_notifications(user_id: int, limit: int = 100) -> list[dict]:
    rows = db.session.scalars(
        db.select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(min(limit, 100))
    ).all()
    return [item.to_dict() for item in rows]


def mark_notification_read(user_id: int, notification_id: int):
    notification = db.session.get(Notification, notification_id)
    if notification is None or notification.user_id != user_id:
        raise ApiError("not_found", "Notification not found.", 404)
    if notification.read_at is None:
        notification.read_at = utcnow()
        db.session.commit()
    return notification


def mark_all_notifications_read(user_id: int) -> int:
    rows = db.session.scalars(
        db.select(Notification).where(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
    ).all()
    now = utcnow()
    for row in rows:
        row.read_at = now
    db.session.commit()
    return len(rows)


def notify_project_members(
    project,
    actor_id: int,
    kind: str,
    message: str,
    task_id: int | None = None,
) -> None:
    organization_id = project.workspace.organization_id
    memberships = db.session.scalars(
        db.select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id != actor_id,
        )
    ).all()
    now = utcnow()
    for membership in memberships:
        db.session.add(
            Notification(
                user_id=membership.user_id,
                organization_id=organization_id,
                project_id=project.id,
                task_id=task_id,
                kind=kind,
                message=message,
                created_at=now,
            )
        )
    if memberships:
        db.session.commit()
