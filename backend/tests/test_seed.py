PASSWORD = "CorrectHorse123!"
DEMO_EMAIL = "owner@demo.local"


def login(client, password):
    return client.post(
        "/api/v1/auth/login",
        json={"email": DEMO_EMAIL, "password": password},
    )


def test_seed_uses_configured_demo_password(app_factory):
    app = app_factory(overrides={"DEMO_PASSWORD": PASSWORD})
    result = app.test_cli_runner().invoke(args=["seed-demo"])

    assert result.exit_code == 0

    client = app.test_client()
    assert login(client, PASSWORD).status_code == 200
    assert login(client, "DemoPulse123!").status_code == 401


def test_seed_rejects_invalid_demo_password(app_factory):
    app = app_factory(overrides={"DEMO_PASSWORD": "short"})

    result = app.test_cli_runner().invoke(args=["seed-demo"])

    assert result.exit_code != 0
    assert "at least 8 characters" in result.output
    assert "Traceback" not in result.output


def test_seed_force_is_allowed_in_production(app_factory):
    app = app_factory(
        "production",
        overrides={"SECRET_KEY": "production-test-secret"},
    )

    result = app.test_cli_runner().invoke(args=["seed-demo", "--force"])

    assert result.exit_code == 0
    assert "3 created, 0 skipped" in result.output
