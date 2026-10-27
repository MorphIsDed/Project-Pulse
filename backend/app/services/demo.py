from app.extensions import db
from app.models.planning import Dependency, Project, Task
from app.models.tenancy import Organization, OrganizationMembership, Workspace
from app.models.user import User
from app.services.identity import seed_demo_users
from app.services.planning import (
    create_dependency,
    create_project,
    create_task,
)
from app.services.tenancy import create_organization, create_workspace

DEMO_ORGANIZATION = "Demo Organization"
DEMO_WORKSPACE = "Demo Workspace"
DEMO_PROJECT = "Demo Project"
DEMO_TASKS = ("Plan launch", "Build product", "Review launch")
DEMO_DEPENDENCIES = (
    ("Plan launch", "Build product", "FS"),
    ("Build product", "Review launch", "FS"),
)


def _find_user(email: str) -> User:
    return db.session.execute(
        db.select(User).where(User.email == email)
    ).scalar_one()


def _ensure_membership(
    organization: Organization,
    user: User,
    role: str,
) -> bool:
    existing = db.session.execute(
        db.select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization.id,
            OrganizationMembership.user_id == user.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False
    db.session.add(
        OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role=role,
        )
    )
    db.session.commit()
    return True


def seed_demo(password: str) -> dict:
    users_created, users_skipped = seed_demo_users(password)
    owner = _find_user("owner@demo.local")
    editor = _find_user("editor@demo.local")
    viewer = _find_user("viewer@demo.local")

    organization = db.session.execute(
        db.select(Organization).where(Organization.name == DEMO_ORGANIZATION)
    ).scalar_one_or_none()
    tenant_created = organization is None
    if organization is None:
        organization = create_organization(owner.id, DEMO_ORGANIZATION)
    else:
        _ensure_membership(organization, owner, "owner")

    memberships_created = 0
    memberships_created += int(
        _ensure_membership(organization, editor, "editor")
    )
    memberships_created += int(
        _ensure_membership(organization, viewer, "viewer")
    )

    workspace = db.session.execute(
        db.select(Workspace).where(
            Workspace.organization_id == organization.id,
            Workspace.name == DEMO_WORKSPACE,
        )
    ).scalar_one_or_none()
    workspace_created = workspace is None
    if workspace is None:
        workspace = create_workspace(organization.id, DEMO_WORKSPACE)

    project = db.session.execute(
        db.select(Project).where(
            Project.workspace_id == workspace.id,
            Project.name == DEMO_PROJECT,
        )
    ).scalar_one_or_none()
    project_created = project is None
    if project is None:
        project = create_project(workspace, owner.id, {"name": DEMO_PROJECT})

    tasks_created = 0
    tasks = {}
    for name in DEMO_TASKS:
        task = db.session.execute(
            db.select(Task).where(
                Task.project_id == project.id,
                Task.name == name,
            )
        ).scalar_one_or_none()
        if task is None:
            task = create_task(project, {"name": name})
            tasks_created += 1
        tasks[name] = task

    dependencies_created = 0
    for predecessor_name, successor_name, dependency_type in DEMO_DEPENDENCIES:
        predecessor = tasks[predecessor_name]
        successor = tasks[successor_name]
        existing = db.session.execute(
            db.select(Dependency).where(
                Dependency.project_id == project.id,
                Dependency.predecessor_task_id == predecessor.id,
                Dependency.successor_task_id == successor.id,
                Dependency.type == dependency_type,
            )
        ).scalar_one_or_none()
        if existing is None:
            create_dependency(
                project,
                {
                    "predecessor_task_id": predecessor.id,
                    "successor_task_id": successor.id,
                    "type": dependency_type,
                },
            )
            dependencies_created += 1

    return {
        "users_created": users_created,
        "users_skipped": users_skipped,
        "tenant_created": tenant_created,
        "memberships_created": memberships_created,
        "workspace_created": workspace_created,
        "project_created": project_created,
        "tasks_created": tasks_created,
        "dependencies_created": dependencies_created,
    }
