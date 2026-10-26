import pytest

from app import create_app


def test_production_requires_secret_key():
    with pytest.raises(RuntimeError, match="SECRET_KEY must be set"):
        create_app("production", {"SECRET_KEY": None})


def test_unknown_environment_is_rejected():
    with pytest.raises(ValueError, match="Unknown APP_ENV"):
        create_app("staging")


def test_production_cookies_are_secure(app_factory):
    app = app_factory(
        "production",
        overrides={"SECRET_KEY": "production-test-secret-with-32-characters", "TESTING": True},
    )

    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["REMEMBER_COOKIE_SECURE"] is True
