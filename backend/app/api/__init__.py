from flask import Flask


def register_blueprints(app: Flask) -> None:
    from app.api.auth import auth_api
    from app.api.health import health_api

    app.register_blueprint(auth_api)
    app.register_blueprint(health_api)
