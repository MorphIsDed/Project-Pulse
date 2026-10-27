from app.services.identity import create_user

PASSWORD = "CorrectHorse123!"


def make_user(
    app,
    email="owner@example.com",
    display_name="Owner",
    password=PASSWORD,
):
    with app.app_context():
        return create_user(email, password, display_name).id


def login(client, email="owner@example.com", password=PASSWORD):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )


def logged_in_client(app, email="owner@example.com", display_name="Owner"):
    client = app.test_client()
    make_user(app, email, display_name)
    response = login(client, email)
    assert response.status_code == 200
    return client


def create_org(client, name="Test Organization"):
    response = client.post("/api/v1/organizations", json={"name": name})
    assert response.status_code == 201, response.get_json()
    return response.get_json()["organization"]


def create_workspace(client, organization_id, name="Test Workspace"):
    response = client.post(
        f"/api/v1/organizations/{organization_id}/workspaces",
        json={"name": name},
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["workspace"]


def add_member(client, organization_id, email, role):
    response = client.post(
        f"/api/v1/organizations/{organization_id}/members",
        json={"email": email, "role": role},
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["member"]


def create_project(client, workspace_id, name="Test Project"):
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/projects",
        json={"name": name},
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["project"]


def create_task(client, project_id, name="Test Task", **fields):
    payload = {"name": name, **fields}
    response = client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json=payload,
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["task"]
