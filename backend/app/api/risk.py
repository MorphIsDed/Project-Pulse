from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from app.api.validation import json_body
from app.services.risk import simulate_project_risk
from app.services.tenancy import require_project_membership


risk_api = Blueprint("risk_api", __name__, url_prefix="/api/v1")


@risk_api.post("/projects/<int:project_id>/risk-simulation")
@login_required
def post_risk_simulation(project_id):
    project, _membership = require_project_membership(
        project_id, current_user.id
    )
    return jsonify(simulation=simulate_project_risk(project, json_body()))
