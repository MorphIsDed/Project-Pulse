import json

from app import get_db
from app.services.identity import create_user


PASSWORD = "CorrectHorse123!"


def signed_in_user(app, client, email="account@example.com"):
    with app.app_context():
        user = create_user(email, PASSWORD, "Account User")
        user_id = user.id
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200
    return user_id


def test_account_export_includes_user_notifications(app, client):
    user_id = signed_in_user(app, client)
    with app.app_context():
        get_db().execute(
            "INSERT INTO notifications(user_id,kind,message) VALUES(?,?,?)",
            (user_id, "task_assigned", "Review the launch plan"),
        )
        get_db().commit()

    response = client.get("/api/v1/account/export")

    assert response.status_code == 200
    exported = json.loads(response.data)
    assert exported["notifications"][0]["message"] == "Review the launch plan"


def test_account_deletion_removes_sole_member_organization(app, client):
    user_id = signed_in_user(app, client)
    with app.app_context():
        db = get_db()
        organization_id = db.execute(
            "INSERT INTO organizations(name) VALUES(?)", ("Personal",)
        ).lastrowid
        db.execute(
            "INSERT INTO organization_memberships(organization_id,user_id,role) VALUES(?,?,'owner')",
            (organization_id, user_id),
        )
        db.commit()

    response = client.delete("/api/v1/account", json={"password": PASSWORD})

    assert response.status_code == 200
    with app.app_context():
        assert get_db().execute(
            "SELECT 1 FROM organizations WHERE id=?", (organization_id,)
        ).fetchone() is None
        assert get_db().execute(
            "SELECT 1 FROM users WHERE id=?", (user_id,)
        ).fetchone() is None


def test_guest_import_is_atomic_and_idempotent(app, client):
    signed_in_user(app, client)
    snapshot = {
        "organizations": [{"id": "guest-org", "name": "Guest Org"}],
        "workspaces": [{"id": "guest-ws", "organization_id": "guest-org", "name": "Guest Workspace"}],
        "projects": [{"id": "guest-project", "workspace_id": "guest-ws", "name": "Guest Project"}],
        "tasks": [{"id": "guest-task", "project_id": "guest-project", "name": "Guest Task", "duration_work_minutes": 60}],
    }

    first = client.post(
        "/api/v1/account/import-guest",
        json={"draft_id": "draft-1", "snapshot": snapshot},
    )
    second = client.post(
        "/api/v1/account/import-guest",
        json={"draft_id": "draft-1", "snapshot": snapshot},
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.get_json()["already_imported"] is True
    with app.app_context():
        assert get_db().execute("SELECT count(*) FROM tasks").fetchone()[0] == 1


def test_guest_import_failure_does_not_partially_save(app, client):
    signed_in_user(app, client)
    response = client.post(
        "/api/v1/account/import-guest",
        json={"draft_id": "broken-draft", "snapshot": {"organizations": ["not-an-object"]}},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "guest_import_failed"
    with app.app_context():
        assert get_db().execute("SELECT count(*) FROM organizations").fetchone()[0] == 0
