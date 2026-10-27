from app.errors import ApiError
from app.extensions import db
from app.models.base import iso_date, iso_utc, utcnow
from app.models.collaboration import Notification
from app.models.tenancy import (
    Organization,
    OrganizationMembership,
    Workspace,
)
from app.models.user import User
from app.services.collaboration import list_notifications


def export_account(user: User) -> dict:
    memberships = db.session.scalars(
        db.select(OrganizationMembership)
        .where(OrganizationMembership.user_id == user.id)
        .order_by(OrganizationMembership.organization_id)
    ).all()
    organizations = []
    for membership in memberships:
        organization = db.session.get(
            Organization, membership.organization_id
        )
        if organization is None:
            continue
        organization_data = organization.to_dict(membership.role)
        organization_data["memberships"] = [
            item.to_dict(include_user=True)
            for item in organization.memberships
        ]
        organization_data["workspaces"] = []
        workspaces = db.session.scalars(
            db.select(Workspace)
            .where(Workspace.organization_id == organization.id)
            .order_by(Workspace.id)
        ).all()
        for workspace in workspaces:
            workspace_data = workspace.to_dict(membership.role)
            workspace_data["projects"] = []
            for project in workspace.projects:
                project_data = project.to_dict(membership.role)
                project_data["calendar"] = (
                    project.calendar.to_dict()
                    if project.calendar is not None
                    else None
                )
                project_data["tasks"] = [
                    task.to_dict() for task in project.tasks
                ]
                project_data["dependencies"] = [
                    dependency.to_dict()
                    for dependency in project.dependencies
                ]
                project_data["resources"] = [
                    resource.to_dict() for resource in project.resources
                ]
                project_data["assignments"] = [
                    assignment.to_dict()
                    for assignment in project.assignments
                ]
                workspace_data["projects"].append(project_data)
            organization_data["workspaces"].append(workspace_data)
        organizations.append(organization_data)

    return {
        "export_version": 1,
        "exported_at": iso_utc(utcnow()),
        "user": user.to_dict(),
        "notifications": list_notifications(user.id),
        "organizations": organizations,
    }


def delete_account(user: User, password) -> None:
    if not isinstance(password, str) or not user.check_password(password):
        raise ApiError(
            "invalid_credentials", "Password is incorrect.", 403
        )

    memberships = db.session.scalars(
        db.select(OrganizationMembership).where(
            OrganizationMembership.user_id == user.id
        )
    ).all()
    for membership in memberships:
        others = db.session.scalars(
            db.select(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id
                == membership.organization_id,
                OrganizationMembership.user_id != user.id,
            )
            .order_by(OrganizationMembership.created_at)
        ).all()
        if not others:
            organization = db.session.get(
                Organization, membership.organization_id
            )
            if organization is not None:
                db.session.delete(organization)
            continue

        if membership.role == "owner":
            successor = next(
                (
                    item
                    for item in others
                    if item.role == "admin"
                ),
                others[0],
            )
            successor.role = "owner"

    db.session.execute(
        db.delete(Notification).where(Notification.user_id == user.id)
    )
    db.session.delete(user)
    db.session.commit()


def account_export_filename(user: User) -> str:
    stem = "".join(
        character
        if character.isalnum() or character in {"-", "_"}
        else "-"
        for character in user.email
    ).strip("-")
    return f"projectpulse-{stem or 'account'}-export.json"


def export_dates(value):
    if hasattr(value, "isoformat"):
        return iso_date(value)
    return value
