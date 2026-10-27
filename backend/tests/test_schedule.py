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


def setup_project(app, start_date="2026-01-05"):
    client = logged_in_client(app)
    organization = create_org(client)
    workspace = create_workspace(client, organization["id"])
    project = create_project(client, workspace["id"])
    if start_date is not None:
        response = client.patch(
            f"/api/v1/projects/{project['id']}",
            json={"version": project["version"], "start_date": start_date},
        )
        assert response.status_code == 200
        project = response.get_json()["project"]
    return client, organization, workspace, project


def switch_to(client, app, email, display_name, role, organization_id):
    make_user(app, email, display_name)
    add_member(client, organization_id, email, role)
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert login(client, email).status_code == 200


def test_schedule_returns_task_dates_and_critical_path(app):
    client, _organization, _workspace, project = setup_project(app)
    first = create_task(
        client, project["id"], "First", duration_work_minutes=480
    )
    second = create_task(
        client, project["id"], "Second", duration_work_minutes=240
    )
    dependency = client.post(
        f"/api/v1/projects/{project['id']}/dependencies",
        json={
            "predecessor_task_id": first["id"],
            "successor_task_id": second["id"],
            "type": "FS",
        },
    )
    assert dependency.status_code == 201

    response = client.get(f"/api/v1/projects/{project['id']}/schedule")
    assert response.status_code == 200
    schedule = response.get_json()["schedule"]

    assert schedule["project_start"] == "2026-01-05"
    assert schedule["project_finish"] == "2026-01-06"
    assert schedule["start_source"] == "project"
    assert schedule["critical_path"] == [first["id"], second["id"]]
    assert len(schedule["tasks"]) == 2
    assert schedule["tasks"][0]["early_start_at"] == "2026-01-05T09:00+00:00"
    assert schedule["tasks"][0]["early_finish_at"] == "2026-01-05T17:00+00:00"
    assert schedule["tasks"][1]["early_start_at"] == "2026-01-06T09:00+00:00"
    assert schedule["tasks"][0]["critical"] is True
    assert schedule["tasks"][0]["total_float_work_minutes"] == 0


def test_schedule_defaults_to_today_when_project_start_is_missing(app):
    client, _organization, _workspace, project = setup_project(
        app, start_date=None
    )

    response = client.get(f"/api/v1/projects/{project['id']}/schedule")
    assert response.status_code == 200
    schedule = response.get_json()["schedule"]

    assert schedule["start_source"] == "today_default"
    assert schedule["warnings"][0]["code"] == "project_start_defaulted"
    assert schedule["project_start"] == schedule["requested_start"]


def test_calendar_update_requires_version_and_validates_timezone(app):
    client, _organization, _workspace, project = setup_project(app)

    missing_version = client.patch(
        f"/api/v1/projects/{project['id']}/calendar",
        json={"timezone": "UTC"},
    )
    assert missing_version.status_code == 400
    assert missing_version.get_json()["error"]["code"] == "validation_error"

    stale = client.patch(
        f"/api/v1/projects/{project['id']}/calendar",
        json={"version": 99, "timezone": "UTC"},
    )
    assert stale.status_code == 409
    assert stale.get_json()["error"]["code"] == "stale_project"

    invalid = client.patch(
        f"/api/v1/projects/{project['id']}/calendar",
        json={"version": 2, "timezone": "Not/AZone"},
    )
    assert invalid.status_code == 400
    assert invalid.get_json()["error"]["code"] == "invalid_timezone"


def test_calendar_update_bumps_project_version_and_changes_schedule(app):
    client, _organization, _workspace, project = setup_project(app)
    create_task(
        client, project["id"], "Full day", duration_work_minutes=480
    )
    current = client.get(f"/api/v1/projects/{project['id']}").get_json()[
        "project"
    ]

    response = client.patch(
        f"/api/v1/projects/{project['id']}/calendar",
        json={
            "version": current["version"],
            "timezone": "America/New_York",
            "weekly_rules": {
                "mon": [["08:00", "12:00"]],
                "tue": [["08:00", "12:00"]],
                "wed": [["08:00", "12:00"]],
                "thu": [["08:00", "12:00"]],
                "fri": [["08:00", "12:00"]],
                "sat": [],
                "sun": [],
            },
            "exceptions": [
                {"date": "2026-01-06", "name": "Holiday", "working": False}
            ],
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["calendar"]["timezone"] == "America/New_York"
    assert body["project"]["version"] == current["version"] + 1

    schedule = client.get(
        f"/api/v1/projects/{project['id']}/schedule"
    ).get_json()["schedule"]
    task = schedule["tasks"][0]
    assert task["early_start_at"] == "2026-01-05T08:00-05:00"
    assert task["early_finish_at"] == "2026-01-07T12:00-05:00"


def test_viewer_can_read_schedule_but_cannot_edit_calendar(app):
    client, organization, _workspace, project = setup_project(app)
    switch_to(
        client,
        app,
        "viewer@example.com",
        "Viewer",
        "viewer",
        organization["id"],
    )

    assert client.get(
        f"/api/v1/projects/{project['id']}/schedule"
    ).status_code == 200
    denied = client.patch(
        f"/api/v1/projects/{project['id']}/calendar",
        json={"version": project["version"], "timezone": "UTC"},
    )
    assert denied.status_code == 403
