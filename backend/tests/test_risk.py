from tests.helpers import (
    create_org,
    create_project,
    create_task,
    create_workspace,
    logged_in_client,
)


def setup_project(app, target_finish="2026-01-16"):
    client = logged_in_client(app)
    organization = create_org(client)
    workspace = create_workspace(client, organization["id"])
    project = create_project(client, workspace["id"])
    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={
            "version": project["version"],
            "start_date": "2026-01-05",
            "target_finish": target_finish,
        },
    )
    assert response.status_code == 200
    return client, response.get_json()["project"]


def create_dependency(client, project_id, predecessor_id, successor_id):
    response = client.post(
        f"/api/v1/projects/{project_id}/dependencies",
        json={
            "predecessor_task_id": predecessor_id,
            "successor_task_id": successor_id,
            "type": "FS",
            "lag_work_minutes": 0,
        },
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["dependency"]


def test_risk_simulation_returns_seeded_percentiles_and_criticality(app):
    client, project = setup_project(app)
    first = create_task(
        client,
        project["id"],
        "Discovery",
        duration_work_minutes=960,
        estimate_optimistic=480,
        estimate_most_likely=960,
        estimate_pessimistic=1920,
    )
    second = create_task(
        client,
        project["id"],
        "Build",
        duration_work_minutes=2400,
        estimate_optimistic=1440,
        estimate_most_likely=2400,
        estimate_pessimistic=3840,
    )
    create_dependency(client, project["id"], first["id"], second["id"])

    response = client.post(
        f"/api/v1/projects/{project['id']}/risk-simulation",
        json={"iterations": 500, "seed": 42},
    )
    assert response.status_code == 200, response.get_json()
    simulation = response.get_json()["simulation"]
    assert simulation["iterations"] == 500
    assert simulation["seed"] == 42
    assert simulation["deterministic_finish"] == "2026-01-13"
    assert (
        simulation["finish_percentiles"]["p10"]
        <= simulation["finish_percentiles"]["p50"]
        <= simulation["finish_percentiles"]["p90"]
        <= simulation["finish_percentiles"]["p95"]
    )
    assert 0 <= simulation["target_probability"] <= 1
    assert len(simulation["tasks"]) == 2
    assert all(
        task["critical_frequency"] == 1 for task in simulation["tasks"]
    )
    assert all(
        task["p10_work_minutes"]
        <= task["p50_work_minutes"]
        <= task["p90_work_minutes"]
        for task in simulation["tasks"]
    )


def test_risk_simulation_is_reproducible_with_the_same_seed(app):
    client, project = setup_project(app)
    create_task(
        client,
        project["id"],
        "Build",
        duration_work_minutes=480,
        estimate_optimistic=240,
        estimate_most_likely=480,
        estimate_pessimistic=960,
    )

    first = client.post(
        f"/api/v1/projects/{project['id']}/risk-simulation",
        json={"iterations": 100, "seed": 7},
    ).get_json()["simulation"]
    second = client.post(
        f"/api/v1/projects/{project['id']}/risk-simulation",
        json={"iterations": 100, "seed": 7},
    ).get_json()["simulation"]
    assert first == second


def test_risk_simulation_validates_iterations(app):
    client, project = setup_project(app)
    response = client.post(
        f"/api/v1/projects/{project['id']}/risk-simulation",
        json={"iterations": 20, "seed": 1},
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "validation_error"

    response = client.post(
        f"/api/v1/projects/{project['id']}/risk-simulation",
        json={"iterations": 100, "seed": "not-an-int"},
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "validation_error"
