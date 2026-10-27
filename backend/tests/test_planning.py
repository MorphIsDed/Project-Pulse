from app.extensions import db
from app.models.planning import Dependency, Project, ProjectCalendar, Task
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


def setup_project(app):
    client = logged_in_client(app)
    organization = create_org(client)
    workspace = create_workspace(client, organization["id"])
    project = create_project(client, workspace["id"])
    return client, organization, workspace, project


def switch_to(client, app, email, display_name, role, organization_id):
    make_user(app, email, display_name)
    add_member(client, organization_id, email, role)
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert login(client, email).status_code == 200


def test_project_crud_and_default_calendar(app):
    client, organization, workspace, project = setup_project(app)

    assert project["status"] == "active"
    assert project["version"] == 1
    assert project["calendar_id"] is not None

    listed = client.get(
        f"/api/v1/workspaces/{workspace['id']}/projects"
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.get_json()["projects"]] == [
        project["id"]
    ]

    calendar = client.get(
        f"/api/v1/projects/{project['id']}/calendar"
    )
    assert calendar.status_code == 200
    body = calendar.get_json()["calendar"]
    assert body["timezone"] == "UTC"
    assert body["weekly_rules"]["mon"] == [["09:00", "17:00"]]
    assert body["weekly_rules"]["sat"] == []


def test_duplicate_project_name_is_case_insensitive(app):
    client, _organization, workspace, _project = setup_project(app)
    duplicate = client.post(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        json={"name": "test project"},
    )
    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"]["code"] == "project_conflict"


def test_project_update_requires_version_and_validates_dates(app):
    client, _organization, _workspace, project = setup_project(app)

    missing_version = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"name": "Renamed"},
    )
    assert missing_version.status_code == 400
    assert missing_version.get_json()["error"]["code"] == "validation_error"

    stale = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"version": 99, "name": "Renamed"},
    )
    assert stale.status_code == 409
    assert stale.get_json()["error"]["code"] == "stale_project"

    invalid_dates = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={
            "version": 1,
            "start_date": "2026-02-01",
            "target_finish": "2026-01-01",
        },
    )
    assert invalid_dates.status_code == 400
    assert invalid_dates.get_json()["error"]["code"] == "invalid_date_range"

    updated = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={
            "version": 1,
            "name": "Renamed",
            "status": "on_hold",
            "start_date": "2026-01-01",
            "target_finish": "2026-02-01",
        },
    )
    assert updated.status_code == 200
    body = updated.get_json()["project"]
    assert body["name"] == "Renamed"
    assert body["status"] == "on_hold"
    assert body["version"] == 2


def test_editor_can_plan_but_cannot_delete_project(app):
    client, organization, workspace, project = setup_project(app)
    switch_to(
        client,
        app,
        "editor@example.com",
        "Editor",
        "editor",
        organization["id"],
    )

    created = client.post(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        json={"name": "Editor Project"},
    )
    assert created.status_code == 201
    task = create_task(client, project["id"], "Editor Task")
    assert task["name"] == "Editor Task"

    denied = client.delete(f"/api/v1/projects/{project['id']}")
    assert denied.status_code == 403


def test_viewer_is_read_only(app):
    client, organization, workspace, project = setup_project(app)
    task = create_task(client, project["id"], "Existing")
    switch_to(
        client,
        app,
        "viewer@example.com",
        "Viewer",
        "viewer",
        organization["id"],
    )

    assert client.get(
        f"/api/v1/workspaces/{workspace['id']}/projects"
    ).status_code == 200
    assert client.get(
        f"/api/v1/projects/{project['id']}/tasks"
    ).status_code == 200
    assert client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        json={"name": "Blocked"},
    ).status_code == 403
    assert client.patch(
        f"/api/v1/projects/{project['id']}/tasks/{task['id']}",
        json={"progress": 50},
    ).status_code == 403


def test_task_crud_validation_and_hierarchy(app):
    client, _organization, _workspace, project = setup_project(app)
    parent = create_task(
        client,
        project["id"],
        "Parent",
        duration_work_minutes=120,
        priority=2,
        status="in_progress",
    )
    child = create_task(
        client,
        project["id"],
        "Child",
        parent_task_id=parent["id"],
    )

    assert child["parent_task_id"] == parent["id"]

    updated = client.patch(
        f"/api/v1/projects/{project['id']}/tasks/{child['id']}",
        json={
            "progress": 40,
            "constraint_type": "must_finish_on",
            "constraint_date": "2026-03-01",
            "estimate_optimistic": 1,
            "estimate_most_likely": 2,
            "estimate_pessimistic": 3,
        },
    )
    assert updated.status_code == 200
    body = updated.get_json()["task"]
    assert body["progress"] == 40
    assert body["constraint_date"] == "2026-03-01"
    assert body["estimate_pessimistic"] == 3

    invalid_estimates = client.patch(
        f"/api/v1/projects/{project['id']}/tasks/{child['id']}",
        json={
            "estimate_optimistic": 5,
            "estimate_most_likely": 2,
            "estimate_pessimistic": 3,
        },
    )
    assert invalid_estimates.status_code == 400
    assert (
        invalid_estimates.get_json()["error"]["code"] == "invalid_estimates"
    )

    self_parent = client.patch(
        f"/api/v1/projects/{project['id']}/tasks/{parent['id']}",
        json={"parent_task_id": parent["id"]},
    )
    assert self_parent.status_code == 400
    assert self_parent.get_json()["error"]["code"] == "invalid_parent"

    cycle = client.patch(
        f"/api/v1/projects/{project['id']}/tasks/{parent['id']}",
        json={"parent_task_id": child["id"]},
    )
    assert cycle.status_code == 400
    assert cycle.get_json()["error"]["code"] == "parent_cycle"

    filtered = client.get(
        f"/api/v1/projects/{project['id']}/tasks?parent_task_id={parent['id']}"
    )
    assert [task["id"] for task in filtered.get_json()["tasks"]] == [
        child["id"]
    ]


def test_task_delete_nulls_children_and_cascades_dependencies(app):
    client, _organization, _workspace, project = setup_project(app)
    first = create_task(client, project["id"], "First")
    second = create_task(
        client, project["id"], "Second", parent_task_id=first["id"]
    )
    third = create_task(client, project["id"], "Third")
    dependency = client.post(
        f"/api/v1/projects/{project['id']}/dependencies",
        json={
            "predecessor_task_id": first["id"],
            "successor_task_id": third["id"],
        },
    )
    assert dependency.status_code == 201

    assert client.delete(
        f"/api/v1/projects/{project['id']}/tasks/{first['id']}"
    ).status_code == 204

    with app.app_context():
        assert db.session.get(Task, second["id"]).parent_task_id is None
        assert db.session.get(Dependency, dependency.get_json()["dependency"]["id"]) is None


def test_dependencies_validate_links_and_cycles(app):
    client, _organization, _workspace, project = setup_project(app)
    first = create_task(client, project["id"], "First")
    second = create_task(client, project["id"], "Second")
    third = create_task(client, project["id"], "Third")

    created = client.post(
        f"/api/v1/projects/{project['id']}/dependencies",
        json={
            "predecessor_task_id": first["id"],
            "successor_task_id": second["id"],
            "type": "SS",
            "lag_work_minutes": -30,
        },
    )
    assert created.status_code == 201
    assert created.get_json()["dependency"]["type"] == "SS"
    assert created.get_json()["dependency"]["lag_work_minutes"] == -30

    duplicate = client.post(
        f"/api/v1/projects/{project['id']}/dependencies",
        json={
            "predecessor_task_id": first["id"],
            "successor_task_id": second["id"],
            "type": "SS",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"]["code"] == "duplicate_dependency"

    self_link = client.post(
        f"/api/v1/projects/{project['id']}/dependencies",
        json={
            "predecessor_task_id": first["id"],
            "successor_task_id": first["id"],
        },
    )
    assert self_link.status_code == 400
    assert self_link.get_json()["error"]["code"] == "self_dependency"

    assert client.post(
        f"/api/v1/projects/{project['id']}/dependencies",
        json={
            "predecessor_task_id": second["id"],
            "successor_task_id": third["id"],
        },
    ).status_code == 201
    cycle = client.post(
        f"/api/v1/projects/{project['id']}/dependencies",
        json={
            "predecessor_task_id": third["id"],
            "successor_task_id": first["id"],
        },
    )
    assert cycle.status_code == 409
    assert cycle.get_json()["error"]["code"] == "dependency_cycle"


def test_cross_project_dependency_is_rejected(app):
    client = logged_in_client(app)
    organization = create_org(client)
    workspace = create_workspace(client, organization["id"])
    first_project = create_project(client, workspace["id"], "First Project")
    second_project = create_project(client, workspace["id"], "Second Project")
    first = create_task(client, first_project["id"], "First")
    second = create_task(client, second_project["id"], "Second")

    response = client.post(
        f"/api/v1/projects/{first_project['id']}/dependencies",
        json={
            "predecessor_task_id": first["id"],
            "successor_task_id": second["id"],
        },
    )
    assert response.status_code == 400
    assert (
        response.get_json()["error"]["code"]
        == "cross_project_dependency"
    )


def test_project_delete_cascades_planning_data(app):
    client, _organization, _workspace, project = setup_project(app)
    create_task(client, project["id"], "Task")
    assert client.delete(f"/api/v1/projects/{project['id']}").status_code == 204

    with app.app_context():
        assert db.session.get(Project, project["id"]) is None
        assert db.session.scalar(
            db.select(ProjectCalendar).where(
                ProjectCalendar.project_id == project["id"]
            )
        ) is None
        assert db.session.scalar(
            db.select(Task).where(Task.project_id == project["id"])
        ) is None


def test_planning_routes_require_authentication(client):
    assert client.get("/api/v1/projects/1/tasks").status_code == 401
    assert client.post(
        "/api/v1/projects/1/tasks", json={"name": "Anonymous"}
    ).status_code == 401
