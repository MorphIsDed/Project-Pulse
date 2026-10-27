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


def setup_project(app, start_date="2026-01-05", target_finish=None):
    client = logged_in_client(app)
    organization = create_org(client)
    workspace = create_workspace(client, organization["id"])
    project = create_project(client, workspace["id"])
    payload = {"version": project["version"], "start_date": start_date}
    if target_finish is not None:
        payload["target_finish"] = target_finish
    response = client.patch(
        f"/api/v1/projects/{project['id']}", json=payload
    )
    assert response.status_code == 200
    return client, organization, response.get_json()["project"]


def create_resource(
    client,
    project_id,
    name="Developer",
    capacity=480,
    role="Engineering",
):
    response = client.post(
        f"/api/v1/projects/{project_id}/resources",
        json={
            "name": name,
            "role": role,
            "capacity_work_minutes_per_day": capacity,
        },
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def create_assignment(
    client, project_id, resource_id, task_id, allocation=100
):
    response = client.post(
        f"/api/v1/projects/{project_id}/assignments",
        json={
            "resource_id": resource_id,
            "task_id": task_id,
            "allocation_percent": allocation,
        },
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def switch_to(client, app, email, display_name, role, organization_id):
    make_user(app, email, display_name)
    add_member(client, organization_id, email, role)
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert login(client, email).status_code == 200


def test_resource_and_assignment_crud(app):
    client, _organization, project = setup_project(app)
    created = create_resource(client, project["id"], capacity=240)
    resource = created["resource"]
    assert resource["capacity_work_minutes_per_day"] == 240
    assert created["project_version"] == project["version"] + 1

    updated = client.patch(
        f"/api/v1/projects/{project['id']}/resources/{resource['id']}",
        json={
            "name": "Lead Developer",
            "role": "Delivery",
            "capacity_work_minutes_per_day": 300,
        },
    )
    assert updated.status_code == 200
    resource = updated.get_json()["resource"]
    assert resource["name"] == "Lead Developer"
    assert resource["capacity_work_minutes_per_day"] == 300

    task = create_task(
        client, project["id"], "Build", duration_work_minutes=480
    )
    assignment = create_assignment(
        client, project["id"], resource["id"], task["id"], allocation=50
    )["assignment"]
    assert assignment["allocation_percent"] == 50

    changed = client.patch(
        f"/api/v1/projects/{project['id']}/assignments/{assignment['id']}",
        json={"allocation_percent": 75},
    )
    assert changed.status_code == 200
    assert changed.get_json()["assignment"]["allocation_percent"] == 75

    listed = client.get(
        f"/api/v1/projects/{project['id']}/assignments"
    ).get_json()
    assert [item["id"] for item in listed["assignments"]] == [
        assignment["id"]
    ]

    deleted = client.delete(
        f"/api/v1/projects/{project['id']}/assignments/{assignment['id']}"
    )
    assert deleted.status_code == 204
    deleted = client.delete(
        f"/api/v1/projects/{project['id']}/resources/{resource['id']}"
    )
    assert deleted.status_code == 204


def test_resource_and_assignment_validation(app):
    client, _organization, project = setup_project(app)
    resource = create_resource(
        client, project["id"], name="Developer"
    )["resource"]

    duplicate = client.post(
        f"/api/v1/projects/{project['id']}/resources",
        json={"name": "developer"},
    )
    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"]["code"] == "resource_conflict"

    invalid_capacity = client.post(
        f"/api/v1/projects/{project['id']}/resources",
        json={"name": "Zero", "capacity_work_minutes_per_day": 0},
    )
    assert invalid_capacity.status_code == 400
    assert invalid_capacity.get_json()["error"]["code"] == "invalid_capacity"

    task = create_task(client, project["id"], "Task")
    other_project = client.post(
        f"/api/v1/workspaces/{project['workspace_id']}/projects",
        json={"name": "Other Project"},
    ).get_json()["project"]
    other_task = create_task(client, other_project["id"], "Other task")
    cross_project = client.post(
        f"/api/v1/projects/{project['id']}/assignments",
        json={"resource_id": resource["id"], "task_id": other_task["id"]},
    )
    assert cross_project.status_code == 400
    assert cross_project.get_json()["error"]["code"] == "invalid_task"

    create_assignment(
        client,
        project["id"],
        resource["id"],
        task["id"],
        allocation=100,
    )
    duplicate_assignment = client.post(
        f"/api/v1/projects/{project['id']}/assignments",
        json={"resource_id": resource["id"], "task_id": task["id"]},
    )
    assert duplicate_assignment.status_code == 409
    assert (
        duplicate_assignment.get_json()["error"]["code"]
        == "duplicate_assignment"
    )


def test_workload_reports_overload_and_contributors(app):
    client, _organization, project = setup_project(app)
    first = create_task(
        client, project["id"], "First", duration_work_minutes=480
    )
    second = create_task(
        client, project["id"], "Second", duration_work_minutes=480
    )
    resource = create_resource(client, project["id"], capacity=480)[
        "resource"
    ]
    create_assignment(client, project["id"], resource["id"], first["id"])
    create_assignment(client, project["id"], resource["id"], second["id"])

    response = client.get(f"/api/v1/projects/{project['id']}/workload")
    assert response.status_code == 200
    workload = response.get_json()["workload"]
    assert workload["summary"]["overload_count"] == 1
    assert workload["summary"]["excess_work_minutes"] == 480
    overload = workload["overloads"][0]
    assert overload["date"] == "2026-01-05"
    assert overload["assigned_work_minutes"] == 960
    assert overload["capacity_work_minutes"] == 480
    assert overload["load_percent"] == 200.0
    assert {task["task_id"] for task in overload["tasks"]} == {
        first["id"],
        second["id"],
    }


def test_workload_uses_assignment_allocation(app):
    client, _organization, project = setup_project(app)
    task = create_task(
        client, project["id"], "Half time", duration_work_minutes=480
    )
    resource = create_resource(client, project["id"], capacity=480)[
        "resource"
    ]
    create_assignment(
        client, project["id"], resource["id"], task["id"], allocation=50
    )

    workload = client.get(
        f"/api/v1/projects/{project['id']}/workload"
    ).get_json()["workload"]
    day = workload["resources"][0]["load_days"][0]
    assert day["assigned_work_minutes"] == 240
    assert day["load_percent"] == 50.0
    assert day["overloaded"] is False
    assert workload["overloads"] == []


def test_leveling_preview_delays_lower_priority_task_without_persisting(app):
    client, _organization, project = setup_project(
        app, target_finish="2026-01-07"
    )
    lower = create_task(
        client,
        project["id"],
        "Lower priority",
        duration_work_minutes=480,
        priority=5,
    )
    higher = create_task(
        client,
        project["id"],
        "Higher priority",
        duration_work_minutes=480,
        priority=3,
    )
    resource = create_resource(client, project["id"], capacity=480)[
        "resource"
    ]
    create_assignment(client, project["id"], resource["id"], lower["id"])
    create_assignment(client, project["id"], resource["id"], higher["id"])
    current_version = client.get(
        f"/api/v1/projects/{project['id']}"
    ).get_json()["project"]["version"]

    preview = client.get(
        f"/api/v1/projects/{project['id']}/leveling-preview"
    ).get_json()["preview"]
    assert preview["before"]["overload_count"] == 1
    assert preview["before"]["excess_work_minutes"] == 480
    assert preview["after"]["excess_work_minutes"] == 0
    assert len(preview["proposals"]) == 1
    proposal = preview["proposals"][0]
    assert proposal["task_id"] == lower["id"]
    assert proposal["proposed_start"] == "2026-01-06"
    assert proposal["proposed_constraint_type"] == "start_no_earlier_than"
    assert preview["after"]["project_finish"] == "2026-01-05"

    schedule = client.get(
        f"/api/v1/projects/{project['id']}/schedule"
    ).get_json()["schedule"]
    assert next(
        task for task in schedule["tasks"] if task["id"] == lower["id"]
    )["early_start"] == "2026-01-05"
    assert schedule["project_version"] == current_version


def test_viewer_can_read_workload_but_cannot_manage_resources(app):
    client, organization, project = setup_project(app)
    switch_to(
        client,
        app,
        "viewer@example.com",
        "Viewer",
        "viewer",
        organization["id"],
    )

    assert client.get(
        f"/api/v1/projects/{project['id']}/workload"
    ).status_code == 200
    assert client.get(
        f"/api/v1/projects/{project['id']}/leveling-preview"
    ).status_code == 200
    denied = client.post(
        f"/api/v1/projects/{project['id']}/resources",
        json={"name": "Viewer Resource"},
    )
    assert denied.status_code == 403
