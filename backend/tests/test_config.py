import pytest

from app import create_app


def test_production_requires_secret_key():
    with pytest.raises(RuntimeError, match="SECRET_KEY must be set"):
        create_app("production", {"SECRET_KEY": None})


def test_unknown_environment_is_rejected():
    with pytest.raises(ValueError, match="Unknown APP_ENV"):
        create_app("staging")
