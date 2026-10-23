import pytest

from app import create_app
from app.extensions import db


@pytest.fixture()
def app_factory(tmp_path):
    applications = []
    counter = {"value": 0}

    def factory(config_name="testing", overrides=None):
        counter["value"] += 1
        database_path = (tmp_path / f"test-{counter['value']}.sqlite3").as_posix()
        config = {
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
            "ALLOW_PUBLIC_SIGNUP": False,
        }
        if overrides:
            config.update(overrides)

        application = create_app(config_name, config)
        with application.app_context():
            db.create_all()

        applications.append(application)
        return application

    yield factory

    for application in applications:
        with application.app_context():
            db.session.remove()
            db.drop_all()


@pytest.fixture()
def app(app_factory):
    return app_factory()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def public_signup_app(app_factory):
    return app_factory(overrides={"ALLOW_PUBLIC_SIGNUP": True})


@pytest.fixture()
def secure_app(app_factory):
    return app_factory(overrides={"WTF_CSRF_ENABLED": True})
