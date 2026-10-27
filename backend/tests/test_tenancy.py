from tests.helpers import (
    add_member,
    create_org,
    create_workspace,
    logged_in_client,
    login,
    make_user,
)


def test_create_and_list_organization(app):
    client = logged_in_client(app)
    organization = create_org(client)

    assert organization["name"] == "Test Organization"
    assert organization["role"] == "owner"

    response = client.get("/api/v1/organizations")
    assert response.status_code == 200
    body = response.get_json()
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert [item["id"] for item in body["organizations"]] == [
        organization["id"]
    ]

    detail = client.get(f"/api/v1/organizations/{organization['id']}")
    assert detail.status_code == 200
    assert detail.get_json()["organization"]["role"] == "owner"


def test_organization_is_not_visible_to_non_members(app):
    client = logged_in_client(app, "owner@example.com", "Owner")
    organization = create_org(client)
    assert client.get(
        f"/api/v1/organizations/{organization['id']}"
    ).status_code == 200

    make_user(app, "outsider@example.com", "Outsider")
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert login(client, "outsider@example.com").status_code == 200
    assert client.get(
        f"/api/v1/organizations/{organization['id']}"
    ).status_code == 404
    assert client.get(
        f"/api/v1/organizations/{organization['id']}/workspaces"
    ).status_code == 404


def test_member_management_and_roles(app):
    owner = logged_in_client(app, "owner@example.com", "Owner")
    organization = create_org(owner)
    make_user(app, "editor@example.com", "Editor")
    make_user(app, "viewer@example.com", "Viewer")

    editor = add_member(owner, organization["id"], "editor@example.com", "editor")
    viewer = add_member(owner, organization["id"], "viewer@example.com", "viewer")

    members = owner.get(
        f"/api/v1/organizations/{organization['id']}/members"
    ).get_json()["members"]
    assert {member["user"]["email"] for member in members} == {
        "owner@example.com",
        "editor@example.com",
        "viewer@example.com",
    }

    promoted = owner.patch(
        f"/api/v1/organizations/{organization['id']}/members/{editor['user_id']}",
        json={"role": "admin"},
    )
    assert promoted.status_code == 200
    assert promoted.get_json()["member"]["role"] == "admin"

    removed = owner.delete(
        f"/api/v1/organizations/{organization['id']}/members/{viewer['user_id']}"
    )
    assert removed.status_code == 204
    assert len(
        owner.get(
            f"/api/v1/organizations/{organization['id']}/members"
        ).get_json()["members"]
    ) == 2


def test_editor_can_read_but_cannot_create_workspace(app):
    client = logged_in_client(app, "owner@example.com", "Owner")
    organization = create_org(client)
    make_user(app, "editor@example.com", "Editor")
    add_member(client, organization["id"], "editor@example.com", "editor")

    assert client.post("/api/v1/auth/logout").status_code == 200
    assert login(client, "editor@example.com").status_code == 200
    assert client.get(
        f"/api/v1/organizations/{organization['id']}/workspaces"
    ).status_code == 200
    response = client.post(
        f"/api/v1/organizations/{organization['id']}/workspaces",
        json={"name": "Blocked"},
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "forbidden"


def test_workspace_crud_and_case_insensitive_conflict(app):
    client = logged_in_client(app)
    organization = create_org(client)
    workspace = create_workspace(client, organization["id"], "Delivery")

    duplicate = client.post(
        f"/api/v1/organizations/{organization['id']}/workspaces",
        json={"name": "delivery"},
    )
    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"]["code"] == "workspace_conflict"

    renamed = client.patch(
        f"/api/v1/workspaces/{workspace['id']}",
        json={"name": "Delivery 2"},
    )
    assert renamed.status_code == 200
    assert renamed.get_json()["workspace"]["name"] == "Delivery 2"

    deleted = client.delete(f"/api/v1/workspaces/{workspace['id']}")
    assert deleted.status_code == 204
    assert client.get(
        f"/api/v1/workspaces/{workspace['id']}"
    ).status_code == 404


def test_last_owner_cannot_be_demoted_or_removed(app):
    client = logged_in_client(app)
    organization = create_org(client)
    owner_id = client.get("/api/v1/auth/me").get_json()["user"]["id"]

    demote = client.patch(
        f"/api/v1/organizations/{organization['id']}/members/{owner_id}",
        json={"role": "admin"},
    )
    assert demote.status_code == 409
    assert demote.get_json()["error"]["code"] == "last_owner"

    remove = client.delete(
        f"/api/v1/organizations/{organization['id']}/members/{owner_id}"
    )
    assert remove.status_code == 409
    assert remove.get_json()["error"]["code"] == "last_owner"


def test_admin_cannot_manage_owner_role(app):
    client = logged_in_client(app, "owner@example.com", "Owner")
    organization = create_org(client)
    make_user(app, "admin@example.com", "Admin")
    admin_member = add_member(
        client, organization["id"], "admin@example.com", "admin"
    )
    owner_id = client.get("/api/v1/auth/me").get_json()["user"]["id"]

    assert client.post("/api/v1/auth/logout").status_code == 200
    assert login(client, "admin@example.com").status_code == 200
    grant_owner = client.patch(
        f"/api/v1/organizations/{organization['id']}/members/{admin_member['user_id']}",
        json={"role": "owner"},
    )
    assert grant_owner.status_code == 403
    change_owner = client.patch(
        f"/api/v1/organizations/{organization['id']}/members/{owner_id}",
        json={"role": "editor"},
    )
    assert change_owner.status_code == 403


def test_tenant_routes_require_authentication(client):
    assert client.get("/api/v1/organizations").status_code == 401
    assert client.post(
        "/api/v1/organizations", json={"name": "Anonymous"}
    ).status_code == 401


def test_invalid_pagination_is_rejected(app):
    client = logged_in_client(app)

    for query in ("?limit=0", "?limit=101", "?offset=-1", "?limit=x"):
        response = client.get(f"/api/v1/organizations{query}")
        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "invalid_pagination"


def test_duplicate_member_is_rejected(app):
    client = logged_in_client(app)
    organization = create_org(client)
    make_user(app, "second@example.com", "Second")
    add_member(client, organization["id"], "second@example.com", "viewer")

    duplicate = client.post(
        f"/api/v1/organizations/{organization['id']}/members",
        json={"email": "SECOND@example.com", "role": "editor"},
    )
    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"]["code"] == "member_exists"


def test_member_add_requires_existing_user(app):
    client = logged_in_client(app)
    organization = create_org(client)

    response = client.post(
        f"/api/v1/organizations/{organization['id']}/members",
        json={"email": "missing@example.com", "role": "viewer"},
    )
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "member_not_found"


def test_owner_can_read_members(app):
    client = logged_in_client(app)
    organization = create_org(client)
    assert client.get(
        f"/api/v1/organizations/{organization['id']}/members"
    ).status_code == 200
