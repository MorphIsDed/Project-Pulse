from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.errors import ApiError
from app.extensions import db
from app.models.planning import Project
from app.models.tenancy import (
    ORGANIZATION_ROLES,
    Organization,
    OrganizationMembership,
    Workspace,
)
from app.models.user import User
from app.services.identity import normalize_email

MANAGE_ROLES = ("owner", "admin")
EDIT_ROLES = ("owner", "admin", "editor")


def validate_name(value, label: str, max_length: int = 120) -> str:
    if not isinstance(value, str):
        raise ApiError("invalid_name", f"{label} name is required.", 400)
    name = value.strip()
    if not name:
        raise ApiError("invalid_name", f"{label} name is required.", 400)
    if len(name) > max_length:
        raise ApiError(
            "invalid_name",
            f"{label} name must be {max_length} characters or fewer.",
            400,
        )
    return name


def validate_role(value, allowed_roles=ORGANIZATION_ROLES) -> str:
    if value not in allowed_roles:
        raise ApiError(
            "invalid_role",
            "Choose a supported organization role.",
            400,
            {"roles": list(allowed_roles)},
        )
    return value


def get_membership(organization_id: int, user_id: int):
    return db.session.execute(
        db.select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
    ).scalar_one_or_none()


def require_organization_membership(
    organization_id: int,
    user_id: int,
    allowed_roles=None,
) -> OrganizationMembership:
    membership = get_membership(organization_id, user_id)
    if membership is None:
        raise ApiError("not_found", "Organization not found.", 404)
    if allowed_roles is not None and membership.role not in allowed_roles:
        raise ApiError(
            "forbidden",
            "You do not have permission to perform this action.",
            403,
        )
    return membership


def require_workspace_membership(
    workspace_id: int,
    user_id: int,
    allowed_roles=None,
):
    workspace = db.session.get(Workspace, workspace_id)
    if workspace is None:
        raise ApiError("not_found", "Workspace not found.", 404)
    membership = get_membership(workspace.organization_id, user_id)
    if membership is None:
        raise ApiError("not_found", "Workspace not found.", 404)
    if allowed_roles is not None and membership.role not in allowed_roles:
        raise ApiError(
            "forbidden",
            "You do not have permission to perform this action.",
            403,
        )
    return workspace, membership


def require_project_membership(
    project_id: int,
    user_id: int,
    allowed_roles=None,
):
    project = db.session.get(Project, project_id)
    if project is None:
        raise ApiError("not_found", "Project not found.", 404)
    membership = get_membership(project.workspace.organization_id, user_id)
    if membership is None:
        raise ApiError("not_found", "Project not found.", 404)
    if allowed_roles is not None and membership.role not in allowed_roles:
        raise ApiError(
            "forbidden",
            "You do not have permission to perform this action.",
            403,
        )
    return project, membership


def list_organizations(user_id: int, limit: int, offset: int) -> list[dict]:
    rows = db.session.execute(
        db.select(Organization, OrganizationMembership.role)
        .join(
            OrganizationMembership,
            OrganizationMembership.organization_id == Organization.id,
        )
        .where(OrganizationMembership.user_id == user_id)
        .order_by(func.lower(Organization.name), Organization.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [organization.to_dict(role=role) for organization, role in rows]


def create_organization(user_id: int, name) -> Organization:
    organization = Organization(name=validate_name(name, "Organization"))
    organization.memberships.append(
        OrganizationMembership(user_id=user_id, role="owner")
    )
    db.session.add(organization)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError(
            "organization_creation_failed",
            "Could not create the organization.",
            400,
        ) from None
    return organization


def rename_organization(organization: Organization, name) -> Organization:
    organization.name = validate_name(name, "Organization")
    db.session.commit()
    return organization


def delete_organization(organization: Organization) -> None:
    db.session.delete(organization)
    db.session.commit()


def list_members(organization_id: int, limit: int, offset: int) -> list[dict]:
    memberships = db.session.scalars(
        db.select(OrganizationMembership)
        .where(OrganizationMembership.organization_id == organization_id)
        .order_by(
            OrganizationMembership.created_at,
            OrganizationMembership.user_id,
        )
        .limit(limit)
        .offset(offset)
    ).all()
    return [membership.to_dict(include_user=True) for membership in memberships]


def _owner_count(organization_id: int) -> int:
    return db.session.scalar(
        db.select(func.count())
        .select_from(OrganizationMembership)
        .where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.role == "owner",
        )
    )


def add_member(
    actor: OrganizationMembership,
    email,
    role,
) -> OrganizationMembership:
    valid_role = validate_role(role)
    if valid_role == "owner" and actor.role != "owner":
        raise ApiError(
            "forbidden",
            "Only an owner can grant the owner role.",
            403,
        )

    normalized_email = normalize_email(email)
    user = db.session.execute(
        db.select(User).where(User.email == normalized_email)
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise ApiError("member_not_found", "User not found.", 404)

    existing = get_membership(actor.organization_id, user.id)
    if existing is not None:
        raise ApiError(
            "member_exists",
            "That user is already a member of this organization.",
            409,
        )

    membership = OrganizationMembership(
        organization_id=actor.organization_id,
        user_id=user.id,
        role=valid_role,
    )
    db.session.add(membership)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError(
            "member_exists",
            "That user is already a member of this organization.",
            409,
        ) from None
    return membership


def update_member_role(
    actor: OrganizationMembership,
    target_user_id: int,
    role,
) -> OrganizationMembership:
    target = get_membership(actor.organization_id, target_user_id)
    if target is None:
        raise ApiError("member_not_found", "Member not found.", 404)

    valid_role = validate_role(role)
    if actor.role != "owner" and (
        target.role == "owner" or valid_role == "owner"
    ):
        raise ApiError(
            "forbidden",
            "Only an owner can manage the owner role.",
            403,
        )

    if (
        target.role == "owner"
        and valid_role != "owner"
        and _owner_count(actor.organization_id) <= 1
    ):
        raise ApiError(
            "last_owner",
            "The organization must keep at least one owner.",
            409,
        )

    target.role = valid_role
    db.session.commit()
    return target


def remove_member(
    actor: OrganizationMembership,
    target_user_id: int,
) -> None:
    target = get_membership(actor.organization_id, target_user_id)
    if target is None:
        raise ApiError("member_not_found", "Member not found.", 404)

    if target.role == "owner":
        if actor.role != "owner":
            raise ApiError(
                "forbidden",
                "Only an owner can remove an owner.",
                403,
            )
        if _owner_count(actor.organization_id) <= 1:
            raise ApiError(
                "last_owner",
                "The organization must keep at least one owner.",
                409,
            )

    db.session.delete(target)
    db.session.commit()


def list_workspaces(
    organization_id: int,
    role: str,
    limit: int,
    offset: int,
) -> list[dict]:
    workspaces = db.session.scalars(
        db.select(Workspace)
        .where(Workspace.organization_id == organization_id)
        .order_by(func.lower(Workspace.name), Workspace.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [workspace.to_dict(role=role) for workspace in workspaces]


def create_workspace(organization_id: int, name) -> Workspace:
    workspace = Workspace(
        organization_id=organization_id,
        name=validate_name(name, "Workspace"),
    )
    db.session.add(workspace)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError(
            "workspace_conflict",
            "A workspace with that name already exists.",
            409,
        ) from None
    return workspace


def rename_workspace(workspace: Workspace, name) -> Workspace:
    workspace.name = validate_name(name, "Workspace")
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError(
            "workspace_conflict",
            "A workspace with that name already exists.",
            409,
        ) from None
    return workspace


def delete_workspace(workspace: Workspace) -> None:
    db.session.delete(workspace)
    db.session.commit()
