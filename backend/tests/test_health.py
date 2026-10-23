def test_health_reports_ok_and_database(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "service": "projectpulse-api",
        "database": "ok",
    }


def test_health_echoes_request_id(client):
    response = client.get(
        "/api/v1/health", headers={"X-Request-ID": "client-request-id"}
    )

    assert response.headers["X-Request-ID"] == "client-request-id"
