import re


def test_request_id_is_generated(client):
    response = client.get("/api/v1/health")

    request_id = response.headers["X-Request-ID"]
    assert re.fullmatch(r"[0-9a-f]{32}", request_id)


def test_request_id_is_truncated_to_128_characters(client):
    request_id = "a" * 200

    response = client.get(
        "/api/v1/health", headers={"X-Request-ID": request_id}
    )

    assert response.headers["X-Request-ID"] == "a" * 128
