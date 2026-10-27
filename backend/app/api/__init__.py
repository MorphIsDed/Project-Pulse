from flask import Flask


def register_blueprints(app: Flask) -> None:
    from app.api.auth import auth_api
    from app.api.dependencies import dependencies_api
    from app.api.health import health_api
    from app.api.organizations import organizations_api
    from app.api.projects import projects_api
    from app.api.resources import resources_api
    from app.api.schedules import schedules_api
    from app.api.tasks import tasks_api
    from app.api.workspaces import workspaces_api

    app.register_blueprint(auth_api)
    app.register_blueprint(dependencies_api)
    app.register_blueprint(health_api)
    app.register_blueprint(organizations_api)
    app.register_blueprint(projects_api)
    app.register_blueprint(resources_api)
    app.register_blueprint(schedules_api)
    app.register_blueprint(tasks_api)
    app.register_blueprint(workspaces_api)
