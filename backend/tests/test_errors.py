from app.api.validation import json_body, require_fields
from app.errors import ApiError


def test_not_found_uses_error_envelope(client):
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    error = response.get_json()["error"]
    assert error["code"] == "not_found"
    assert error["request_id"]
    assert response.headers["X-Request-ID"] == error["request_id"]


def test_method_not_allowed_uses_error_envelope(client):
    response = client.post("/api/v1/health")

    assert response.status_code == 405
    assert response.get_json()["error"]["code"] == "method_not_allowed"


def test_api_error_uses_error_envelope(app, client):
    @app.get("/api/v1/test/api-error")
    def raise_api_error():
        raise ApiError("teapot", "Short and stout.", 418, {"hint": "kettle"})

    response = client.get("/api/v1/test/api-error")

    assert response.status_code == 418
    error = response.get_json()["error"]
    assert error["code"] == "teapot"
    assert error["message"] == "Short and stout."
    assert error["details"] == {"hint": "kettle"}


def test_unhandled_exception_returns_internal_error(app, client):
    @app.get("/api/v1/test/crash")
    def crash():
        raise RuntimeError("boom")

    response = client.get("/api/v1/test/crash")

    assert response.status_code == 500
    error = response.get_json()["error"]
    assert error["code"] == "internal_error"
    assert "boom" not in error["message"]


def test_invalid_json_body_rejected(app, client):
    @app.post("/api/v1/test/json")
    def echo_json():
        return json_body()

    response = client.post("/api/v1/test/json", data="not json", content_type="text/plain")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_json"


def test_missing_fields_rejected(app, client):
    @app.post("/api/v1/test/fields")
    def require_demo_fields():
        data = json_body()
        require_fields(data, "name", "email")
        return {"ok": True}

    response = client.post("/api/v1/test/fields", json={"name": "Ada"})

    assert response.status_code == 400
    error = response.get_json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["fields"] == ["email"]
