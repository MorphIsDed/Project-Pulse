from sqlalchemy import text

from app.config import DevelopmentConfig
from app.extensions import db


def test_sqlite_foreign_keys_are_enabled(app):
    with app.app_context():
        assert db.session.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_testing_database_is_isolated(app):
    assert app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:///")


def test_csrf_is_enabled_by_default():
    assert DevelopmentConfig.WTF_CSRF_ENABLED is True
