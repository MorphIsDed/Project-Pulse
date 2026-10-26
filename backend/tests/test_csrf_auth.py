from app.services.identity import create_user

PASSWORD = "CorrectHorse123!"
EMAIL = "csrf@example.com"


def create_user_for(app):
    with app.app_context():
        create_user(EMAIL, PASSWORD, "CSRF User")


def csrf_headers(client):
    token = client.get("/api/v1/auth/csrf").get_json()["csrf_token"]
    return {"X-CSRFToken": token}


def test_csrf_endpoint_returns_token(secure_app):
    client = secure_app.test_client()

    response = client.get("/api/v1/auth/csrf")

    assert response.status_code == 200
    token = response.get_json()["csrf_token"]
    assert isinstance(token, str)
    assert token


def test_login_requires_csrf_token(secure_app):
    create_user_for(secure_app)
    client = secure_app.test_client()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "csrf_error"


def test_login_succeeds_with_csrf_token(secure_app):
    create_user_for(secure_app)
    client = secure_app.test_client()
    headers = csrf_headers(client)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.get_json()["user"]["email"] == EMAIL


def test_logout_requires_csrf_token(secure_app):
    create_user_for(secure_app)
    client = secure_app.test_client()
    headers = csrf_headers(client)
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
            headers=headers,
        ).status_code
        == 200
    )

    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "csrf_error"


def test_register_requires_csrf_token(secure_public_app):
    client = secure_public_app.test_client()
    payload = {
        "email": "new@example.com",
        "password": PASSWORD,
        "display_name": "New User",
    }

    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "csrf_error"

    headers = csrf_headers(client)
    response = client.post("/api/v1/auth/register", json=payload, headers=headers)

    assert response.status_code == 201
    assert response.get_json()["user"]["email"] == "new@example.com"


def test_logout_accepts_token_returned_by_login(secure_app):
    create_user_for(secure_app)
    client = secure_app.test_client()

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        headers=csrf_headers(client),
    )
    assert login_response.status_code == 200

    returned_token = login_response.get_json()["csrf_token"]
    response = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRFToken": returned_token},
    )

    assert response.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_mutation_rejects_an_untrusted_origin(secure_app):
    client = secure_app.test_client()
    headers = csrf_headers(client)
    headers["Origin"] = "https://attacker.example"

    response = client.post(
        "/api/v1/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        headers=headers,
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "origin_denied"
