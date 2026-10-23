from flask import Flask


def register_blueprints(app: Flask) -> None:
    from app.api.health import health_api

    app.register_blueprint(health_api)
