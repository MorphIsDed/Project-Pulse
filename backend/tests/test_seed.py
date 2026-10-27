from sqlalchemy import func, select

from app.extensions import db
from app.models.planning import Dependency, Project, ProjectCalendar, Task
from app.models.tenancy import Organization, OrganizationMembership, Workspace
from app.models.user import User

PASSWORD = "CorrectHorse123!"
DEMO_EMAIL = "owner@demo.local"


def login(client, password):
    return client.post(
        "/api/v1/auth/login",
        json={"email": DEMO_EMAIL, "password": password},
    )


def test_seed_uses_configured_demo_password(app_factory):
    app = app_factory(overrides={"DEMO_PASSWORD": PASSWORD})
    result = app.test_cli_runner().invoke(args=["seed-demo"])

    assert result.exit_code == 0

    client = app.test_client()
    assert login(client, PASSWORD).status_code == 200
    assert login(client, "DemoPulse123!").status_code == 401


def test_seed_rejects_invalid_demo_password(app_factory):
    app = app_factory(overrides={"DEMO_PASSWORD": "short"})

    result = app.test_cli_runner().invoke(args=["seed-demo"])

    assert result.exit_code != 0
    assert "at least 8 characters" in result.output
    assert "Traceback" not in result.output


def test_seed_force_is_allowed_in_production(app_factory):
    app = app_factory(
        "production",
        overrides={"SECRET_KEY": "production-test-secret"},
    )

    result = app.test_cli_runner().invoke(args=["seed-demo", "--force"])

    assert result.exit_code == 0
    assert "3 created, 0 skipped" in result.output


def test_seed_creates_tenant_and_is_idempotent(app):
    runner = app.test_cli_runner()

    first = runner.invoke(args=["seed-demo"])
    second = runner.invoke(args=["seed-demo"])

    assert first.exit_code == 0
    assert "3 created, 0 skipped" in first.output
    assert "organization created" in first.output
    assert "3 tasks and 2 dependencies created" in first.output
    assert second.exit_code == 0
    assert "0 created, 3 skipped" in second.output
    assert "organization existing" in second.output
    assert "0 tasks and 0 dependencies created" in second.output

    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(User)) == 3
        assert (
            db.session.scalar(select(func.count()).select_from(Organization))
            == 1
        )
        assert (
            db.session.scalar(select(func.count()).select_from(Workspace))
            == 1
        )
        assert db.session.scalar(select(func.count()).select_from(Project)) == 1
        assert (
            db.session.scalar(select(func.count()).select_from(ProjectCalendar))
            == 1
        )
        assert db.session.scalar(select(func.count()).select_from(Task)) == 3
        assert (
            db.session.scalar(select(func.count()).select_from(Dependency))
            == 2
        )
        roles = {
            membership.user.email: membership.role
            for membership in db.session.scalars(
                select(OrganizationMembership)
            ).all()
        }
        assert roles == {
            "owner@demo.local": "owner",
            "editor@demo.local": "editor",
            "viewer@demo.local": "viewer",
        }
