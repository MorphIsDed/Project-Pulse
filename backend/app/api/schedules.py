from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from app.services.scheduling import build_schedule
from app.services.tenancy import require_project_membership


schedules_api = Blueprint("schedules_api", __name__, url_prefix="/api/v1")


@schedules_api.get("/projects/<int:project_id>/schedule")
@login_required
def get_project_schedule(project_id):
    project, _membership = require_project_membership(
        project_id, current_user.id
    )
    return jsonify(schedule=build_schedule(project))
