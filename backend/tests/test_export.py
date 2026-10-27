from tests.helpers import (
    create_org,
    create_project,
    create_task,
    create_workspace,
    logged_in_client,
)


def setup_project(app):
    client = logged_in_client(app)
    organization = create_org(client)
    workspace = create_workspace(client, organization["id"])
    project = create_project(client, workspace["id"], name="Launch Plan")
    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"version": project["version"], "start_date": "2026-01-05"},
    )
    assert response.status_code == 200
    return client, response.get_json()["project"]


def test_export_ics_contains_calendar_and_escaped_task(app):
    client, project = setup_project(app)
    create_task(
        client,
        project["id"],
        "Design, build; test",
        description="Line one\nLine two",
        duration_work_minutes=480,
    )

    response = client.get(f"/api/v1/projects/{project['id']}/export.ics")
    assert response.status_code == 200
    assert response.mimetype == "text/calendar"
    assert 'filename="Launch-Plan.ics"' in response.headers[
        "Content-Disposition"
    ]
    body = response.get_data(as_text=True)
    assert body.startswith("BEGIN:VCALENDAR\r\n")
    assert body.endswith("END:VCALENDAR\r\n")
    assert "DTSTART;VALUE=DATE:20260105" in body
    assert "DTEND;VALUE=DATE:20260106" in body
    assert "SUMMARY:Design\\, build\\; test" in body
    assert "Line one\\nLine two" in body
    assert "UID:task-" in body
    assert "X-PROJECTPULSE-TASK-ID:" in body
    assert "\n" not in body.replace("\r\n", "")


def test_export_ics_for_empty_project_is_valid(app):
    client, project = setup_project(app)
    response = client.get(f"/api/v1/projects/{project['id']}/export.ics")
    assert response.status_code == 200
    assert "BEGIN:VCALENDAR" in response.get_data(as_text=True)
    assert "BEGIN:VEVENT" not in response.get_data(as_text=True)
