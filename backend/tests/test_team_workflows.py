import re

from app import get_db
from app.services.identity import create_user


PASSWORD = "CorrectHorse123!"


def setup_project(app, client, second_user=False):
    with app.app_context():
        owner = create_user("owner-flow@example.com", PASSWORD, "Owner")
        owner_id = owner.id
        teammate_id = None
        if second_user:
            teammate_id = create_user("member-flow@example.com", PASSWORD, "Member").id
        db = get_db()
        org_id = db.execute("INSERT INTO organizations(name) VALUES('Flow Org')").lastrowid
        db.execute(
            "INSERT INTO organization_memberships(organization_id,user_id,role) VALUES(?,?,'owner')",
            (org_id, owner_id),
        )
        if teammate_id:
            db.execute(
                "INSERT INTO organization_memberships(organization_id,user_id,role) VALUES(?,?,'member')",
                (org_id, teammate_id),
            )
        workspace_id = db.execute(
            "INSERT INTO workspaces(organization_id,name) VALUES(?, 'Flow Workspace')",
            (org_id,),
        ).lastrowid
        project_id = db.execute(
            "INSERT INTO projects(workspace_id,name,created_by) VALUES(?, 'Flow Project',?)",
            (workspace_id, owner_id),
        ).lastrowid
        db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner-flow@example.com", "password": PASSWORD},
    )
    assert response.status_code == 200
    return owner_id, teammate_id, org_id, project_id


def test_calendar_persists_timezone_workdays_and_holidays(app, client):
    _, _, _, project_id = setup_project(app, client)
    response = client.put(
        f"/api/v1/projects/{project_id}/calendar",
        json={
            "timezone": "Asia/Kolkata",
            "working_days": [0, 1, 2, 3, 4, 5],
            "holidays": ["2026-12-25"],
        },
    )

    assert response.status_code == 200
    calendar = client.get(f"/api/v1/projects/{project_id}/calendar").get_json()["calendar"]
    assert calendar["timezone"] == "Asia/Kolkata"
    assert calendar["weekly_rules"]["working_days"] == [0, 1, 2, 3, 4, 5]
    assert calendar["exceptions"]["holidays"] == ["2026-12-25"]


def test_task_assignment_notifies_workspace_member(app, client):
    _, teammate_id, _, project_id = setup_project(app, client, second_user=True)
    created = client.post(
        f"/api/v1/projects/{project_id}/tasks",
        json={"name": "Review proposal", "duration_work_minutes": 60},
    )
    assert created.status_code == 201
    task_id = created.get_json()["task"]["id"]

    response = client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        json={"owner_user_id": teammate_id},
    )

    assert response.status_code == 200
    with app.app_context():
        notification = get_db().execute(
            "SELECT message FROM notifications WHERE user_id=?", (teammate_id,)
        ).fetchone()
        assert notification["message"] == "You were assigned to Review proposal"


def test_invitation_is_accepted_only_by_matching_verified_user(app, client, monkeypatch):
    _, teammate_id, org_id, _ = setup_project(app, client, second_user=True)
    with app.app_context():
        get_db().execute(
            "DELETE FROM organization_memberships WHERE organization_id=? AND user_id=?",
            (org_id, teammate_id),
        )
        get_db().commit()
    sent = []
    monkeypatch.setattr("app.api.invitations.send_email", lambda *args: sent.append(args))

    response = client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        json={"email": "member-flow@example.com", "role": "member"},
    )
    assert response.status_code == 201
    token = re.search(r"invite_token=([^\s]+)", sent[0][2]).group(1)

    invitee = app.test_client()
    assert invitee.post(
        "/api/v1/auth/login",
        json={"email": "member-flow@example.com", "password": PASSWORD},
    ).status_code == 200
    accepted = invitee.post("/api/v1/invitations/accept", json={"token": token})

    assert accepted.status_code == 200
    with app.app_context():
        membership = get_db().execute(
            "SELECT role FROM organization_memberships WHERE organization_id=? AND user_id=?",
            (org_id, teammate_id),
        ).fetchone()
        assert membership["role"] == "member"
