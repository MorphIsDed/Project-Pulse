import pytest

from app import create_app
from app.extensions import db
from app.models import Assignment, Notification, Resource, Task, WorkspaceInvitation
from app.models.base import utcnow
from app.services.summary import summarize_tasks
from tests.helpers import create_task, login, make_user, add_member
from tests.test_schedule import setup_project


def test_summary_known_dataset():
    result = summarize_tasks([
        ("completed", 0), ("completed", 60),
        ("in_progress", 120), ("blocked", 180),
    ], 8)
    assert result == {
        "project_version": 8, "task_count": 4, "completed_task_count": 2,
        "completion_percent": 50,
        "status_counts": {"not_started": 0, "in_progress": 1, "blocked": 1, "completed": 2},
        "duration_stats": {"mean": 120, "median": 120, "p90": 168},
    }


@pytest.mark.parametrize("records,total,completion", [([], 0, 0), ([("completed", 0)], 1, 100)])
def test_empty_and_milestone_only(records, total, completion):
    result = summarize_tasks(records, 1)
    assert result["duration_stats"] is None
    assert result["task_count"] == total
    assert result["completion_percent"] == completion
    assert len(result["status_counts"]) == 4


def test_summary_authorization_and_refresh(app):
    client, org, _, project = setup_project(app)
    url = f"/api/v1/projects/{project['id']}/summary"
    assert client.get(url).get_json()["summary"]["task_count"] == 0
    task = create_task(client, project["id"], "A", duration_work_minutes=60)
    before = client.get(url).get_json()["summary"]
    client.patch(f"/api/v1/projects/{project['id']}/tasks/{task['id']}", json={"status": "completed"})
    after = client.get(url).get_json()["summary"]
    assert after["completion_percent"] == 100
    assert after["project_version"] > before["project_version"]
    make_user(app, "viewer@example.com", "Viewer")
    add_member(client, org["id"], "viewer@example.com", "viewer")
    client.post("/api/v1/auth/logout")
    assert client.get(url).status_code == 401
    login(client, "viewer@example.com")
    assert client.get(url).status_code == 200
    client.post("/api/v1/auth/logout")
    make_user(app, "outsider@example.com", "Outsider")
    login(client, "outsider@example.com")
    assert client.get(url).status_code == 404


def test_legacy_records_survive_restart_and_task_edit(app):
    client, org, _, project = setup_project(app)
    task = create_task(client, project["id"], "Existing", estimate_optimistic=10,
                       estimate_most_likely=20, estimate_pessimistic=30)
    with app.app_context():
        user_id = db.session.get(Task, task["id"]).project.created_by
        resource = Resource(project_id=project["id"], name="Legacy resource")
        db.session.add(resource)
        db.session.flush()
        db.session.add_all([
            Assignment(project_id=project["id"], resource_id=resource.id, task_id=task["id"]),
            Notification(user_id=user_id, organization_id=org["id"], project_id=project["id"],
                         kind="legacy", message="Preserve me", created_at=utcnow()),
            WorkspaceInvitation(organization_id=org["id"], email="old@example.com",
                                token_hash="a" * 64, invited_by=user_id,
                                expires_at=utcnow(), created_at=utcnow()),
        ])
        db.session.commit()
    restarted = create_app("testing", {"SQLALCHEMY_DATABASE_URI": app.config["SQLALCHEMY_DATABASE_URI"]})
    new_client = restarted.test_client()
    login(new_client)
    response = new_client.patch(f"/api/v1/projects/{project['id']}/tasks/{task['id']}", json={"name": "Renamed"})
    assert response.status_code == 200
    with restarted.app_context():
        for model in (Resource, Assignment, Notification, WorkspaceInvitation):
            assert db.session.scalar(db.select(db.func.count()).select_from(model)) == 1
        saved = db.session.get(Task, task["id"])
        assert (saved.estimate_optimistic, saved.estimate_most_likely, saved.estimate_pessimistic) == (10, 20, 30)
        db.session.remove()
        db.engine.dispose()


def test_retired_routes_absent(app):
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    for word in ("resources", "assignments", "workload", "leveling", "risk", "notifications", "invitations", "account"):
        assert not any(word in path for path in paths)
    client = app.test_client()
    assert client.get("/api/v1/notifications").status_code == 404
