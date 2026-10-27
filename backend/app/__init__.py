import logging
from pathlib import Path

from flask import Flask

from app.api import register_blueprints
from app.cli import register_cli
from app.config import DEVELOPMENT_SECRET, get_config
from app.errors import error_response, register_error_handlers
from app.extensions import csrf, db, login_manager, migrate
from app.models import User
from app.request_context import register_request_context


def create_app(config_name: str | None = None, overrides: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_object(get_config(config_name))
    if overrides:
        app.config.update(overrides)

    _configure_logging(app)
    _validate_config(app)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    @login_manager.unauthorized_handler
    def unauthorized():
        return error_response("unauthorized", "Authentication is required.", 401)

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    register_blueprints(app)
    register_cli(app)
    register_error_handlers(app)
    register_request_context(app)

    return app


def _configure_logging(app: Flask) -> None:
    level_name = str(app.config.get("LOG_LEVEL", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    app.logger.setLevel(level)


def _validate_config(app: Flask) -> None:
    if app.config.get("APP_ENV") == "production" and not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be set when APP_ENV=production.")

    if (
        app.config.get("APP_ENV") != "production"
        and app.config.get("SECRET_KEY") == DEVELOPMENT_SECRET
    ):
        app.logger.warning(
            "Using the development SECRET_KEY. Set SECRET_KEY in .env for shared environments."
        )
