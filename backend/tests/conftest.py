import pytest

from app import create_app
from app.extensions import db


@pytest.fixture()
def app(tmp_path):
    database_path = (tmp_path / "test.sqlite3").as_posix()
    application = create_app(
        "testing",
        {
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
        },
    )
    with application.app_context():
        db.create_all()

    yield application

    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
