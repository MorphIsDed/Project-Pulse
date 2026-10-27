from tests.helpers import PASSWORD, make_user


def csrf_headers(client):
    token = client.get("/api/v1/auth/csrf").get_json()["csrf_token"]
    return {"X-CSRFToken": token}


def login_with_csrf(client, email):
    headers = csrf_headers(client)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
        headers=headers,
    )
    assert response.status_code == 200
    return response.get_json()["csrf_token"]


def test_tenancy_mutations_require_csrf(secure_app):
    make_user(secure_app)
    client = secure_app.test_client()
    token = login_with_csrf(client, "owner@example.com")

    denied = client.post(
        "/api/v1/organizations",
        json={"name": "No Token"},
    )
    assert denied.status_code == 400
    assert denied.get_json()["error"]["code"] == "csrf_error"

    created = client.post(
        "/api/v1/organizations",
        json={"name": "With Token"},
        headers={"X-CSRFToken": token},
    )
    assert created.status_code == 201

    organization_id = created.get_json()["organization"]["id"]
    denied_patch = client.patch(
        f"/api/v1/organizations/{organization_id}",
        json={"name": "No Token"},
    )
    assert denied_patch.status_code == 400
    assert denied_patch.get_json()["error"]["code"] == "csrf_error"

    allowed_patch = client.patch(
        f"/api/v1/organizations/{organization_id}",
        json={"name": "Renamed"},
        headers={"X-CSRFToken": token},
    )
    assert allowed_patch.status_code == 200
