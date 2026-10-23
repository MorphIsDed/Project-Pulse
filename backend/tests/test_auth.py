import json

import pytest
from sqlalchemy import func, select

from app.extensions import db
from app.models.user import User
from app.services.identity import create_user

PASSWORD = "CorrectHorse123!"
EMAIL = "owner@example.com"


def create_test_user(app, email=EMAIL, password=PASSWORD, display_name="Owner"):
    with app.app_context():
        user = create_user(email, password, display_name)
        return user.id


def login(client, email=EMAIL, password=PASSWORD, remember=False):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "remember": remember},
    )


def test_register_is_disabled_by_default(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@example.com",
            "password": PASSWORD,
            "display_name": "New User",
        },
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "registration_disabled"


def test_register_enabled_creates_user_and_session(public_signup_app):
    client = public_signup_app.test_client()

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "New@Example.com",
            "password": PASSWORD,
            "display_name": "New User",
        },
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["user"]["email"] == "new@example.com"
    assert body["user"]["display_name"] == "New User"
    assert body["csrf_token"]
    assert "password_hash" not in json.dumps(body)

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.get_json()["user"]["email"] == "new@example.com"

    with public_signup_app.app_context():
        user = db.session.execute(
            db.select(User).where(User.email == "new@example.com")
        ).scalar_one()
        assert user.password_hash != PASSWORD
        assert user.check_password(PASSWORD)


def test_register_rejects_duplicate_email_case_insensitively(public_signup_app):
    client = public_signup_app.test_client()
    payload = {
        "email": "Owner@Example.com",
        "password": PASSWORD,
        "display_name": "Owner",
    }

    assert client.post("/api/v1/auth/register", json=payload).status_code == 201

    payload["email"] = "owner@example.com"
    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "email_taken"


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (
            {"email": "not-an-email", "password": PASSWORD, "display_name": "A"},
            "invalid_email",
        ),
        (
            {"email": "a@example.com", "password": "short", "display_name": "A"},
            "weak_password",
        ),
        (
            {"email": "a@example.com", "password": PASSWORD, "display_name": "  "},
            "validation_error",
        ),
        (
            {"email": "a@example.com", "password": PASSWORD},
            "validation_error",
        ),
    ],
)
def test_register_validation(public_signup_app, payload, code):
    client = public_signup_app.test_client()

    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == code


def test_login_success_sets_session(app, client):
    create_test_user(app)

    response = login(client, email="OWNER@example.com")

    assert response.status_code == 200
    body = response.get_json()
    assert body["user"]["email"] == EMAIL
    assert body["csrf_token"]

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.get_json()["user"]["id"] == body["user"]["id"]


@pytest.mark.parametrize(
    ("email", "password"),
    [
        (EMAIL, "WrongPassword123!"),
        ("unknown@example.com", PASSWORD),
    ],
)
def test_login_failure_is_generic(app, client, email, password):
    create_test_user(app)

    response = login(client, email=email, password=password)

    assert response.status_code == 401
    error = response.get_json()["error"]
    assert error["code"] == "invalid_credentials"
    assert error["message"] == "Email or password is incorrect."


def test_me_requires_authentication(client):
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "unauthorized"


def test_logout_clears_session(app, client):
    create_test_user(app)
    assert login(client).status_code == 200

    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_is_idempotent(client):
    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_password_is_never_returned(app, client):
    create_test_user(app)

    response = login(client)

    assert "password_hash" not in json.dumps(response.get_json())
    assert PASSWORD not in json.dumps(response.get_json())


def test_seed_demo_is_idempotent(app):
    runner = app.test_cli_runner()

    first = runner.invoke(args=["seed-demo"])
    second = runner.invoke(args=["seed-demo"])

    assert first.exit_code == 0
    assert "3 created, 0 skipped" in first.output
    assert second.exit_code == 0
    assert "0 created, 3 skipped" in second.output

    with app.app_context():
        count = db.session.scalar(select(func.count()).select_from(User))
        assert count == 3


def test_seed_demo_refuses_production_without_force(app_factory):
    production_app = app_factory(
        "production",
        overrides={"SECRET_KEY": "production-test-secret"},
    )
    runner = production_app.test_cli_runner()

    result = runner.invoke(args=["seed-demo"])

    assert result.exit_code != 0
    assert "Refusing to seed demo accounts in production" in result.output
