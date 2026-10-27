from tests.helpers import (
    add_member,
    create_org,
    create_project,
    create_task,
    create_workspace,
    logged_in_client,
    login,
    make_user,
)


def setup_org(app):
    client = logged_in_client(app)
    organization = create_org(client)
    workspace = create_workspace(client, organization["id"])
    project = create_project(client, workspace["id"])
    return client, organization, workspace, project


def test_invitation_can_be_listed_accepted_and_revoked(app):
    client, organization, _workspace, _project = setup_org(app)

    response = client.post(
        f"/api/v1/organizations/{organization['id']}/invitations",
        json={"email": "invitee@example.com", "role": "editor"},
    )
    assert response.status_code == 201, response.get_json()
    body = response.get_json()
    invitation = body["invitation"]
    token = body["accept_token"]
    assert invitation["role"] == "editor"
    assert invitation["email"] == "invitee@example.com"

    listed = client.get(
        f"/api/v1/organizations/{organization['id']}/invitations"
    ).get_json()["invitations"]
    assert [item["id"] for item in listed] == [invitation["id"]]

    make_user(app, "invitee@example.com", "Invitee")
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert login(client, "invitee@example.com").status_code == 200

    mismatch = client.post(
        "/api/v1/invitations/accept", json={"token": "wrong-token"}
    )
    assert mismatch.status_code == 400

    accepted = client.post(
        "/api/v1/invitations/accept", json={"token": token}
    )
    assert accepted.status_code == 200, accepted.get_json()
    assert accepted.get_json()["organization_id"] == organization["id"]

    organizations = client.get("/api/v1/organizations").get_json()[
        "organizations"
    ]
    assert any(
        item["id"] == organization["id"] and item["role"] == "editor"
        for item in organizations
    )


def test_invitation_for_existing_member_is_rejected(app):
    client, organization, _workspace, _project = setup_org(app)
    make_user(app, "member@example.com", "Member")
    add_member(client, organization["id"], "member@example.com", "viewer")
    response = client.post(
        f"/api/v1/organizations/{organization['id']}/invitations",
        json={"email": "member@example.com", "role": "editor"},
    )
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "already_member"


def test_task_creation_notifies_other_members_and_can_be_read(app):
    client, organization, _workspace, project = setup_org(app)
    make_user(app, "editor@example.com", "Editor")
    add_member(client, organization["id"], "editor@example.com", "editor")
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert login(client, "editor@example.com").status_code == 200
    create_task(client, project["id"], "Notify the team")

    assert client.post("/api/v1/auth/logout").status_code == 200
    assert login(client, "owner@example.com").status_code == 200
    notifications = client.get("/api/v1/notifications").get_json()[
        "notifications"
    ]
    assert len(notifications) == 1
    assert notifications[0]["kind"] == "task_created"
    assert "Notify the team" in notifications[0]["message"]
    assert notifications[0]["read_at"] is None

    marked = client.patch(
        f"/api/v1/notifications/{notifications[0]['id']}"
    )
    assert marked.status_code == 200
    assert marked.get_json()["notification"]["read_at"] is not None

    read_all = client.post("/api/v1/notifications/read-all")
    assert read_all.status_code == 200
    assert read_all.get_json()["marked_read"] == 0


def test_account_export_and_delete_sole_member_organization(app):
    client, organization, _workspace, project = setup_org(app)
    create_task(client, project["id"], "Exported task")

    exported = client.get("/api/v1/account/export")
    assert exported.status_code == 200
    assert exported.mimetype == "application/json"
    body = exported.get_json()
    assert body["export_version"] == 1
    assert body["user"]["email"] == "owner@example.com"
    assert body["organizations"][0]["id"] == organization["id"]
    assert body["organizations"][0]["workspaces"][0]["projects"][0][
        "tasks"
    ][0]["name"] == "Exported task"

    wrong = client.delete(
        "/api/v1/account", json={"password": "wrong-password"}
    )
    assert wrong.status_code == 403
    deleted = client.delete(
        "/api/v1/account", json={"password": "CorrectHorse123!"}
    )
    assert deleted.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={
            "email": "owner@example.com",
            "password": "CorrectHorse123!",
        },
    ).status_code == 401
